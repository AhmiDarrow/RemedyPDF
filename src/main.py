#!/usr/bin/env python3
"""
RemedyPDF - A sleek, fast PDF viewer and editor
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root and src are importable when run as a script
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = Path(__file__).resolve().parent
for path in (str(PROJECT_ROOT), str(SRC_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

try:
    from src import __app_name__ as APP_NAME
    from src import __version__ as VERSION
except ImportError:
    try:
        from __init__ import __app_name__ as APP_NAME  # type: ignore
        from __init__ import __version__ as VERSION  # type: ignore
    except ImportError:
        APP_NAME = "RemedyPDF"
        VERSION = "1.2.0"


def main(argv: list[str] | None = None) -> int:
    """Application entry point."""
    args = list(sys.argv if argv is None else argv)
    try:
        from core.app import run
    except ImportError:
        from src.core.app import run  # type: ignore
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
