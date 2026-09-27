"""CSV with the same columns as the spreadsheet, newest first."""

from __future__ import annotations

import csv
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from ..models import WatchedMovie
from ..watched import sort_newest_first
from .columns import HEADERS, column_index, row_values


def _cell(value: Any, col: int, progress_col: int) -> Any:
    if col == progress_col and isinstance(value, float):
        return f"{value:.0%}"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    return "" if value is None else value


def write_csv(movies: Sequence[WatchedMovie], path: Path) -> None:
    progress_col = column_index("Watched %")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(HEADERS)
        for movie in sort_newest_first(movies):
            writer.writerow(_cell(value, col, progress_col) for col, value in enumerate(row_values(movie), 1))
