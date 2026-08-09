"""Remedy themes and shared form styles (QSS)."""

from __future__ import annotations

from typing import Dict, Literal

ThemeName = Literal["dark", "light"]

# Remedy brand palette
REMEDY_ACCENT = "#6C5CE7"
REMEDY_ACCENT_HOVER = "#7F71F0"
REMEDY_ACCENT_PRESSED = "#5A4BD1"
REMEDY_SUCCESS = "#00B894"
REMEDY_WARNING = "#FDCB6E"
REMEDY_DANGER = "#FF6B6B"


DARK: Dict[str, str] = {
    "name": "dark",
    "window": "#1A1B26",
    "panel": "#24283B",
    "panel_alt": "#1F2335",
    "border": "#3B4261",
    "border_soft": "#2A2F45",
    "text": "#C0CAF5",
    "text_muted": "#9AA5CE",
    "text_dim": "#565F89",
    "input_bg": "#1F2335",
    "input_border": "#3B4261",
    "canvas": "#16161E",
    "canvas_text": "#565F89",
    "selection": "#6C5CE7",
    "selection_text": "#FFFFFF",
    "menu_bg": "#1F2335",
    "toolbar_bg": "#1F2335",
    "status_bg": "#16161E",
    "button_bg": "#2A2F45",
    "button_hover": "#3B4261",
    "button_pressed": "#1A1B26",
    "accent": REMEDY_ACCENT,
    "accent_hover": REMEDY_ACCENT_HOVER,
    "accent_pressed": REMEDY_ACCENT_PRESSED,
    "scrollbar": "#3B4261",
    "scrollbar_hover": "#565F89",
    "tooltip_bg": "#24283B",
    "tooltip_text": "#C0CAF5",
}

LIGHT: Dict[str, str] = {
    "name": "light",
    "window": "#F7F8FC",
    "panel": "#FFFFFF",
    "panel_alt": "#EEF0F7",
    "border": "#D8DCE8",
    "border_soft": "#E8EBF4",
    "text": "#1A1B26",
    "text_muted": "#4A5168",
    "text_dim": "#8B93A7",
    "input_bg": "#FFFFFF",
    "input_border": "#C5CAD8",
    "canvas": "#E4E7F1",
    "canvas_text": "#8B93A7",
    "selection": "#6C5CE7",
    "selection_text": "#FFFFFF",
    "menu_bg": "#FFFFFF",
    "toolbar_bg": "#FFFFFF",
    "status_bg": "#EEF0F7",
    "button_bg": "#EEF0F7",
    "button_hover": "#E0E3EF",
    "button_pressed": "#D0D4E4",
    "accent": REMEDY_ACCENT,
    "accent_hover": REMEDY_ACCENT_HOVER,
    "accent_pressed": REMEDY_ACCENT_PRESSED,
    "scrollbar": "#C5CAD8",
    "scrollbar_hover": "#8B93A7",
    "tooltip_bg": "#1A1B26",
    "tooltip_text": "#F7F8FC",
}

THEMES: Dict[str, Dict[str, str]] = {"dark": DARK, "light": LIGHT}
DEFAULT_THEME: ThemeName = "dark"


def get_palette(name: str | None = None) -> Dict[str, str]:
    key = (name or DEFAULT_THEME).lower()
    return THEMES.get(key, DARK).copy()


