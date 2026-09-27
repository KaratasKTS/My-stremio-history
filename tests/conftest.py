"""Shared fixtures: a small fake Stremio library covering every classification path."""

from __future__ import annotations

import pytest

from stremio_watched.models import LibraryItem, MovieMeta

HOUR = 3_600_000  # ms


def _item(_id: str, name: str, *, type_: str = "movie", removed: bool, temp: bool, last_watched: str, **state):
    base = {"timeWatched": 0, "timeOffset": 0, "overallTimeWatched": 0, "timesWatched": 0, "flaggedWatched": 0, "duration": 0}
    base.update(state)
    return {
        "_id": _id,
        "name": name,
        "type": type_,
        "removed": removed,
        "temp": temp,
        "_ctime": "2024-01-01T00:00:00.000Z",
        "_mtime": last_watched,
        "state": {"lastWatched": last_watched, "video_id": _id, **base},
    }


RAW_LIBRARY = [
    # Finished, never added to the library: Stremio flagged it and reset the resume position.
    _item("tt0111161", "Finished not in library", removed=True, temp=True, last_watched="2026-09-20T21:30:00.000Z",
          timeWatched=int(2.2 * HOUR), timeOffset=0, duration=int(2.37 * HOUR), timesWatched=1, flaggedWatched=1),
    # Stopped in the middle, still in Continue Watching.
    _item("tt0468569", "Resume point", removed=True, temp=True, last_watched="2026-09-10T20:00:00.000Z",
          timeWatched=int(0.8 * HOUR), timeOffset=int(0.83 * HOUR), duration=int(2.53 * HOUR)),
    # Watched a bit, then removed from the library (no resume position).
    _item("tt0068646", "Partial removed", removed=True, temp=False, last_watched="2026-08-01T20:00:00.000Z",
          timeWatched=int(0.42 * HOUR), timeOffset=0, duration=int(2.9 * HOUR)),
    # In the library, opened in the player but never played a second.
    _item("tt0110912", "Opened only", removed=False, temp=False, last_watched="2026-08-01T20:00:00.000Z"),
    # In the library, marked watched by hand (no time recorded).
    _item("tt0137523", "Manually marked", removed=False, temp=False, last_watched="2026-08-02T20:00:00.000Z",
          timesWatched=1),
    # A series with progress must be ignored.
    _item("tt0903747", "Series", type_="series", removed=True, temp=True, last_watched="2026-09-01T00:00:00.000Z",
          timeWatched=HOUR, timeOffset=HOUR, duration=2 * HOUR),
    # Non-IMDb id: no metadata available.
    _item("tmdb:123", "No imdb id", removed=True, temp=True, last_watched="2026-07-01T00:00:00.000Z",
          timeWatched=HOUR, timeOffset=HOUR, duration=2 * HOUR),
]


@pytest.fixture
def raw_library() -> list[dict]:
    return [dict(item) for item in RAW_LIBRARY]


@pytest.fixture
def items(raw_library) -> list[LibraryItem]:
    return [LibraryItem.from_api(raw) for raw in raw_library]


@pytest.fixture
def metas() -> dict[str, MovieMeta]:
    return {
        "tt0111161": MovieMeta.from_cinemeta("tt0111161", {"name": "The Shawshank Redemption", "year": "1994", "genres": ["Drama"],
                                                           "imdbRating": "9.3", "runtime": "142 min", "director": ["Frank Darabont"]}),
        "tt0468569": MovieMeta.from_cinemeta("tt0468569", {"name": "The Dark Knight", "year": "2008", "genre": ["Action", "Crime", "Drama"]}),
        "tt0068646": MovieMeta.from_cinemeta("tt0068646", {"name": "The Godfather", "year": "1972", "genres": "Crime"}),
        "tt0137523": MovieMeta.from_cinemeta("tt0137523", {"name": "Fight Club", "year": "1999", "genres": ["Drama"]}),
    }
