#!/usr/bin/env python3
"""Entry point. Usage: python3 stremio_fetch_watched.py start|getWatched [options]"""

import sys

from stremio_watched.cli import main

if __name__ == "__main__":
    sys.exit(main())
