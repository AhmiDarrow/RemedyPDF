#!/usr/bin/env python3
"""p4a entry — delegates to main_android."""
from main_android import main

# Exported for test alignment + version checks
from src import __version__ as VERSION  # noqa: E402,F401

if __name__ == '__main__':
    raise SystemExit(main())
