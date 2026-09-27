"""Output writers. Each takes the movies and a target path; the registry maps user-facing keys."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from ..models import WatchedMovie
from .csv_export import write_csv
from .terminal import print_table
from .txt import write_txt
from .xlsx import write_xlsx

Writer = Callable[[Sequence[WatchedMovie], Path | None], None]


@dataclass(frozen=True)
class Format:
    key: str
    label: str
    extension: str | None  # None -> writes to the terminal, no file
    writer: Writer


FORMATS: dict[str, Format] = {
    "terminal": Format("terminal", "Terminal table", None, lambda movies, _path: print_table(movies)),
    "xlsx": Format("xlsx", "Excel spreadsheet (.xlsx)", "xlsx", lambda movies, path: write_xlsx(movies, _required(path))),
    "csv": Format("csv", "CSV file (.csv)", "csv", lambda movies, path: write_csv(movies, _required(path))),
    "txt": Format("txt", "Text file, one movie per line in chronological order (.txt)", "txt", lambda movies, path: write_txt(movies, _required(path))),
}
FORMAT_ORDER: tuple[str, ...] = ("terminal", "xlsx", "csv", "txt")


def _required(path: Path | None) -> Path:
    if path is None:
        raise ValueError("this format needs an output path")
    return path


def parse_formats(raw: str) -> list[str]:
    """'all' or a comma-separated list of format keys -> keys in canonical order."""
    tokens = [t.strip().lower() for t in raw.split(",") if t.strip()]
    if not tokens or "all" in tokens:
        return list(FORMAT_ORDER)
    unknown = [t for t in tokens if t not in FORMATS]
    if unknown:
        raise ValueError(f"unknown format(s): {', '.join(unknown)}. Choose from: {', '.join(FORMAT_ORDER)}, all")
    return [key for key in FORMAT_ORDER if key in tokens]


def default_filename(email: str, extension: str, day: date | None = None) -> str:
    local_part = re.sub(r"[^A-Za-z0-9._-]+", "_", email.split("@", 1)[0]) or "account"
    return f"stremio_watched_{local_part}_{(day or date.today()).isoformat()}.{extension}"


def export(movies: Sequence[WatchedMovie], keys: Iterable[str], outdir: Path, email: str) -> list[Path]:
    """Run each requested writer; returns the files written (terminal output produces none)."""
    written: list[Path] = []
    for key in keys:
        fmt = FORMATS[key]
        path = None
        if fmt.extension is not None:
            outdir.mkdir(parents=True, exist_ok=True)
            path = outdir / default_filename(email, fmt.extension)
        fmt.writer(movies, path)
        if path is not None:
            written.append(path)
    return written


__all__ = [
    "FORMATS",
    "FORMAT_ORDER",
    "Format",
    "default_filename",
    "export",
    "parse_formats",
    "print_table",
    "write_csv",
    "write_txt",
    "write_xlsx",
]
