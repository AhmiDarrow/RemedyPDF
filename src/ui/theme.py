"""Remedy themes and shared form styles (QSS)."""

from __future__ import annotations

from typing import Dict, Literal, Tuple

ThemeName = Literal[
    "normal",
    "dark",
    "light",
    "high_contrast",
    "sepia",
    "night",
    "midnight",
    "paper",
    "slate",
]

# Remedy brand palette
REMEDY_ACCENT = "#6C5CE7"
REMEDY_ACCENT_HOVER = "#7F71F0"
REMEDY_ACCENT_PRESSED = "#5A4BD1"
REMEDY_SUCCESS = "#00B894"
REMEDY_WARNING = "#FDCB6E"
REMEDY_DANGER = "#FF6B6B"

# Reading / visibility modes (UI chrome + canvas feel)
THEME_LABELS = {
    "normal": "Normal (no theme)",
    "dark": "Dark",
    "light": "Light",
    "high_contrast": "High contrast",
    "sepia": "Sepia (paper)",
    "night": "Night (OLED)",
    "midnight": "Midnight blue",
    "paper": "Soft paper",
    "slate": "Slate gray",
}

# Page filter labels (document pixels — independent of chrome theme)
PAGE_FILTER_LABELS = {
    "none": "Normal page",
    "invert": "Invert page (dark paper)",
    "sepia": "Sepia page",
    "grayscale": "Grayscale page",
    "warm": "Warm page",
    "cool": "Cool page",
}


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
    "canvas_text": "#9AA5CE",
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
    # Document page recolor (view-only ink + paper)
    "page_ink": "#C0CAF5",
    "page_paper": "#1A1B26",
    "link": "#A78BFA",
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
    "canvas_text": "#4A5168",
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
    "page_ink": "#1A1B26",
    "page_paper": "#FFFFFF",
    "link": "#5B4FC7",
}

HIGH_CONTRAST: Dict[str, str] = {
    "name": "high_contrast",
    "window": "#000000",
    "panel": "#0A0A0A",
    "panel_alt": "#141414",
    "border": "#FFFFFF",
    "border_soft": "#CCCCCC",
    "text": "#FFFFFF",
    "text_muted": "#F0F0F0",
    "text_dim": "#BBBBBB",
    "input_bg": "#000000",
    "input_border": "#FFFFFF",
    "canvas": "#000000",
    "canvas_text": "#FFFFFF",
    "selection": "#FFFF00",
    "selection_text": "#000000",
    "menu_bg": "#000000",
    "toolbar_bg": "#0A0A0A",
    "status_bg": "#000000",
    "button_bg": "#1A1A1A",
    "button_hover": "#333333",
    "button_pressed": "#000000",
    "accent": "#00E5FF",
    "accent_hover": "#66F0FF",
    "accent_pressed": "#00B8CC",
    "scrollbar": "#FFFFFF",
    "scrollbar_hover": "#FFFF00",
    "tooltip_bg": "#000000",
    "tooltip_text": "#FFFFFF",
    "page_ink": "#FFFFFF",
    "page_paper": "#000000",
    "link": "#FFFF00",
}

SEPIA: Dict[str, str] = {
    "name": "sepia",
    "window": "#F4ECD8",
    "panel": "#FBF6EA",
    "panel_alt": "#EDE4CF",
    "border": "#C9B896",
    "border_soft": "#E0D4B5",
    "text": "#3B2F1E",
    "text_muted": "#5C4A32",
    "text_dim": "#8A7350",
    "input_bg": "#FFFAF0",
    "input_border": "#C9B896",
    "canvas": "#E8DCC4",
    "canvas_text": "#5C4A32",
    "selection": "#8B6914",
    "selection_text": "#FFF8E7",
    "menu_bg": "#FBF6EA",
    "toolbar_bg": "#FBF6EA",
    "status_bg": "#EDE4CF",
    "button_bg": "#EDE4CF",
    "button_hover": "#E0D4B5",
    "button_pressed": "#D4C49E",
    "accent": "#8B6914",
    "accent_hover": "#A67C1A",
    "accent_pressed": "#6B5010",
    "scrollbar": "#C9B896",
    "scrollbar_hover": "#8A7350",
    "tooltip_bg": "#3B2F1E",
    "tooltip_text": "#F4ECD8",
    "page_ink": "#3B2F1E",
    "page_paper": "#F4ECD8",
    "link": "#8B6914",
}

