"""Use cases: `start` (fresh sync) and `getWatched` (from the database). Glue between layers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import prompts
from .api import StremioAPIError, StremioClient
from .cinemeta import CinemetaClient, supports
from .config import LEGACY_ACCOUNTS_FILE, LEGACY_META_FILE, MAX_LOGIN_ATTEMPTS, OUTPUT_DIR, WATCHED_THRESHOLD
from .db import Database
from .exporters import export
from .models import Account, LibraryItem, WatchedMovie, parse_stremio_time
from .watched import attach_meta, extract_watched, filter_by_genres, status_counts


@dataclass(frozen=True)
class Options:
    account: str | None = None  # email to use without asking
    genres: str | None = None  # "all" or comma list; None -> ask
    formats: str | None = None  # "all" or comma list; None -> ask
    outdir: Path = OUTPUT_DIR
    threshold: float = WATCHED_THRESHOLD
    library_only: bool = False


class App:
    def __init__(self, db: Database, api: StremioClient | None = None, cinemeta: CinemetaClient | None = None):
        self.db = db
        self.api = api or StremioClient()
        self.cinemeta = cinemeta or CinemetaClient()
        if db.created:
            self._import_legacy()

    # ------------------------------------------------------------------ commands

    def run_start(self, opts: Options) -> int:
        """Always re-download the library from Stremio, then genres -> output."""
        account = self.select_account(opts.account)
        print("Fetching your Stremio library...")
        items = self.sync(account)
        print(f"Synced {len(items)} library items for {account.email}.")
        return self._report(account, opts)

    def run_get_watched(self, opts: Options) -> int:
        """Serve from the database; only hit Stremio if this account was never synced."""
        account = self.select_account(opts.account)
        if account.is_synced:
            synced = parse_stremio_time(account.last_synced_at)
            when = f"{synced:%Y-%m-%d %H:%M}" if synced else account.last_synced_at
            print(f"Using data synced {when} (run 'start' to refresh from Stremio).")
        else:
            if not prompts.confirm(f"No local data for {account.email}. Fetch from Stremio now?"):
                print("Nothing to do.")
                return 1
            items = self.sync(account)
            print(f"Synced {len(items)} library items for {account.email}.")
        return self._report(account, opts)

    # ------------------------------------------------------------------ accounts / login

    def select_account(self, preselect: str | None) -> Account:
        accounts = self.db.list_accounts()
        if preselect:
            account = self.db.get_account(preselect)
            if account is None:
                print(f"No saved account for {preselect}; logging in.")
                return self.add_account(preselect)
            return account
        if not accounts:
            print("No saved accounts yet. Let's add one.")
            return self.add_account()
        chosen = prompts.choose_account(accounts)
        return chosen if chosen is not None else self.add_account()

    def add_account(self, email: str | None = None) -> Account:
        email, auth_key = self.login_interactively(email)
        return self.db.upsert_account(email, auth_key)

    def login_interactively(self, email: str | None = None) -> tuple[str, str]:
        """Ask for credentials until Stremio accepts them; returns (email, authKey)."""
        for attempt in range(1, MAX_LOGIN_ATTEMPTS + 1):
            email = email or prompts.prompt_nonempty("Stremio email: ")
            password = prompts.prompt_password(email)
            try:
                auth_key = self.api.login(email, password)
            except StremioAPIError as exc:
                print(f"  Login failed: {exc.message}")
                if attempt < MAX_LOGIN_ATTEMPTS:
                    print(f"  ({MAX_LOGIN_ATTEMPTS - attempt} attempt(s) left)")
                continue
            print(f"Logged in as {email}.")
            return email, auth_key
        raise SystemExit("Too many failed login attempts.")

    # ------------------------------------------------------------------ sync

    def sync(self, account: Account) -> list[LibraryItem]:
        """Download the library (re-logging in if the key expired) and replace the DB snapshot."""
        try:
            raw_items = self.api.fetch_library(account.auth_key)
        except StremioAPIError as exc:
            if not exc.is_auth_error:
                raise
            print(f"Session expired for {account.email} ({exc.message}). Please log in again.")
            _, auth_key = self.login_interactively(account.email)
            account = self.db.upsert_account(account.email, auth_key)
            raw_items = self.api.fetch_library(account.auth_key)
        items = [LibraryItem.from_api(raw) for raw in raw_items]
        self.db.replace_library(account.id, items)
        return items

    def ensure_meta(self, movies: list[WatchedMovie]) -> list[WatchedMovie]:
        """Attach cached Cinemeta metadata, fetching (and caching) whatever is missing."""
        ids = {movie.item_id for movie in movies}
        known = self.db.get_meta(ids)
        # Only ids Cinemeta can serve; misses are not cached so a flaky fetch is retried next run.
        missing = {item_id for item_id in ids - known.keys() if supports(item_id)}
        if missing:
            fetched = self.cinemeta.fetch_many(missing, progress=_progress_line("Fetching metadata from Cinemeta"))
            print()
            if fetched:
                self.db.upsert_meta(fetched.values())
                known.update(fetched)
        return attach_meta(movies, known)

    # ------------------------------------------------------------------ reporting

    def _report(self, account: Account, opts: Options) -> int:
        items = self.db.get_items(account.id, type_="movie")
        movies = extract_watched(items, threshold=opts.threshold, library_only=opts.library_only)
        if not movies:
            print(f"No movies with playback history found ({len(items)} movies in the library snapshot).")
            return 0
        print(f"Found {len(movies)} movie(s) with playback history out of {len(items)} movies.")

        movies = self.ensure_meta(movies)
        selected = prompts.choose_genres(movies, opts.genres)
        chosen = filter_by_genres(movies, selected)
        if not chosen:
            print("No movies match the selected genres.")
            return 0

        formats = prompts.choose_formats(opts.formats)
        written = export(chosen, formats, opts.outdir, account.email)

        counts = status_counts(chosen)
        summary = ", ".join(f"{n} {status.value.lower()}" for status, n in counts.items())
        print(f"\n{len(chosen)} movie(s): {summary}.")
        for path in written:
            print(f"  -> {path}")
        return 0

    # ------------------------------------------------------------------ misc

    def _import_legacy(self) -> None:
        accounts, metas = self.db.import_legacy(LEGACY_ACCOUNTS_FILE, LEGACY_META_FILE)
        if accounts or metas:
            print(f"Imported {accounts} account(s) and {metas} cached metadata row(s) from the previous version.")


def _progress_line(label: str):
    def show(done: int, total: int) -> None:
        print(f"\r{label}... {done}/{total}", end="", flush=True)

    return show
