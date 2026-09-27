# stremio_fetch_watched

Export the movies you have watched in Stremio — including the ones you only watched part-way — to
the terminal, an Excel spreadsheet, a CSV, and/or a chronological text file. Your library is kept
in a local SQLite database so later exports don't need to download anything.

## Install

```sh
pip install -r requirements.txt        # requests, openpyxl
```

## Usage

```sh
python3 stremio_fetch_watched.py start        # fresh download from Stremio
python3 stremio_fetch_watched.py getWatched   # work from the local database
```

**`start`** — choose a saved account or add one (email + password in the terminal, no browser;
only the session key is stored), download the whole library from Stremio into `data/stremio.db`,
then pick genres and output formats.

**`getWatched`** — choose an account. If it has been synced before, everything comes from the
database (no network). If not, you are offered to fetch it now. Then pick genres and outputs.

Both commands then ask:

1. **Genres** — listed with counts; type numbers or names separated by commas, or `all`.
2. **Output** — `[1] Terminal table  [2] Excel (.xlsx)  [3] CSV  [4] Text file, one movie per line
   in chronological order  [5] All`. Files go to `output/stremio_watched_<account>_<date>.<ext>`.

### Skipping the menus

| Flag | Meaning |
|------|---------|
| `--account EMAIL` | use this account without asking |
| `--genres all` / `--genres "Action,Drama"` | skip the genre menu |
| `--formats all` / `--formats xlsx,txt` | skip the output menu (`terminal`, `xlsx`, `csv`, `txt`) |
| `--outdir PATH` | where files are written (default `output/`) |
| `--db PATH` | database location (default `data/stremio.db`) |
| `--threshold 0.7` | fraction of the runtime watched that counts as "Watched" (Stremio's own value) |
| `--library-only` | only movies currently in your Library (default: every movie you played) |

Example: `python3 stremio_fetch_watched.py getWatched --account me@example.com --genres all --formats all`

## What Stremio actually stores (and why this matters)

Everything comes from your account's `libraryItem` collection on `api.strem.io`. Verified
against the [stremio-core](https://github.com/Stremio/stremio-core) source:

- **Nothing is auto-deleted.** Every movie you ever played while logged in stays on the server
  with its state; there is no age limit or item cap.
- **`removed: true` does not mean deleted.** A movie played without pressing *Add to Library* is
  stored with `removed: true, temp: true` and stays that way. "Removed" simply means "not in my
  Library list", so this tool includes those by default (`--library-only` to exclude them).
- **"Watched" = more than 70% of the runtime actually watched** (`WATCHED_THRESHOLD_COEF`), which
  sets `timesWatched`/`flaggedWatched`. The 90% figure (`CREDITS_THRESHOLD_COEF`) is only where
  Stremio resets the *resume position* to 0 so the title leaves *Continue Watching*.
- Because of that reset, most finished movies have position 0; progress here is therefore
  measured from `timeWatched` (time actually watched), not from the resume position.

Status column: `Watched` (Stremio's flag, or ≥ `--threshold` watched), `In progress` (has a
resume position), `Partial` (some time watched, no resume position — dropped/rewound/dismissed).

Spreadsheet/CSV columns: Title, Year, Genres, Status, Watched %, Time watched, Position, Duration,
Times watched, Last watched, In library, IMDb rating, Runtime, Director, IMDb ID, IMDb URL.

## Project layout

```
stremio_fetch_watched.py   entry point
stremio_watched/           package: cli, workflows, prompts, api, cinemeta, db, watched, models, config, exporters/
tests/                     pytest suite (no network)
data/                      SQLite database (created on first run, not tracked)
output/                    exported files (not tracked)
```

Run the tests with `python3 -m pytest`.
