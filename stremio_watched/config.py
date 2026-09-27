"""Paths, endpoints and constants. No logic lives here."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_DIR / "data"
OUTPUT_DIR = PROJECT_DIR / "output"
DB_PATH = Path(os.environ.get("STREMIO_WATCHED_DB", DATA_DIR / "stremio.db"))

# Stremio account API and the official metadata add-on.
API_URL = "https://api.strem.io/api"
CINEMETA_URL = "https://v3-cinemeta.strem.io/meta/movie/{id}.json"
HTTP_TIMEOUT = 30
META_WORKERS = 8
MAX_LOGIN_ATTEMPTS = 3
USER_AGENT = "stremio_fetch_watched/2.0"

# From stremio-core `constants.rs`:
#   WATCHED_THRESHOLD_COEF - a movie is flagged watched once *time actually watched* exceeds this
#   fraction of its duration.
#   CREDITS_THRESHOLD_COEF - once the *position* passes this fraction the resume point is reset
#   to 0 (the title leaves "Continue Watching"), which is why finished movies show position 0.
WATCHED_THRESHOLD = 0.7
CREDITS_THRESHOLD = 0.9

UNKNOWN_GENRE = "Unknown"

# v1 of this tool stored accounts and the metadata cache as JSON files; they are imported into
# the database the first time it is created.
_XDG_CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
_XDG_CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
LEGACY_ACCOUNTS_FILE = _XDG_CONFIG / "stremio_fetch_watched" / "accounts.json"
LEGACY_META_FILE = _XDG_CACHE / "stremio_fetch_watched" / "meta.json"
