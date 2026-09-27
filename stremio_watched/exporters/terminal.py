"""Fixed-width table on stdout, newest first."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from typing import TextIO

from ..models import WatchedMovie
from ..watched import sort_newest_first

_HEADERS = ("#", "Title", "Year", "Genres", "Status", "Watched", "Last watched", "Library")
_MAX_WIDTHS = (5, 40, 4, 28, 11, 7, 16, 7)


def _clip(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 1] + "…"


def _row(index: int, movie: WatchedMovie) -> tuple[str, ...]:
    return (
        str(index),
        movie.title,
        movie.year,
        ", ".join(movie.genres),
        movie.status.value,
        f"{movie.progress:.0%}",
        movie.last_watched.strftime("%Y-%m-%d %H:%M") if movie.last_watched else "",
        "Yes" if movie.in_library else "No",
    )


def print_table(movies: Sequence[WatchedMovie], stream: TextIO | None = None) -> None:
    stream = stream or sys.stdout
    rows = [_row(i, movie) for i, movie in enumerate(sort_newest_first(movies), 1)]
    widths = [
        min(max(len(header), *(len(row[c]) for row in rows)) if rows else len(header), _MAX_WIDTHS[c])
        for c, header in enumerate(_HEADERS)
    ]
    header_line = "  ".join(h.ljust(w) for h, w in zip(_HEADERS, widths))
    print("", file=stream)
    print(header_line, file=stream)
    print("-" * len(header_line), file=stream)
    for row in rows:
        print("  ".join(_clip(value, w).ljust(w) for value, w in zip(row, widths)), file=stream)
