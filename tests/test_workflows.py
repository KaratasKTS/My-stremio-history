"""Orchestration tests with fake API/Cinemeta clients and scripted prompts (no network, no stdin)."""

from __future__ import annotations

import pytest

from stremio_watched import prompts
from stremio_watched.api import StremioAPIError
from stremio_watched.cli import build_parser, main
from stremio_watched.db import Database
from stremio_watched.models import MovieMeta
from stremio_watched.workflows import App, Options


class FakeStremio:
    def __init__(self, library, valid_key="good-key"):
        self.library = library
        self.valid_key = valid_key
        self.fetch_calls = 0
        self.logins: list[tuple[str, str]] = []

    def login(self, email, password):
        self.logins.append((email, password))
        if password != "secret":
            raise StremioAPIError(2, "User not found")
        return self.valid_key

    def fetch_library(self, auth_key):
        self.fetch_calls += 1
        if auth_key != self.valid_key:
            raise StremioAPIError(1, "Session does not exist")
        return self.library


class FakeCinemeta:
    def __init__(self, metas):
        self.metas = metas
        self.requested: list[set[str]] = []

    def fetch_many(self, ids, progress=None):
        wanted = set(ids)
        self.requested.append(wanted)
        return {i: m for i, m in self.metas.items() if i in wanted}


@pytest.fixture
def db():
    with Database(":memory:") as database:
        yield database


@pytest.fixture
def app(db, raw_library, metas):
    return App(db, api=FakeStremio(raw_library), cinemeta=FakeCinemeta(metas))


def script_prompts(monkeypatch, answers: list[str], passwords: list[str] | None = None):
    inputs = iter(answers)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(inputs))
    pw = iter(passwords or [])
    monkeypatch.setattr(prompts.getpass, "getpass", lambda _prompt="": next(pw))


def test_start_logs_in_syncs_and_exports_everything(app, db, tmp_path, monkeypatch, capsys):
    script_prompts(monkeypatch, ["me@example.com"], ["secret"])
    opts = Options(genres="all", formats="all", outdir=tmp_path)
    assert app.run_start(opts) == 0

    account = db.get_account("me@example.com")
    assert account.auth_key == "good-key" and account.is_synced
    assert db.count_items(account.id) == 7
    assert sorted(p.suffix for p in tmp_path.iterdir()) == [".csv", ".txt", ".xlsx"]
    assert app.cinemeta.requested == [{"tt0111161", "tt0468569", "tt0068646", "tt0137523"}]  # tmdb ids never requested
    out = capsys.readouterr().out
    assert "5 movie(s): 2 watched, 2 in progress, 1 partial" in out


def test_get_watched_uses_database_without_network(app, db, tmp_path, monkeypatch):
    db.upsert_account("me@example.com", "good-key")
    script_prompts(monkeypatch, ["1"])  # choose the only account
    assert app.run_start(Options(genres="all", formats="txt", outdir=tmp_path)) == 0
    assert app.api.fetch_calls == 1

    script_prompts(monkeypatch, ["1", "all", "4"])  # account, genres, txt
    assert app.run_get_watched(Options(outdir=tmp_path)) == 0
    assert app.api.fetch_calls == 1  # served from SQLite
    assert len(app.cinemeta.requested) == 1  # metadata came from the DB cache, no second Cinemeta round


def test_get_watched_offers_sync_for_new_account(app, db, tmp_path, monkeypatch):
    db.upsert_account("me@example.com", "good-key")
    script_prompts(monkeypatch, ["y"])
    assert app.run_get_watched(Options(account="me@example.com", genres="all", formats="csv", outdir=tmp_path)) == 0
    assert app.api.fetch_calls == 1

    db.upsert_account("other@example.com", "good-key")
    script_prompts(monkeypatch, ["n"])
    assert app.run_get_watched(Options(account="other@example.com", outdir=tmp_path)) == 1


def test_expired_key_triggers_relogin(app, db, tmp_path, monkeypatch):
    db.upsert_account("me@example.com", "stale-key")
    script_prompts(monkeypatch, [], ["wrong", "secret"])
    assert app.run_start(Options(account="me@example.com", genres="all", formats="txt", outdir=tmp_path)) == 0
    assert db.get_account("me@example.com").auth_key == "good-key"
    assert [pw for _, pw in app.api.logins] == ["wrong", "secret"]
    assert app.api.fetch_calls == 2


def test_genre_and_library_filters(app, db, tmp_path, monkeypatch, capsys):
    db.upsert_account("me@example.com", "good-key")
    assert app.run_start(Options(account="me@example.com", genres="Action", formats="terminal", outdir=tmp_path)) == 0
    assert "1 movie(s)" in capsys.readouterr().out
    assert app.run_get_watched(Options(account="me@example.com", genres="all", formats="terminal", library_only=True, outdir=tmp_path)) == 0
    assert "1 movie(s): 1 watched" in capsys.readouterr().out


def test_bad_genre_flag_exits_with_available_list(app, db, tmp_path):
    db.upsert_account("me@example.com", "good-key")
    with pytest.raises(SystemExit, match="Available: Action, Crime, Drama, Unknown"):
        app.run_start(Options(account="me@example.com", genres="Western", formats="txt", outdir=tmp_path))


def test_cli_parser_and_dispatch(tmp_path, capsys):
    parser = build_parser()
    args = parser.parse_args(["getWatched", "--genres", "all", "--formats", "csv,txt", "--library-only"])
    assert args.command == "getWatched" and args.run is App.run_get_watched and args.library_only
    assert parser.parse_args(["get-watched"]).run is App.run_get_watched
    assert parser.parse_args(["start"]).run is App.run_start

    assert main([]) == 2
    assert "start" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        main(["start", "--threshold", "5", "--db", str(tmp_path / "x.db")])
