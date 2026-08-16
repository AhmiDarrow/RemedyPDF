"""Path helpers."""

from __future__ import annotations

import sys
from pathlib import Path


def project_root() -> Path:
    """Return the RemedyPDF project root (parent of src/).

    In a PyInstaller freeze, prefer the folder that actually holds bundled
    data (``sys._MEIPASS`` for onefile, or the onedir app folder next to the
    exe). Dev / editable installs keep the repo root (parent of ``src/``).
    """
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


def resources_dir() -> Path:
    """Brand / icon assets directory.

    Checks frozen bundle layouts first so packaged builds find
    ``resources/`` next to the exe or under ``_MEIPASS``, then falls back
    to the dev-tree path under the project root.
    """
    if getattr(sys, "frozen", False):
        candidates = []
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "resources")
        exe_dir = Path(sys.executable).resolve().parent
        candidates.append(exe_dir / "resources")
        # onedir sometimes nests data under _internal/
        candidates.append(exe_dir / "_internal" / "resources")
        for c in candidates:
            if c.is_dir():
                return c
        # Prefer MEIPASS path even if not yet extracted (onefile race)
        if meipass:
            return Path(meipass) / "resources"
        return exe_dir / "resources"
    return project_root() / "resources"
