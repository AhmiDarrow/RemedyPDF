"""UI package — themes, widgets, About."""

from .theme import DEFAULT_THEME, apply_theme, toggle_theme
from .widgets import PDFCanvas, PageNavigator, SearchBar
from .about import AboutDialog

__all__ = [
    "DEFAULT_THEME",
    "apply_theme",
    "toggle_theme",
    "PDFCanvas",
    "PageNavigator",
    "SearchBar",
    "AboutDialog",
]
