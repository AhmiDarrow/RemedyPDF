"""Brand asset paths — icons and logos for window, About, and builds."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from .paths import project_root, resources_dir

__all__ = [
    "project_root",
    "resources_dir",
    "icon_path",
    "icon_ico_path",
    "icon_png",
    "icon_ico",
    "logo_path",
    "logo_ui_path",
    "logo_png",
    "logo_ui",
    "about_mark_path",
    "window_icon_path",
    "brand_assets",
    "brand_files_present",
    "required_brand_files",
    "apply_app_icon",
    "first_existing",
]


def icon_png() -> Path:
    return resources_dir() / "icon.png"


def icon_ico() -> Path:
    return resources_dir() / "icon.ico"


def icon_transparent() -> Path:
    return resources_dir() / "icon_transparent.png"


def logo_png() -> Path:
    return resources_dir() / "logo.png"


def logo_ui() -> Path:
    """Compact logo preferred in About / chrome; falls back to logo.png."""
    ui = resources_dir() / "logo_ui.png"
    return ui if ui.is_file() else logo_png()


def logo_transparent() -> Path:
    return resources_dir() / "logo_transparent.png"


def brand_preview() -> Path:
    return resources_dir() / "brand_preview.png"


def icons_dir() -> Path:
    return resources_dir() / "icons"


# Friendly aliases used by app / package exports
def icon_path() -> Path:
    return icon_png()


def icon_ico_path() -> Path:
    return icon_ico()


def logo_path() -> Path:
    return logo_png()


def logo_ui_path() -> Path:
    return logo_ui()


def first_existing(*candidates: Path) -> Optional[Path]:
    for p in candidates:
        if p is not None and Path(p).is_file():
            return Path(p)
    return None


def window_icon_path() -> Optional[Path]:
    """Best icon for QMainWindow / QApplication (prefer multi-size ICO on Windows)."""
    return first_existing(icon_ico(), icon_png(), icon_transparent())


def about_mark_path() -> Optional[Path]:
    """Mark / logo for About dialog header."""
    ui = resources_dir() / "logo_ui.png"
    return first_existing(ui, logo_png(), icon_png(), icon_transparent())


def required_brand_files() -> list[Path]:
    """Core brand files that must ship with the app."""
    return [icon_png(), icon_ico(), logo_png(), resources_dir() / "logo_ui.png"]


def brand_files_present() -> dict[str, bool]:
    names = {
        "icon.png": icon_png(),
        "icon.ico": icon_ico(),
        "icon_transparent.png": icon_transparent(),
        "logo.png": logo_png(),
        "logo_transparent.png": logo_transparent(),
        "logo_ui.png": resources_dir() / "logo_ui.png",
        "brand_preview.png": brand_preview(),
    }
    return {k: v.is_file() for k, v in names.items()}


def brand_assets() -> dict[str, Path]:
    """Map of logical brand names → paths (may or may not exist)."""
    return {
        "icon": icon_png(),
        "icon_ico": icon_ico(),
        "icon_transparent": icon_transparent(),
        "logo": logo_png(),
        "logo_ui": resources_dir() / "logo_ui.png",
        "logo_transparent": logo_transparent(),
        "preview": brand_preview(),
        "icons_dir": icons_dir(),
    }


def apply_app_icon(target: Any) -> bool:
    """Set window/application icon from resources. Returns True if applied."""
    path = window_icon_path()
    if path is None:
        return False
    try:
        from PyQt5.QtGui import QIcon
    except ImportError:
        return False
    try:
        icon = QIcon(str(path))
        if icon.isNull():
            # fallback PNG
            png = icon_png()
            if png.is_file():
                icon = QIcon(str(png))
        if icon.isNull():
            return False
        if hasattr(target, "setWindowIcon"):
            target.setWindowIcon(icon)
        if hasattr(target, "setWindowIcon") is False and hasattr(target, "setIcon"):
            target.setIcon(icon)
        # QApplication also supports setWindowIcon
        return True
    except Exception:  # noqa: BLE001
        return False
