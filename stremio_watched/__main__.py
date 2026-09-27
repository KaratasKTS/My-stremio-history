"""Allow `python3 -m stremio_watched start|getWatched`."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