def build_stylesheet(theme: str | Dict[str, str] | None = None) -> str:
    """Full application QSS — windows, menus, toolbars, forms, scrollbars."""
    p = get_palette(theme) if isinstance(theme, str) or theme is None else theme

    return f"""
/* ===== RemedyPDF — {p['name']} theme ===== */
QWidget {{
    background-color: {p['window']};
    color: {p['text']};
    font-family: "Segoe UI", "SF Pro Text", "Helvetica Neue", sans-serif;
    font-size: 13px;
}}

QMainWindow, QDialog {{
    background-color: {p['window']};
}}

/* ----- Menus ----- */
QMenuBar {{
    background-color: {p['panel']};
    color: {p['text']};
    border-bottom: 1px solid {p['border_soft']};
    padding: 2px 6px;
    spacing: 4px;
}}
QMenuBar::item {{
    background: transparent;
    padding: 6px 12px;
    border-radius: 6px;
}}
QMenuBar::item:selected {{
    background: {p['button_hover']};
}}
QMenuBar::item:pressed {{
    background: {p['accent']};
    color: {p['selection_text']};
}}
QMenu {{
    background-color: {p['menu_bg']};
    color: {p['text']};
    border: 1px solid {p['border']};
    border-radius: 8px;
    padding: 6px;
}}
QMenu::item {{
    padding: 8px 28px 8px 16px;
    border-radius: 6px;
}}
QMenu::item:selected {{
    background: {p['accent']};
    color: {p['selection_text']};
}}
QMenu::separator {{
    height: 1px;
    background: {p['border_soft']};
    margin: 6px 10px;
}}
QMenu::indicator {{
    width: 14px;
    height: 14px;
    margin-left: 8px;
}}

/* ----- Toolbar ----- */
QToolBar {{
    background-color: {p['toolbar_bg']};
    border: none;
    border-bottom: 1px solid {p['border_soft']};
    spacing: 6px;
    padding: 6px 10px;
}}
QToolBar::separator {{
    background: {p['border']};
    width: 1px;
    margin: 6px 8px;
}}
QToolButton {{
    background-color: {p['button_bg']};
    color: {p['text']};
    border: 1px solid {p['border_soft']};
    border-radius: 8px;
    padding: 6px 12px;
    min-height: 22px;
}}
QToolButton:hover {{
    background-color: {p['button_hover']};
    border-color: {p['border']};
}}
QToolButton:pressed, QToolButton:checked {{
    background-color: {p['accent']};
    color: {p['selection_text']};
    border-color: {p['accent_pressed']};
}}
QToolButton:disabled {{
    color: {p['text_dim']};
    background-color: {p['panel_alt']};
}}

/* ----- Buttons (forms) ----- */
QPushButton {{
    background-color: {p['button_bg']};
    color: {p['text']};
    border: 1px solid {p['border']};
    border-radius: 8px;
    padding: 8px 16px;
    min-height: 20px;
    font-weight: 500;
}}
QPushButton:hover {{
    background-color: {p['button_hover']};
    border-color: {p['accent']};
}}
QPushButton:pressed {{
    background-color: {p['button_pressed']};
}}
QPushButton:disabled {{
    color: {p['text_dim']};
    background-color: {p['panel_alt']};
    border-color: {p['border_soft']};
}}
QPushButton[cssClass="primary"], QPushButton#primaryButton {{
    background-color: {p['accent']};
    color: {p['selection_text']};
    border: 1px solid {p['accent_pressed']};
}}
QPushButton[cssClass="primary"]:hover, QPushButton#primaryButton:hover {{
    background-color: {p['accent_hover']};
}}
QPushButton[cssClass="primary"]:pressed, QPushButton#primaryButton:pressed {{
    background-color: {p['accent_pressed']};
}}

/* ----- Form inputs ----- */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background-color: {p['input_bg']};
    color: {p['text']};
    border: 1px solid {p['input_border']};
    border-radius: 8px;
    padding: 7px 10px;
    selection-background-color: {p['selection']};
    selection-color: {p['selection_text']};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border: 1px solid {p['accent']};
}}
QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled {{
    color: {p['text_dim']};
    background-color: {p['panel_alt']};
}}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    background: {p['button_bg']};
    border: none;
    width: 18px;
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{
    background: {p['button_hover']};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background-color: {p['menu_bg']};
    color: {p['text']};
    border: 1px solid {p['border']};
    selection-background-color: {p['accent']};
    selection-color: {p['selection_text']};
    outline: none;
}}

/* ----- Labels / status ----- */
QLabel {{
    background: transparent;
    color: {p['text']};
}}
QLabel#mutedLabel, QLabel[cssClass="muted"] {{
    color: {p['text_muted']};
}}
QStatusBar {{
    background-color: {p['status_bg']};
    color: {p['text_muted']};
    border-top: 1px solid {p['border_soft']};
    padding: 2px 8px;
}}
QStatusBar::item {{
    border: none;
}}

/* ----- Scroll areas ----- */
QScrollArea {{
    background-color: {p['canvas']};
    border: none;
}}
QScrollArea > QWidget > QWidget {{
    background-color: {p['canvas']};
}}
QScrollBar:vertical {{
    background: {p['panel_alt']};
    width: 12px;
    margin: 0;
    border-radius: 6px;
}}
QScrollBar::handle:vertical {{
    background: {p['scrollbar']};
    min-height: 32px;
    border-radius: 6px;
    margin: 2px;
}}
QScrollBar::handle:vertical:hover {{
    background: {p['scrollbar_hover']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    height: 0;
    background: none;
}}
QScrollBar:horizontal {{
    background: {p['panel_alt']};
    height: 12px;
    margin: 0;
    border-radius: 6px;
}}
QScrollBar::handle:horizontal {{
    background: {p['scrollbar']};
    min-width: 32px;
    border-radius: 6px;
    margin: 2px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {p['scrollbar_hover']};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    width: 0;
    background: none;
}}

/* ----- PDF canvas ----- */
QLabel#pdfCanvas {{
    background-color: {p['canvas']};
    color: {p['canvas_text']};
    border: none;
    font-size: 15px;
}}

/* ----- Dialogs / message boxes ----- */
QMessageBox, QInputDialog {{
    background-color: {p['panel']};
}}
QMessageBox QLabel, QInputDialog QLabel {{
    color: {p['text']};
}}
QDialogButtonBox QPushButton {{
    min-width: 80px;
}}

/* ----- Tooltips ----- */
QToolTip {{
    background-color: {p['tooltip_bg']};
    color: {p['tooltip_text']};
    border: 1px solid {p['border']};
    border-radius: 6px;
    padding: 6px 10px;
}}

/* ----- Page navigator strip ----- */
QWidget#pageNavigator {{
    background-color: {p['panel']};
    border: 1px solid {p['border_soft']};
    border-radius: 10px;
}}

/* ----- Search bar ----- */
QWidget#searchBar {{
    background-color: {p['panel']};
    border-bottom: 1px solid {p['border_soft']};
}}
QLineEdit#searchField {{
    background-color: {p['input_bg']};
    border: 1px solid {p['input_border']};
    border-radius: 8px;
    padding: 8px 12px;
    min-width: 220px;
}}
QLineEdit#searchField:focus {{
    border: 1px solid {p['accent']};
}}
"""