NIGHT: Dict[str, str] = {
    "name": "night",
    "window": "#000000",
    "panel": "#0B0D12",
    "panel_alt": "#12151C",
    "border": "#2A3142",
    "border_soft": "#1A1F2B",
    "text": "#A8B4D4",
    "text_muted": "#7A869E",
    "text_dim": "#4A5568",
    "input_bg": "#0B0D12",
    "input_border": "#2A3142",
    "canvas": "#000000",
    "canvas_text": "#7A869E",
    "selection": "#5B4FC7",
    "selection_text": "#FFFFFF",
    "menu_bg": "#0B0D12",
    "toolbar_bg": "#0B0D12",
    "status_bg": "#000000",
    "button_bg": "#151922",
    "button_hover": "#1E2430",
    "button_pressed": "#0B0D12",
    "accent": "#7C6CF0",
    "accent_hover": "#9588F5",
    "accent_pressed": "#5B4FC7",
    "scrollbar": "#2A3142",
    "scrollbar_hover": "#4A5568",
    "tooltip_bg": "#12151C",
    "tooltip_text": "#A8B4D4",
    "page_ink": "#A8B4D4",
    "page_paper": "#000000",
    "link": "#9588F5",
}

# Deep blue reading chrome — easy on eyes at night without pure black crush
MIDNIGHT: Dict[str, str] = {
    "name": "midnight",
    "window": "#0D1526",
    "panel": "#152238",
    "panel_alt": "#101C30",
    "border": "#2A4060",
    "border_soft": "#1A2C48",
    "text": "#D6E4FF",
    "text_muted": "#9BB0D4",
    "text_dim": "#5A7198",
    "input_bg": "#101C30",
    "input_border": "#2A4060",
    "canvas": "#0A1220",
    "canvas_text": "#9BB0D4",
    "selection": "#3D7EFF",
    "selection_text": "#FFFFFF",
    "menu_bg": "#152238",
    "toolbar_bg": "#152238",
    "status_bg": "#0A1220",
    "button_bg": "#1A2C48",
    "button_hover": "#243A5C",
    "button_pressed": "#0D1526",
    "accent": "#4C8DFF",
    "accent_hover": "#6BA3FF",
    "accent_pressed": "#2F6FE0",
    "scrollbar": "#2A4060",
    "scrollbar_hover": "#5A7198",
    "tooltip_bg": "#152238",
    "tooltip_text": "#D6E4FF",
    "page_ink": "#D6E4FF",
    "page_paper": "#0D1526",
    "link": "#6BA3FF",
}

# Soft off-white paper — long daylight reading, low glare
PAPER: Dict[str, str] = {
    "name": "paper",
    "window": "#F3EFE6",
    "panel": "#FAF7F0",
    "panel_alt": "#EBE6DA",
    "border": "#D0C8B6",
    "border_soft": "#E2DCCE",
    "text": "#2C2820",
    "text_muted": "#5A5346",
    "text_dim": "#8A8274",
    "input_bg": "#FFFCF7",
    "input_border": "#D0C8B6",
    "canvas": "#E8E2D4",
    "canvas_text": "#5A5346",
    "selection": "#6C5CE7",
    "selection_text": "#FFFFFF",
    "menu_bg": "#FAF7F0",
    "toolbar_bg": "#FAF7F0",
    "status_bg": "#EBE6DA",
    "button_bg": "#EBE6DA",
    "button_hover": "#E0D9C8",
    "button_pressed": "#D4CCB8",
    "accent": "#5B4FC7",
    "accent_hover": "#6C5CE7",
    "accent_pressed": "#4A3FB0",
    "scrollbar": "#D0C8B6",
    "scrollbar_hover": "#8A8274",
    "tooltip_bg": "#2C2820",
    "tooltip_text": "#F3EFE6",
    "page_ink": "#2C2820",
    "page_paper": "#FAF7F0",
    "link": "#5B4FC7",
}

