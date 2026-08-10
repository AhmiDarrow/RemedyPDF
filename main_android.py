#!/usr/bin/env python3
"""Android entry — Kivy-based PDF viewer for RemedyPDF.

Sets REMEDYPDF_MOBILE=1, then launches the Kivy UI (src/ui/kivy_app.py).
PyQt5 is NOT imported on Android — the Kivy app uses the same PDFEngine
backend directly.
"""
import os
import sys
from pathlib import Path

os.environ["REMEDYPDF_MOBILE"] = "1"

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def main() -> int:
    """Launch the Kivy-based Android PDF viewer. Returns exit code."""
    from src.ui.kivy_app import RemedyPDFApp

    RemedyPDFApp().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
