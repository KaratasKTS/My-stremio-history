"""Pure domain logic: classify library items, attach metadata, genre selection, sorting.

No I/O here - everything takes and returns plain values so it is trivially testable.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from datetime import datetime

from .config import UNKNOWN_GENRE, WATCHED_THRESHOLD
from .models import LibraryItem, MovieMeta, Status, WatchedMovie, parse_stremio_time


def classify(item: LibraryItem, threshold: float = WATCHED_THRESHOLD) -> WatchedMovie | None:
    """Turn a library item into a WatchedMovie, or None if it is not a movie with playback."""
    if not item.is_movie or not item.has_playback:
        return None

    duration = item.duration
    watched_ratio = min(item.time_watched / duration, 1.0) if duration > 0 else 0.0
    position_ratio = min(item.time_offset / duration, 1.0) if duration > 0 else 0.0
    flagged_by_stremio = item.flagged_watched > 0 or item.times_watched > 0
    watched = flagged_by_stremio or max(watched_ratio, position_ratio) >= threshold

    if watched:
        status = Status.WATCHED
        progress = watched_ratio or 1.0  # marked watched manually / no time recorded
    elif item.time_offset > 0:
        status = Status.IN_PROGRESS
        progress = watched_ratio
    else:
        status = Status.PARTIAL
        progress = watched_ratio

    return WatchedMovie(
        item_id=item.item_id,
        title=item.name,
        status=status,
        progress=progress,
        time_watched_ms=item.time_watched,
        position_ms=item.time_offset,
        duration_ms=duration,
        times_watched=max(item.times_watched, 1 if watched else 0),
        last_watched=parse_stremio_time(item.last_watched) or parse_stremio_time(item.mtime),
        in_library=not item.removed,
    )


def extract_watched(
    items: Iterable[LibraryItem],
    threshold: float = WATCHED_THRESHOLD,
    library_only: bool = False,
) -> list[WatchedMovie]:
    movies = []
    for item in items:
        if library_only and item.removed:
            continue
        movie = classify(item, threshold)
        if movie is not None:
            movies.append(movie)
    return movies


def attach_meta(movies: Iterable[WatchedMovie], meta: Mapping[str, MovieMeta]) -> list[WatchedMovie]:
    return [movie.with_meta(meta[movie.item_id]) if movie.item_id in meta else movie for movie in movies]


# ---------------------------------------------------------------- genres


def genre_counts(movies: Iterable[WatchedMovie]) -> list[tuple[str, int]]:
    """Alphabetical (genre, count) pairs, with the Unknown bucket last."""
    counts = Counter(genre for movie in movies for genre in movie.genres)
    named = sorted((g, c) for g, c in counts.items() if g != UNKNOWN_GENRE)
    if UNKNOWN_GENRE in counts:
        named.append((UNKNOWN_GENRE, counts[UNKNOWN_GENRE]))
    return named


def parse_genre_selection(raw: str, genres: list[tuple[str, int]]) -> set[str] | None:
    """Comma-separated menu numbers and/or names -> set of genres; None means "all"."""
    tokens = [t.strip() for t in raw.split(",") if t.strip()]
    if not tokens or any(t.lower() == "all" or t == "0" for t in tokens):
        return None
    by_lower = {g.lower(): g for g, _ in genres}
    selected: set[str] = set()
    for token in tokens:
        if token.isdigit() and 1 <= int(token) <= len(genres):
            selected.add(genres[int(token) - 1][0])
        elif token.lower() in by_lower:
            selected.add(by_lower[token.lower()])
        else:
            raise ValueError(f"unknown genre: {token!r}")
    return selected


def filter_by_genres(movies: Iterable[WatchedMovie], selected: set[str] | None) -> list[WatchedMovie]:
    if selected is None:
        return list(movies)
    return [movie for movie in movies if selected.intersection(movie.genres)]


# ---------------------------------------------------------------- ordering / summary


def sort_newest_first(movies: Iterable[WatchedMovie]) -> list[WatchedMovie]:
    return sorted(movies, key=lambda m: m.last_watched or datetime.min, reverse=True)


def sort_chronological(movies: Iterable[WatchedMovie]) -> list[WatchedMovie]:
    """Oldest first; movies with no known date go last."""
    return sorted(movies, key=lambda m: m.last_watched or datetime.max)


def status_counts(movies: Iterable[WatchedMovie]) -> dict[Status, int]:
    counts = Counter(movie.status for movie in movies)
    return {status: counts.get(status, 0) for status in Status}
