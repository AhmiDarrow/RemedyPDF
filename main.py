#!/usr/bin/env python3
"""p4a entry — delegates to main_android."""
from src import __version__ as VERSION
from main_android import main
if __name__ == '__main__':
    raise SystemExit(main())
