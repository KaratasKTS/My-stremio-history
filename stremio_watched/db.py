"""SQLite persistence: accounts, per-account library snapshot, shared metadata cache.

The only module that contains SQL. Watch status is *not* stored - it is derived in `watched.py`
from the raw counters so that `--threshold` can be changed without re-syncing.
"""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from types import TracebackType
from typing import Any

from .models import Account, LibraryItem, MovieMeta

SCHEMA_VERSION = 1
_SQLITE_MAX_PARAMS = 900  # stay under SQLite's classic 999 host-parameter limit

_SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id             INTEGER PRIMARY KEY,
    email          TEXT NOT NULL UNIQUE COLLATE NOCASE,
    auth_key       TEXT NOT NULL,
    added_at       TEXT NOT NULL,
    last_synced_at TEXT
);
CREATE TABLE IF NOT EXISTS library_items (
    account_id           INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    item_id              TEXT NOT NULL,
    type                 TEXT NOT NULL,
    name                 TEXT NOT NULL,
    removed              INTEGER NOT NULL,
    temp                 INTEGER NOT NULL,
    ctime                TEXT,
    mtime                TEXT,
    last_watched         TEXT,
    time_watched         INTEGER NOT NULL,
    time_offset          INTEGER NOT NULL,
    overall_time_watched INTEGER NOT NULL,
    times_watched        INTEGER NOT NULL,
    flagged_watched      INTEGER NOT NULL,
    duration             INTEGER NOT NULL,
    video_id             TEXT,
    raw_json             TEXT NOT NULL,
    synced_at            TEXT NOT NULL,
    PRIMARY KEY (account_id, item_id)
);
CREATE INDEX IF NOT EXISTS idx_library_items_type ON library_items(account_id, type);
CREATE TABLE IF NOT EXISTS meta (
    item_id     TEXT PRIMARY KEY,
    name        TEXT,
    year        TEXT,
    genres      TEXT NOT NULL,
    imdb_rating TEXT,
    runtime     TEXT,
    director    TEXT,
    raw_json    TEXT NOT NULL,
    fetched_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);
