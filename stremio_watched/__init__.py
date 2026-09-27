"""Export watched (fully or partially) movies from a Stremio account.

Layers (see CLAUDE.md):
  api / cinemeta  -> network only
  db              -> SQLite only
  watched         -> pure domain logic
  prompts         -> terminal input only
  exporters       -> output writers
  workflows / cli -> orchestration
"""

__version__ = "2.0.0"
