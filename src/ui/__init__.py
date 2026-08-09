"""UI package — themes, widgets, About."""

from .theme import (
    DEFAULT_THEME,
    THEME_ORDER,
    apply_theme,
    list_page_filters,
    list_themes,
    page_colors_for_theme,
    page_filter_label,
    theme_is_dark,
    theme_label,
    toggle_theme,
)
from .widgets import PDFCanvas, PageNavigator, SearchBar
from .about import AboutDialog

__all__ = [
    "DEFAULT_THEME",
    "THEME_ORDER",
    "apply_theme",
    "list_page_filters",
    "list_themes",
    "page_colors_for_theme",
    "page_filter_label",
    "theme_is_dark",
    "theme_label",
    "toggle_theme",
    "PDFCanvas",
    "PageNavigator",
    "SearchBar",
    "AboutDialog",
]