# Neutral slate — balanced contrast, low color cast
SLATE: Dict[str, str] = {
    "name": "slate",
    "window": "#1E2228",
    "panel": "#272C34",
    "panel_alt": "#22262E",
    "border": "#3D4450",
    "border_soft": "#2E343E",
    "text": "#E8EAED",
    "text_muted": "#B0B6C0",
    "text_dim": "#6B7280",
    "input_bg": "#22262E",
    "input_border": "#3D4450",
    "canvas": "#181B20",
    "canvas_text": "#B0B6C0",
    "selection": "#6C5CE7",
    "selection_text": "#FFFFFF",
    "menu_bg": "#272C34",
    "toolbar_bg": "#272C34",
    "status_bg": "#181B20",
    "button_bg": "#2E343E",
    "button_hover": "#3D4450",
    "button_pressed": "#1E2228",
    "accent": "#7B6CF0",
    "accent_hover": "#9588F5",
    "accent_pressed": "#5B4FC7",
    "scrollbar": "#3D4450",
    "scrollbar_hover": "#6B7280",
    "tooltip_bg": "#272C34",
    "tooltip_text": "#E8EAED",
    "page_ink": "#E8EAED",
    "page_paper": "#1E2228",
    "link": "#9588F5",
}

THEMES: Dict[str, Dict[str, str]] = {
    "dark": DARK,
    "light": LIGHT,
    "high_contrast": HIGH_CONTRAST,
    "sepia": SEPIA,
    "night": NIGHT,
    "midnight": MIDNIGHT,
    "paper": PAPER,
    "slate": SLATE,
}
DEFAULT_THEME: ThemeName = "normal"
THEME_ORDER: tuple[str, ...] = (
    "normal",
    "dark",
    "light",
    "high_contrast",
    "sepia",
    "night",
    "midnight",
    "paper",
    "slate",
)


def get_palette(name: str | None = None) -> Dict[str, str]:
    key = (name or DEFAULT_THEME).lower()
    if key == "normal":
        # No theme — neutral fallback used only for property reads (no QSS applied)
        return LIGHT.copy()
    return THEMES.get(key, DARK).copy()


def hex_to_rgb(value: str) -> Tuple[int, int, int]:
    """Parse #RGB / #RRGGBB into 0–255 RGB tuple."""
    h = (value or "").strip().lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    if len(h) != 6:
        return (192, 202, 245)
    try:
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    except ValueError:
        return (192, 202, 245)


def page_colors_for_theme(name: str | None = None) -> Dict[str, str]:
    """Ink + paper hex colors used to recolor document pixels for a theme."""
    p = get_palette(name)
    return {
        "ink": p.get("page_ink") or p.get("text") or "#C0CAF5",
        "paper": p.get("page_paper") or p.get("window") or "#1A1B26",
        "link": p.get("link") or p.get("accent") or REMEDY_ACCENT,
        "canvas_text": p.get("canvas_text") or p.get("text_muted") or p.get("text"),
    }


def theme_is_dark(name: str | None = None) -> bool:
    """True when the theme's page paper is dark (for default invert-style mapping)."""
    paper = page_colors_for_theme(name)["paper"]
    r, g, b = hex_to_rgb(paper)
    # Perceived luminance
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) < 140


