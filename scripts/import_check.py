#!/usr/bin/env python3
"""Dry-run imports for CI (no GUI show)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def main() -> int:
    # Package metadata
    import src  # noqa: F401
    from src import __version__, GITHUB_OWNER, GITHUB_REPO  # noqa: F401

    # Core
    from src.core.pdf_engine import PDFEngine  # noqa: F401
    from src.core.app import RemedyPDFApp  # noqa: F401

    # UI / utils
    from src.ui import theme, widgets, about  # noqa: F401
    from src.utils import brand, mobile, paths, updater  # noqa: F401

    print(f"import_check OK version={__version__} repo={GITHUB_OWNER}/{GITHUB_REPO}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
