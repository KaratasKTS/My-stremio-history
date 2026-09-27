"""The one definition of the tabular layout shared by the spreadsheet-like exporters."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..models import WatchedMovie, ms_to_hms


@dataclass(frozen=True)
class Column:
    header: str
    width: int  # spreadsheet column width
    value: Callable[[WatchedMovie], Any]


COLUMNS: tuple[Column, ...] = (
    Column("Title", 40, lambda m: m.title),
    Column("Year", 8, lambda m: m.year),
    Column("Genres", 28, lambda m: ", ".join(m.genres)),
    Column("Status", 12, lambda m: m.status.value),
    Column("Watched %", 11, lambda m: m.progress),
    Column("Time watched", 13, lambda m: ms_to_hms(m.time_watched_ms)),
    Column("Position", 10, lambda m: ms_to_hms(m.position_ms)),
    Column("Duration", 10, lambda m: ms_to_hms(m.duration_ms)),
    Column("Times watched", 14, lambda m: m.times_watched),
    Column("Last watched", 18, lambda m: m.last_watched),
    Column("In library", 11, lambda m: "Yes" if m.in_library else "No"),
    Column("IMDb rating", 12, lambda m: m.imdb_rating),
    Column("Runtime", 10, lambda m: m.runtime),
    Column("Director", 24, lambda m: m.director),
    Column("IMDb ID", 12, lambda m: m.item_id),
    Column("IMDb URL", 34, lambda m: m.imdb_url),
)

HEADERS: tuple[str, ...] = tuple(column.header for column in COLUMNS)


def column_index(header: str) -> int:
    """1-based position of a column, for cell formatting."""
    return HEADERS.index(header) + 1


def row_values(movie: WatchedMovie) -> list[Any]:
    return [column.value(movie) for column in COLUMNS]
