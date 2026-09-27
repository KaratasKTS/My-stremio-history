from datetime import datetime

import pytest

from stremio_watched.models import Status
from stremio_watched.watched import (
    attach_meta,
    extract_watched,
    filter_by_genres,
    genre_counts,
    parse_genre_selection,
    sort_chronological,
    sort_newest_first,
    status_counts,
)


def by_id(movies):
    return {movie.item_id: movie for movie in movies}


def test_classification_covers_every_status(items):
    movies = by_id(extract_watched(items))
    assert set(movies) == {"tt0111161", "tt0468569", "tt0068646", "tt0137523", "tmdb:123"}

    finished = movies["tt0111161"]
    assert finished.status is Status.WATCHED
    assert finished.progress == pytest.approx(2.2 / 2.37, abs=0.01)
    assert finished.position_ms == 0 and not finished.in_library

    resume = movies["tt0468569"]
    assert resume.status is Status.IN_PROGRESS
    assert resume.progress == pytest.approx(0.8 / 2.53, abs=0.01)

    partial = movies["tt0068646"]
    assert partial.status is Status.PARTIAL
    assert 0 < partial.progress < 0.2

    manual = movies["tt0137523"]
    assert manual.status is Status.WATCHED
    assert manual.progress == 1.0 and manual.times_watched == 1 and manual.in_library


def test_series_and_never_played_items_are_excluded(items):
    ids = {movie.item_id for movie in extract_watched(items)}
    assert "tt0903747" not in ids  # series
    assert "tt0110912" not in ids  # opened, nothing played


def test_library_only_keeps_bookmarked_titles(items):
    assert {m.item_id for m in extract_watched(items, library_only=True)} == {"tt0137523"}


def test_threshold_overrides_status(items):
    movies = by_id(extract_watched(items, threshold=0.3))
    assert movies["tt0468569"].status is Status.WATCHED  # 0.32 watched >= 0.3
    assert movies["tt0068646"].status is Status.PARTIAL  # 0.14 watched


def test_last_watched_is_local_naive_datetime(items):
    movie = by_id(extract_watched(items))["tt0111161"]
    assert isinstance(movie.last_watched, datetime) and movie.last_watched.tzinfo is None


def test_attach_meta_and_unknown_genre(items, metas):
    movies = by_id(attach_meta(extract_watched(items), metas))
    assert movies["tt0111161"].genres == ("Drama",)
    assert movies["tt0111161"].director == "Frank Darabont"
    assert movies["tt0468569"].genres == ("Action", "Crime", "Drama")  # `genre` key, list
    assert movies["tt0068646"].genres == ("Crime",)  # `genres` key, plain string
    assert movies["tmdb:123"].genres == ("Unknown",)
    assert movies["tmdb:123"].imdb_url == ""
    assert movies["tt0111161"].imdb_url.endswith("/tt0111161/")


def test_genre_counts_alphabetical_with_unknown_last(items, metas):
    movies = attach_meta(extract_watched(items), metas)
    assert genre_counts(movies) == [("Action", 1), ("Crime", 2), ("Drama", 3), ("Unknown", 1)]


def test_parse_genre_selection(items, metas):
    genres = genre_counts(attach_meta(extract_watched(items), metas))
    assert parse_genre_selection("all", genres) is None
    assert parse_genre_selection("0", genres) is None
    assert parse_genre_selection("", genres) is None
    assert parse_genre_selection("1, drama", genres) == {"Action", "Drama"}
    assert parse_genre_selection("CRIME", genres) == {"Crime"}
    with pytest.raises(ValueError, match="unknown genre"):
        parse_genre_selection("Bogus", genres)
    with pytest.raises(ValueError):
        parse_genre_selection("99", genres)


def test_filter_by_genres(items, metas):
    movies = attach_meta(extract_watched(items), metas)
    assert filter_by_genres(movies, None) == movies
    assert {m.item_id for m in filter_by_genres(movies, {"Action"})} == {"tt0468569"}
    assert {m.item_id for m in filter_by_genres(movies, {"Unknown"})} == {"tmdb:123"}


def test_sorting_and_counts(items):
    movies = extract_watched(items)
    newest = [m.item_id for m in sort_newest_first(movies)]
    oldest = [m.item_id for m in sort_chronological(movies)]
    assert newest[0] == "tt0111161" and newest[-1] == "tmdb:123"
    assert oldest == list(reversed(newest))
    assert status_counts(movies) == {Status.WATCHED: 2, Status.IN_PROGRESS: 2, Status.PARTIAL: 1}
