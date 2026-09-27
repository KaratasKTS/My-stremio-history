"""Plain text, one movie per line, oldest first."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from ..models import WatchedMovie
from ..watched import sort_chronological


def format_line(movie: WatchedMovie) -> str:
    when = movie.last_watched.strftime("%Y-%m-%d %H:%M") if movie.last_watched else "unknown date   "
    title = f"{movie.title} ({movie.year})" if movie.year else movie.title
    return f"{when} | {title} | {movie.status.value} {movie.progress:.0%}"


def write_txt(movies: Sequence[WatchedMovie], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [format_line(movie) for movie in sort_chronological(movies)]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
