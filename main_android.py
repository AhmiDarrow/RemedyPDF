#!/usr/bin/env python3
"""Android entry — force mobile QoL then start RemedyPDF."""
import os
import sys
from pathlib import Path

os.environ["REMEDYPDF_MOBILE"] = "1"
os.environ.setdefault("QT_QPA_PLATFORM", "android")

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.main import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
