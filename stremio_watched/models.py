"""Data classes shared by every layer, plus the small parsing helpers they need."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import Enum
from typing import Any

from .config import UNKNOWN_GENRE


class Status(str, Enum):
    WATCHED = "Watched"  # Stremio's own flag, or watched fraction >= threshold
    IN_PROGRESS = "In progress"  # has a resume position (appears in Continue Watching)
    PARTIAL = "Partial"  # some time watched, but no resume position (dropped / rewound / dismissed)


def as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def parse_stremio_time(value: Any) -> datetime | None:
    """ISO-8601 with 'Z' -> naive *local* datetime (what spreadsheets display best)."""
    if not value or not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone().replace(tzinfo=None)
    return parsed


def ms_to_hms(ms: int) -> str:
    if ms <= 0:
        return ""
    hours, remainder = divmod(ms // 1000, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:d}:{minutes:02d}:{seconds:02d}"


@dataclass(frozen=True)
class Account:
    id: int
    email: str
    auth_key: str = field(repr=False)
    added_at: str
    last_synced_at: str | None = None

    @property
    def is_synced(self) -> bool:
        return self.last_synced_at is not None


@dataclass(frozen=True)
class LibraryItem:
    """One entry of Stremio's `libraryItem` collection, flattened.

    `removed` is true for every title played without being added to the Library - it does NOT
    mean deleted. Times are milliseconds.
    """

    item_id: str
    type: str
    name: str
    removed: bool
    temp: bool
    ctime: str | None
    mtime: str | None
    last_watched: str | None
    time_watched: int
    time_offset: int
    overall_time_watched: int
    times_watched: int
    flagged_watched: int
    duration: int
    video_id: str | None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_api(cls, item: dict[str, Any]) -> LibraryItem:
        state = item.get("state") or {}
        return cls(
            item_id=str(item.get("_id", "")),
            type=str(item.get("type", "")),
            name=str(item.get("name", "")),
            removed=bool(item.get("removed")),
            temp=bool(item.get("temp")),
            ctime=item.get("_ctime"),
            mtime=item.get("_mtime"),
            last_watched=state.get("lastWatched"),
            time_watched=as_int(state.get("timeWatched")),
            time_offset=as_int(state.get("timeOffset")),
            overall_time_watched=as_int(state.get("overallTimeWatched")),
            times_watched=as_int(state.get("timesWatched")),
            flagged_watched=as_int(state.get("flaggedWatched")),
            duration=as_int(state.get("duration")),
            video_id=state.get("video_id") or state.get("videoId"),
            raw=item,
        )

    @property
    def has_playback(self) -> bool:
        """False for titles opened in the player where nothing was ever played."""
        return bool(self.time_watched or self.time_offset or self.times_watched or self.flagged_watched)

    @property
    def is_movie(self) -> bool:
        return self.type == "movie"


@dataclass(frozen=True)
class MovieMeta:
    """Cinemeta metadata for one IMDb id."""

    item_id: str
    name: str = ""
    year: str = ""
    genres: tuple[str, ...] = ()
    imdb_rating: str = ""
    runtime: str = ""
    director: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_cinemeta(cls, item_id: str, meta: dict[str, Any]) -> MovieMeta:
        genres = meta.get("genres") or meta.get("genre") or []
        if isinstance(genres, str):
            genres = [genres]
        director = meta.get("director") or []
        return cls(
            item_id=item_id,
            name=str(meta.get("name") or ""),
            year=str(meta.get("year") or meta.get("releaseInfo") or ""),
            genres=tuple(g.strip() for g in genres if isinstance(g, str) and g.strip()),
            imdb_rating=str(meta.get("imdbRating") or ""),
            runtime=str(meta.get("runtime") or ""),
            director=", ".join(director) if isinstance(director, list) else str(director),
            raw=meta,
        )


@dataclass(frozen=True)
class WatchedMovie:
    """A movie with playback history, classified; what the exporters consume."""

    item_id: str
    title: str
    status: Status
    progress: float  # fraction of the runtime actually watched, 0..1
    time_watched_ms: int
    position_ms: int
    duration_ms: int
    times_watched: int
    last_watched: datetime | None
    in_library: bool
    genres: tuple[str, ...] = (UNKNOWN_GENRE,)
    year: str = ""
    imdb_rating: str = ""
    runtime: str = ""
    director: str = ""

    @property
    def imdb_url(self) -> str:
        return f"https://www.imdb.com/title/{self.item_id}/" if self.item_id.startswith("tt") else ""

    def with_meta(self, meta: MovieMeta) -> WatchedMovie:
        return replace(
            self,
            title=self.title or meta.name,
            genres=meta.genres or (UNKNOWN_GENRE,),
            year=meta.year,
            imdb_rating=meta.imdb_rating,
            runtime=meta.runtime,
            director=meta.director,
        )