def apply_qt_palette(app, theme: str | Dict[str, str] | None = None) -> None:
    """Push theme text/background colors into QPalette so native text follows theme."""
    try:
        from PyQt5.QtGui import QColor, QPalette
    except ImportError:
        return
    p = get_palette(theme) if isinstance(theme, str) or theme is None else theme

    def qc(key: str, fallback: str = "#FFFFFF") -> "QColor":
        return QColor(p.get(key) or fallback)

    pal = QPalette()
    window = qc("window", "#1A1B26")
    text = qc("text", "#C0CAF5")
    muted = qc("text_muted", "#9AA5CE")
    dim = qc("text_dim", "#565F89")
    panel = qc("panel", "#24283B")
    input_bg = qc("input_bg", "#1F2335")
    accent = qc("accent", REMEDY_ACCENT)
    sel_text = qc("selection_text", "#FFFFFF")
    link = qc("link", REMEDY_ACCENT)
    tooltip_bg = qc("tooltip_bg", "#24283B")
    tooltip_text = qc("tooltip_text", "#C0CAF5")

    pal.setColor(QPalette.Window, window)
    pal.setColor(QPalette.WindowText, text)
    pal.setColor(QPalette.Base, input_bg)
    pal.setColor(QPalette.AlternateBase, panel)
    pal.setColor(QPalette.Text, text)
    pal.setColor(QPalette.BrightText, sel_text)
    pal.setColor(QPalette.Button, qc("button_bg", "#2A2F45"))
    pal.setColor(QPalette.ButtonText, text)
    pal.setColor(QPalette.Highlight, accent)
    pal.setColor(QPalette.HighlightedText, sel_text)
    pal.setColor(QPalette.ToolTipBase, tooltip_bg)
    pal.setColor(QPalette.ToolTipText, tooltip_text)
    pal.setColor(QPalette.Link, link)
    pal.setColor(QPalette.LinkVisited, muted)
    pal.setColor(QPalette.PlaceholderText, dim)

    for group in (QPalette.Disabled, QPalette.Inactive):
        pal.setColor(group, QPalette.WindowText, dim)
        pal.setColor(group, QPalette.Text, dim)
        pal.setColor(group, QPalette.ButtonText, dim)
        pal.setColor(group, QPalette.HighlightedText, muted)

    try:
        app.setPalette(pal)
    except Exception:  # noqa: BLE001
        pass


def build_stylesheet(theme: str | Dict[str, str] | None = None) -> str:
    """Full application QSS — windows, menus, toolbars, forms, scrollbars.

    "normal" is the no-theme mode: returns an empty stylesheet so the app
    keeps the native system look.
    """
    if isinstance(theme, str) and theme.lower() == "normal":
        return ""
    p = get_palette(theme) if isinstance(theme, str) or theme is None else theme
    link = p.get("link") or p.get("accent") or REMEDY_ACCENT

    return f"""
/* ===== RemedyPDF — {p['name']} theme ===== */
QWidget {{
    background-color: {p['window']};
    color: {p['text']};
    font-family: "Segoe UI", "SF Pro Text", "Helvetica Neue", "Noto Sans", sans-serif;
    font-size: 13px;
    /* Improve glyph clarity on mixed DPI */
    font-weight: 400;
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
QLabel#dimLabel, QLabel[cssClass="dim"] {{
    color: {p['text_dim']};
}}
QLabel#accentLabel, QLabel[cssClass="accent"] {{
    color: {p['accent']};
}}
QLabel a, QTextBrowser a, QTextEdit a {{
    color: {link};
}}
QStatusBar {{
    background-color: {p['status_bg']};
    color: {p['text_muted']};
    border-top: 1px solid {p['border_soft']};
    padding: 4px 10px;
    font-size: 12px;
}}
QStatusBar QLabel {{
    color: {p['text_muted']};
    background: transparent;
}}
QStatusBar::item {{
    border: none;
}}
/* Readable chrome labels */
QLabel#zoomLabel, QLabel#statusHint {{
    color: {p['text_muted']};
    font-weight: 500;
    padding: 0 6px;
}}
/* Menu / toolbar text always follows theme (guards against native palette bleed) */
QMenuBar, QMenuBar::item, QMenu, QMenu::item, QToolBar, QToolButton {{
    color: {p['text']};
}}
QHeaderView::section {{
    background-color: {p['panel']};
    color: {p['text']};
    border: 1px solid {p['border_soft']};
    padding: 6px 8px;
}}
QTabBar::tab {{
    background: {p['panel_alt']};
    color: {p['text_muted']};
    padding: 8px 14px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}}
QTabBar::tab:selected {{
    background: {p['panel']};
    color: {p['text']};
}}
QCheckBox, QRadioButton {{
    color: {p['text']};
    spacing: 8px;
}}
QCheckBox:disabled, QRadioButton:disabled {{
    color: {p['text_dim']};
}}
QGroupBox {{
    color: {p['text']};
    border: 1px solid {p['border_soft']};
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 8px;
}}
QGroupBox::title {{
    color: {p['text_muted']};
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
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
/* Placeholder / empty-state text on canvas follows theme text color */
QLabel#pdfCanvas[empty="true"] {{
    color: {p['canvas_text']};
}}

/* ----- Dialogs / message boxes ----- */
QMessageBox, QInputDialog, QDialog {{
    background-color: {p['panel']};
    color: {p['text']};
}}
QMessageBox QLabel, QInputDialog QLabel, QDialog QLabel {{
    color: {p['text']};
    background: transparent;
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
    color: {p['text']};
}}
QWidget#pageNavigator QLabel {{
    color: {p['text_muted']};
}}
QWidget#pageNavigator QSpinBox {{
    color: {p['text']};
    background-color: {p['input_bg']};
}}

/* ----- Search bar ----- */
QWidget#searchBar {{
    background-color: {p['panel']};
    border-bottom: 1px solid {p['border_soft']};
    color: {p['text']};
}}
QWidget#searchBar QLabel {{
    color: {p['text']};
}}
QWidget#searchBar QLabel#mutedLabel {{
    color: {p['text_muted']};
}}
QLineEdit#searchField {{
    background-color: {p['input_bg']};
    color: {p['text']};
    border: 1px solid {p['input_border']};
    border-radius: 8px;
    padding: 8px 12px;
    min-width: 220px;
}}
QLineEdit#searchField:focus {{
    border: 1px solid {p['accent']};
}}
/* Placeholder text color (Qt 5.15+ supports this in some styles) */
QLineEdit {{
    selection-background-color: {p['selection']};
    selection-color: {p['selection_text']};
}}
"""


