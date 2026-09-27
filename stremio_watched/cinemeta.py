"""Cinemeta metadata add-on client (genres, year, rating...). Network only."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from .config import CINEMETA_URL, HTTP_TIMEOUT, META_WORKERS, USER_AGENT
from .models import MovieMeta

ProgressCallback = Callable[[int, int], None]


def supports(item_id: str) -> bool:
    """Cinemeta only knows IMDb ids; e.g. `tmdb:123` items get no metadata."""
    return item_id.startswith("tt")


class CinemetaClient:
    def __init__(
        self,
        url_template: str = CINEMETA_URL,
        timeout: int = HTTP_TIMEOUT,
        workers: int = META_WORKERS,
        session: requests.Session | None = None,
    ):
        self._url_template = url_template
        self._timeout = timeout
        self._workers = workers
        self._session = session or requests.Session()
        self._session.headers.setdefault("User-Agent", USER_AGENT)

    def fetch(self, item_id: str) -> MovieMeta | None:
        try:
            response = self._session.get(self._url_template.format(id=item_id), timeout=self._timeout)
            if response.status_code != 200:
                return None
            meta = response.json().get("meta")
        except (requests.RequestException, ValueError):
            return None
        return MovieMeta.from_cinemeta(item_id, meta) if meta else None

    def fetch_many(self, ids: Iterable[str], progress: ProgressCallback | None = None) -> dict[str, MovieMeta]:
        """Fetch several ids concurrently; ids Cinemeta cannot serve are skipped silently."""
        wanted = sorted({i for i in ids if supports(i)})
        found: dict[str, MovieMeta] = {}
        if not wanted:
            return found
        with ThreadPoolExecutor(max_workers=self._workers) as pool:
            futures = {pool.submit(self.fetch, item_id): item_id for item_id in wanted}
            for done, future in enumerate(as_completed(futures), 1):
                meta = future.result()
                if meta is not None:
                    found[meta.item_id] = meta
                if progress:
                    progress(done, len(wanted))
        return found