"""

_INSERT_ITEM = """
INSERT INTO library_items (
    account_id, item_id, type, name, removed, temp, ctime, mtime, last_watched, time_watched,
    time_offset, overall_time_watched, times_watched, flagged_watched, duration, video_id,
    raw_json, synced_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_UPSERT_META = """
INSERT INTO meta (item_id, name, year, genres, imdb_rating, runtime, director, raw_json, fetched_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(item_id) DO UPDATE SET
    name = excluded.name, year = excluded.year, genres = excluded.genres,
    imdb_rating = excluded.imdb_rating, runtime = excluded.runtime, director = excluded.director,
    raw_json = excluded.raw_json, fetched_at = excluded.fetched_at
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _chunks(values: list[Any], size: int) -> Iterable[list[Any]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


class Database:
    """Thin repository over one SQLite file (or ':memory:' for tests)."""

    def __init__(self, path: Path | str):
        self.path = Path(path) if str(path) != ":memory:" else None
        self.created = False
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.created = not self.path.exists()
        self._conn = sqlite3.connect(str(path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        if self.path is not None:
            self._conn.execute("PRAGMA journal_mode = WAL")
            if self.created:
                os.chmod(self.path, 0o600)  # holds account auth keys
        self._init_schema()

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.executescript(_SCHEMA)
            if self._conn.execute("SELECT version FROM schema_version").fetchone() is None:
                self._conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Database:
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None) -> None:
        self.close()

    # ------------------------------------------------------------------ accounts

    @staticmethod
    def _account(row: sqlite3.Row) -> Account:
        return Account(
            id=row["id"],
            email=row["email"],
            auth_key=row["auth_key"],
            added_at=row["added_at"],
            last_synced_at=row["last_synced_at"],
        )

    def list_accounts(self) -> list[Account]:
        rows = self._conn.execute("SELECT * FROM accounts ORDER BY added_at, id").fetchall()
        return [self._account(row) for row in rows]

    def get_account(self, email: str) -> Account | None:
        row = self._conn.execute("SELECT * FROM accounts WHERE email = ? COLLATE NOCASE", (email,)).fetchone()
        return self._account(row) if row else None

    def upsert_account(self, email: str, auth_key: str) -> Account:
        """Insert, or refresh the auth key of an existing account (email compared case-insensitively)."""
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO accounts (email, auth_key, added_at) VALUES (?, ?, ?)
                ON CONFLICT(email) DO UPDATE SET auth_key = excluded.auth_key
                """,
                (email, auth_key, now_iso()),
            )
        account = self.get_account(email)
        assert account is not None
        return account

    # ------------------------------------------------------------------ library snapshot

    def replace_library(self, account_id: int, items: Iterable[LibraryItem]) -> int:
        """Atomically replace the account's snapshot and stamp `last_synced_at`."""
        synced_at = now_iso()
        rows = [
            (
                account_id, item.item_id, item.type, item.name, int(item.removed), int(item.temp),
                item.ctime, item.mtime, item.last_watched, item.time_watched, item.time_offset,
                item.overall_time_watched, item.times_watched, item.flagged_watched, item.duration,
                item.video_id, json.dumps(item.raw, separators=(",", ":")), synced_at,
            )
            for item in items
        ]
        with self._conn:
            self._conn.execute("DELETE FROM library_items WHERE account_id = ?", (account_id,))
            self._conn.executemany(_INSERT_ITEM, rows)
            self._conn.execute("UPDATE accounts SET last_synced_at = ? WHERE id = ?", (synced_at, account_id))
        return len(rows)

    @staticmethod
    def _item(row: sqlite3.Row) -> LibraryItem:
        return LibraryItem(
            item_id=row["item_id"],
            type=row["type"],
            name=row["name"],
            removed=bool(row["removed"]),
            temp=bool(row["temp"]),
            ctime=row["ctime"],
            mtime=row["mtime"],
            last_watched=row["last_watched"],
            time_watched=row["time_watched"],
            time_offset=row["time_offset"],
            overall_time_watched=row["overall_time_watched"],
            times_watched=row["times_watched"],
            flagged_watched=row["flagged_watched"],
            duration=row["duration"],
            video_id=row["video_id"],
            raw=json.loads(row["raw_json"]),
        )

    def get_items(self, account_id: int, type_: str | None = None) -> list[LibraryItem]:
        sql = "SELECT * FROM library_items WHERE account_id = ?"
        params: tuple[Any, ...] = (account_id,)
        if type_ is not None:
            sql += " AND type = ?"
            params += (type_,)
        return [self._item(row) for row in self._conn.execute(sql, params)]

    def count_items(self, account_id: int, type_: str | None = None) -> int:
        sql = "SELECT COUNT(*) FROM library_items WHERE account_id = ?"
        params: tuple[Any, ...] = (account_id,)
        if type_ is not None:
            sql += " AND type = ?"
            params += (type_,)
        return int(self._conn.execute(sql, params).fetchone()[0])

    # ------------------------------------------------------------------ metadata cache

    @staticmethod
    def _meta(row: sqlite3.Row) -> MovieMeta:
        return MovieMeta(
            item_id=row["item_id"],
            name=row["name"] or "",
            year=row["year"] or "",
            genres=tuple(json.loads(row["genres"])),
            imdb_rating=row["imdb_rating"] or "",
            runtime=row["runtime"] or "",
            director=row["director"] or "",
            raw=json.loads(row["raw_json"]),
        )

    def get_meta(self, ids: Iterable[str]) -> dict[str, MovieMeta]:
        found: dict[str, MovieMeta] = {}
        for chunk in _chunks(sorted(set(ids)), _SQLITE_MAX_PARAMS):
            placeholders = ",".join("?" * len(chunk))
            for row in self._conn.execute(f"SELECT * FROM meta WHERE item_id IN ({placeholders})", chunk):
                found[row["item_id"]] = self._meta(row)
        return found

    def upsert_meta(self, metas: Iterable[MovieMeta]) -> int:
        fetched_at = now_iso()
        rows = [
            (
                meta.item_id, meta.name, meta.year, json.dumps(list(meta.genres)), meta.imdb_rating,
                meta.runtime, meta.director, json.dumps(meta.raw, separators=(",", ":")), fetched_at,
            )
            for meta in metas
        ]
        with self._conn:
            self._conn.executemany(_UPSERT_META, rows)
        return len(rows)

    # ------------------------------------------------------------------ v1 import

    def import_legacy(self, accounts_file: Path, meta_file: Path) -> tuple[int, int]:
        """Import the JSON files written by v1 of this tool. Returns (accounts, metadata rows)."""
        accounts = 0
        for entry in _read_json(accounts_file).get("accounts", []):
            if entry.get("email") and entry.get("authKey"):
                self.upsert_account(entry["email"], entry["authKey"])
                accounts += 1
        legacy_meta = _read_json(meta_file)
        metas = [MovieMeta.from_cinemeta(item_id, raw) for item_id, raw in legacy_meta.items() if isinstance(raw, dict)]
        return accounts, self.upsert_meta(metas)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}