def apply_theme(app, theme_name: str = DEFAULT_THEME, *, mobile: bool | None = None) -> str:
    """Apply stylesheet + QPalette text colors. Returns theme name.

    When mobile is True (or auto-detected), appends APK/touch-friendly QSS extras.
    Text roles (WindowText, Text, ButtonText, PlaceholderText, Link) follow the theme.
    """
    name = (theme_name or DEFAULT_THEME).lower()
    if name == "normal":
        # No theme — plain system look: clear QSS + palette, no recolor.
        try:
            app.setStyleSheet("")
        except Exception:  # noqa: BLE001
            pass
        try:
            app.setPalette(app.style().standardPalette())
        except Exception:  # noqa: BLE001
            pass
        try:
            app.setProperty("remedyTheme", "normal")
            app.setProperty("remedyMobile", False)
            app.setProperty("remedyPageInk", None)
            app.setProperty("remedyPagePaper", None)
        except Exception:  # noqa: BLE001
            pass
        return "normal"
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
    # Palette first so widgets that ignore partial QSS still get themed text
    apply_qt_palette(app, name)
    app.setStyleSheet(css)
    try:
        app.setProperty("remedyTheme", name)
        app.setProperty("remedyMobile", use_mobile)
        colors = page_colors_for_theme(name)
        app.setProperty("remedyPageInk", colors["ink"])
        app.setProperty("remedyPagePaper", colors["paper"])
    except Exception:  # noqa: BLE001
        pass
    return name


def toggle_theme(current: str) -> str:
    """Cycle through all visibility themes (dark → light → HC → sepia → night → …)."""
    cur = (current or DEFAULT_THEME).lower()
    try:
        idx = THEME_ORDER.index(cur)
    except ValueError:
        idx = 0
    return THEME_ORDER[(idx + 1) % len(THEME_ORDER)]


def theme_label(name: str) -> str:
    return THEME_LABELS.get((name or "").lower(), name or DEFAULT_THEME)


def list_themes() -> tuple[str, ...]:
    return THEME_ORDER


def page_filter_label(name: str) -> str:
    return PAGE_FILTER_LABELS.get((name or "none").lower(), name or "none")


def list_page_filters() -> tuple[str, ...]:
    return tuple(PAGE_FILTER_LABELS.keys())
