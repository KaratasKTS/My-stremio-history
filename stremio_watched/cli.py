"""Command-line parsing and dispatch. Nothing else."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .api import StremioAPIError
from .config import DB_PATH, OUTPUT_DIR, WATCHED_THRESHOLD
from .db import Database
from .exporters import FORMAT_ORDER
from .workflows import App, Options

DESCRIPTION = """Export the movies you have watched (fully or partially) in Stremio.

commands:
  start        log in / pick an account, download the library fresh from Stremio into the
               local database, then choose genres and output formats
  getWatched   pick an account and work from the local database (no download unless the
               account was never synced), then choose genres and output formats
"""


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--account", metavar="EMAIL", help="use this account without asking")
    parser.add_argument("--genres", metavar="LIST", help="comma-separated genres, or 'all' (skips the menu)")
    parser.add_argument(
        "--formats",
        metavar="LIST",
        help=f"comma-separated output formats ({', '.join(FORMAT_ORDER)}) or 'all' (skips the menu)",
    )
    parser.add_argument("--outdir", type=Path, default=OUTPUT_DIR, help=f"where files are written (default: {OUTPUT_DIR})")
    parser.add_argument("--db", type=Path, default=DB_PATH, help=f"SQLite database path (default: {DB_PATH})")
    parser.add_argument(
        "--threshold",
        type=float,
        default=WATCHED_THRESHOLD,
        help=f"fraction of the runtime watched that counts as fully watched (default {WATCHED_THRESHOLD}, same as Stremio)",
    )
    parser.add_argument(
        "--library-only",
        action="store_true",
        help="only movies currently in your Stremio Library (default: every movie you played)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="stremio_fetch_watched.py",
        description=DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    start = subparsers.add_parser("start", help="fresh download from Stremio, then export")
    _add_common(start)
    start.set_defaults(run=App.run_start)

    get_watched = subparsers.add_parser(
        "getWatched", aliases=["get-watched", "getwatched"], help="export from the local database"
    )
    _add_common(get_watched)
    get_watched.set_defaults(run=App.run_get_watched)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 2
    if not 0 < args.threshold <= 1:
        parser.error("--threshold must be between 0 and 1")

    opts = Options(
        account=args.account,
        genres=args.genres,
        formats=args.formats,
        outdir=args.outdir,
        threshold=args.threshold,
        library_only=args.library_only,
    )
    try:
        with Database(args.db) as db:
            return args.run(App(db), opts)
    except KeyboardInterrupt:
        print("\nAborted.")
        return 130
    except StremioAPIError as exc:
        print(f"Error: {exc.message}", file=sys.stderr)
        return 1
