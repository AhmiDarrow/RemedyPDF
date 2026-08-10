"""Mobile / Android APK helpers — touch targets, DPI scale, platform detect."""

from __future__ import annotations

import os
import sys
from typing import Tuple


# Material Design / iOS minimum touch target
MIN_TOUCH_TARGET_PX = 44

# Comfortable toolbar / nav control height on phones
MOBILE_CONTROL_HEIGHT = 48

# Default mobile zoom slightly lower so spreads fit
MOBILE_DEFAULT_ZOOM = 1.0

# Mobile reader tap zones — fraction of width at each edge that flips pages
TAP_ZONE_EDGE = 0.30


def is_android() -> bool:
    """True when running under Android (python-for-android / Pyjnius / env)."""
    if sys.platform.startswith("android"):
        return True
    if "ANDROID_ARGUMENT" in os.environ or "ANDROID_ROOT" in os.environ:
        return True
    if os.environ.get("REMEDYPDF_MOBILE", "").strip() in ("1", "true", "yes"):
        return True
    return False


def is_mobile() -> bool:
    """Android or explicit mobile mode (for APK / emulator testing on desktop)."""
    if is_android():
        return True
    flag = os.environ.get("REMEDYPDF_MOBILE", "").strip().lower()
    return flag in ("1", "true", "yes", "mobile")


def is_touch_primary() -> bool:
    """Prefer touch gestures (long-press edit) over double-click."""
    if is_mobile():
        return True
    return os.environ.get("REMEDYPDF_TOUCH", "").strip().lower() in ("1", "true", "yes")


def ui_scale_factor() -> float:
    """Optional UI scale from env (e.g. REMEDYPDF_UI_SCALE=1.25)."""
    raw = os.environ.get("REMEDYPDF_UI_SCALE", "").strip()
    if not raw:
        return 1.25 if is_mobile() else 1.0
    try:
        return max(0.85, min(2.5, float(raw)))
    except ValueError:
        return 1.0


def touch_target_px(scale: float | None = None) -> int:
    s = ui_scale_factor() if scale is None else scale
    return max(MIN_TOUCH_TARGET_PX, int(round(MOBILE_CONTROL_HEIGHT * s / 1.25)))


def recommended_window_size() -> Tuple[int, int]:
    """Sensible starting size; phones use a portrait-ish frame when emulated."""
    if is_mobile():
        return (420, 780)
    return (1100, 800)


def recommended_default_zoom() -> float:
    return MOBILE_DEFAULT_ZOOM if is_mobile() else 1.25


def mobile_stylesheet_extras(scale: float | None = None) -> str:
    """Extra QSS for larger hit targets on APK / mobile mode."""
    if not is_mobile() and not is_touch_primary():
        return ""
    h = touch_target_px(scale)
    pad_y = max(8, h // 5)
    pad_x = max(12, h // 3)
    font_px = max(14, int(13 * (scale or ui_scale_factor())))
    return f"""
/* ===== Mobile / APK touch polish ===== */
QWidget {{
    font-size: {font_px}px;
}}
QToolButton, QPushButton {{
    min-height: {h - 8}px;
    padding: {pad_y}px {pad_x}px;
    border-radius: 10px;
}}
QToolBar {{
    spacing: 8px;
    padding: 8px 10px;
}}
QSpinBox, QLineEdit {{
    min-height: {h - 10}px;
    padding: {pad_y - 2}px 12px;
    font-size: {font_px}px;
}}
QMenuBar::item {{
    padding: 10px 14px;
}}
QMenu::item {{
    padding: 12px 28px 12px 18px;
}}
QStatusBar {{
    min-height: 28px;
    font-size: {max(12, font_px - 1)}px;
}}
QScrollArea {{
    /* smoother flick feel on touch */
}}
#pageNavigator QPushButton {{
    min-width: 72px;
    min-height: {h}px;
}}
#pdfCanvas {{
    font-size: {font_px}px;
}}
"""


def apply_mobile_attribute(qapp) -> None:
    """Enable high-DPI and touch-friendly Qt attributes when available."""
    try:
        from PyQt5.QtCore import Qt
        from PyQt5.QtWidgets import QApplication

        # High DPI (no-ops on newer Qt if already default)
        for attr in (
            "AA_EnableHighDpiScaling",
            "AA_UseHighDpiPixmaps",
            "AA_SynthesizeTouchForUnhandledMouseEvents",
            "AA_SynthesizeMouseForUnhandledTouchEvents",
        ):
            flag = getattr(Qt, attr, None)
            if flag is not None:
                try:
                    QApplication.setAttribute(flag, True)
                except Exception:  # noqa: BLE001
                    pass
        if qapp is not None and is_mobile():
            qapp.setAttribute(Qt.AA_SynthesizeMouseForUnhandledTouchEvents, True)
    except Exception:  # noqa: BLE001
        pass


def tap_zone_for(x: float, width: float) -> int:
    """Classic reader tap zones: +1 next (right edge), -1 prev (left edge), 0 middle.

    Pure function so it is easy to test headlessly. The canvas uses this to
    decide whether a quick tap flips the page on mobile.
    """
    if width <= 0:
        return 0
    frac = x / width
    if frac >= 1.0 - TAP_ZONE_EDGE:
        return 1
    if frac <= TAP_ZONE_EDGE:
        return -1
    return 0
