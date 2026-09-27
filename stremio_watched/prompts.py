"""Every interactive terminal prompt lives here (the only module calling input()/getpass())."""

from __future__ import annotations

import getpass
from collections.abc import Sequence

from .exporters import FORMAT_ORDER, FORMATS, parse_formats
from .models import Account, WatchedMovie, parse_stremio_time
from .watched import genre_counts, parse_genre_selection


def prompt_choice(prompt: str, count: int, allow_zero: bool = False) -> int:
    """Read one menu number in [1, count] (or [0, count] when allow_zero)."""
    low = 0 if allow_zero else 1
    while True:
        raw = input(prompt).strip()
        if raw.isdigit() and low <= int(raw) <= count:
            return int(raw)
        print(f"  Please enter a number between {low} and {count}.")


def prompt_nonempty(prompt: str) -> str:
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("  This cannot be empty.")


def prompt_password(email: str) -> str:
    while True:
        password = getpass.getpass(f"Password for {email}: ")
        if password:
            return password
        print("  Password cannot be empty.")


def confirm(question: str, default: bool = True) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    raw = input(f"{question} {suffix} ").strip().lower()
    if not raw:
        return default
    return raw in ("y", "yes")


def choose_account(accounts: Sequence[Account]) -> Account | None:
    """Menu of saved accounts plus "Add new account"; returns None when the user wants to add one."""
    print("\nChoose an account:")
    for i, account in enumerate(accounts, 1):
        synced = parse_stremio_time(account.last_synced_at)
        note = f"synced {synced:%Y-%m-%d %H:%M}" if synced else "not synced yet"
        print(f"  [{i}] {account.email}  ({note})")
    print(f"  [{len(accounts) + 1}] Add new account")
    choice = prompt_choice("> ", len(accounts) + 1)
    return accounts[choice - 1] if choice <= len(accounts) else None


def choose_genres(movies: Sequence[WatchedMovie], preselect: str | None = None) -> set[str] | None:
    """Return the selected genres, or None for all. `preselect` skips the menu (e.g. --genres)."""
    genres = genre_counts(movies)
    if preselect is not None:
        try:
            return parse_genre_selection(preselect, genres)
        except ValueError as exc:
            raise SystemExit(f"--genres: {exc}. Available: {', '.join(g for g, _ in genres)}") from exc

    print("\nChoose genres (comma-separated numbers or names, 'all' or 0 for everything):")
    print(f"  [0] All ({len(movies)})")
    for i, (genre, count) in enumerate(genres, 1):
        print(f"  [{i}] {genre} ({count})")
    while True:
        try:
            return parse_genre_selection(input("> "), genres)
        except ValueError as exc:
            print(f"  {exc}")


def choose_formats(preselect: str | None = None) -> list[str]:
    """Return output format keys in canonical order. `preselect` skips the menu (e.g. --formats)."""
    if preselect is not None:
        try:
            return parse_formats(preselect)
        except ValueError as exc:
            raise SystemExit(f"--formats: {exc}") from exc

    print("\nChoose output (comma-separated numbers, or 'all'):")
    for i, key in enumerate(FORMAT_ORDER, 1):
        print(f"  [{i}] {FORMATS[key].label}")
    print(f"  [{len(FORMAT_ORDER) + 1}] All of the above")
    while True:
        raw = input("> ").strip()
        tokens = [t.strip() for t in raw.split(",") if t.strip()]
        if tokens and all(t.isdigit() and 1 <= int(t) <= len(FORMAT_ORDER) + 1 for t in tokens):
            if any(int(t) == len(FORMAT_ORDER) + 1 for t in tokens):
                return list(FORMAT_ORDER)
            chosen = {FORMAT_ORDER[int(t) - 1] for t in tokens}
            return [key for key in FORMAT_ORDER if key in chosen]
        try:
            return parse_formats(raw)
        except ValueError as exc:
            print(f"  {exc}")