def apply_theme(app, theme_name: str = DEFAULT_THEME, *, mobile: bool | None = None) -> str:
    """Apply stylesheet to a QApplication (or any QWidget). Returns theme name.

    When mobile is True (or auto-detected), appends APK/touch-friendly QSS extras.
    """
    name = (theme_name or DEFAULT_THEME).lower()
    if name not in THEMES:
        name = DEFAULT_THEME
    css = build_stylesheet(name)
    try:
        from utils.mobile import is_mobile, is_touch_primary, mobile_stylesheet_extras
    except ImportError:
        try:
            from src.utils.mobile import (  # type: ignore
                is_mobile,
                is_touch_primary,
                mobile_stylesheet_extras,
            )
        except ImportError:
            is_mobile = lambda: False  # type: ignore
            is_touch_primary = lambda: False  # type: ignore
            mobile_stylesheet_extras = lambda scale=None: ""  # type: ignore

    use_mobile = is_mobile() or is_touch_primary() if mobile is None else bool(mobile)
    if use_mobile:
        css = css + "\n" + mobile_stylesheet_extras()
    app.setStyleSheet(css)
    try:
        app.setProperty("remedyTheme", name)
        app.setProperty("remedyMobile", use_mobile)
    except Exception:  # noqa: BLE001
        pass
    return name


def toggle_theme(current: str) -> str:
    return "light" if (current or "").lower() == "dark" else "dark"
