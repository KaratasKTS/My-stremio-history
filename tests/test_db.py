import json
import stat

import pytest

from stremio_watched.db import Database
from stremio_watched.models import MovieMeta


@pytest.fixture
def db():
    with Database(":memory:") as database:
        yield database


def test_new_file_is_private_and_flagged_created(tmp_path):
    path = tmp_path / "nested" / "stremio.db"
    with Database(path) as db:
        assert db.created
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    with Database(path) as db:
        assert not db.created


def test_upsert_account_is_case_insensitive_and_keeps_added_at(db):
    first = db.upsert_account("Someone@Example.com", "key-1")
    second = db.upsert_account("someone@example.com", "key-2")
    assert first.id == second.id
    assert second.auth_key == "key-2"
    assert second.added_at == first.added_at
    assert not second.is_synced
    assert db.get_account("SOMEONE@example.com") == second
    assert db.get_account("nobody@example.com") is None
    assert [a.email for a in db.list_accounts()] == ["Someone@Example.com"]


def test_replace_library_is_a_full_snapshot(db, items):
    account = db.upsert_account("a@b.c", "k")
    assert db.replace_library(account.id, items) == len(items)
    assert db.count_items(account.id) == len(items)
    assert db.count_items(account.id, "movie") == 6
    assert db.get_account("a@b.c").is_synced

    movies = db.get_items(account.id, type_="movie")
    assert {m.item_id for m in movies} == {i.item_id for i in items if i.is_movie}
    restored = next(m for m in movies if m.item_id == "tt0111161")
    original = next(i for i in items if i.item_id == "tt0111161")
    assert restored == original  # raw is excluded from equality, everything else round-trips
    assert restored.raw == original.raw

    # A second sync with fewer items replaces, not appends.
    db.replace_library(account.id, items[:2])
    assert db.count_items(account.id) == 2


def test_other_accounts_are_untouched(db, items):
    one = db.upsert_account("one@x.y", "k1")
    two = db.upsert_account("two@x.y", "k2")
    db.replace_library(one.id, items)
    db.replace_library(two.id, items[:1])
    db.replace_library(one.id, [])
    assert db.count_items(one.id) == 0
    assert db.count_items(two.id) == 1


def test_meta_cache_roundtrip_and_chunked_lookup(db):
    metas = [MovieMeta(item_id=f"tt{n:07d}", name=f"Movie {n}", genres=("Drama", "Crime"), year="2000") for n in range(1500)]
    assert db.upsert_meta(metas) == 1500
    found = db.get_meta(m.item_id for m in metas)
    assert len(found) == 1500
    assert found["tt0000007"].genres == ("Drama", "Crime")
    assert found["tt0000007"].name == "Movie 7"

    db.upsert_meta([MovieMeta(item_id="tt0000007", name="Renamed", genres=())])
    assert db.get_meta(["tt0000007", "missing"])["tt0000007"].name == "Renamed"
    assert db.get_meta([]) == {}


def test_import_legacy_files(db, tmp_path):
    accounts_file = tmp_path / "accounts.json"
    accounts_file.write_text(json.dumps({"accounts": [
        {"email": "old@user.tld", "authKey": "legacy-key", "added": "2026-09-26"},
        {"email": "broken@user.tld"},  # no key -> skipped
    ]}))
    meta_file = tmp_path / "meta.json"
    meta_file.write_text(json.dumps({"tt0111161": {"name": "Shawshank", "genres": ["Drama"], "year": "1994"}}))

    assert db.import_legacy(accounts_file, meta_file) == (1, 1)
    assert db.get_account("old@user.tld").auth_key == "legacy-key"
    assert db.get_meta(["tt0111161"])["tt0111161"].year == "1994"

    # Missing files are not an error.
    assert db.import_legacy(tmp_path / "nope.json", tmp_path / "nope2.json") == (0, 0)
