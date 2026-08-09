"""Utility helpers for RemedyPDF."""

from .brand import (
    apply_app_icon,
    brand_assets,
    icon_ico_path,
    icon_path,
    logo_path,
    logo_ui_path,
)
from .paths import project_root, resources_dir
from .updater import (
    check_for_update,
    compare_versions,
    fetch_latest_json,
    format_update_message,
    open_url,
    update_status_message,
)
from .mobile import (
    apply_mobile_attribute,
    is_android,
    is_mobile,
    is_touch_primary,
    mobile_stylesheet_extras,
    recommended_default_zoom,
    recommended_window_size,
    touch_target_px,
)

__all__ = [
    "project_root",
    "resources_dir",
    "apply_app_icon",
    "brand_assets",
    "icon_ico_path",
    "icon_path",
    "logo_path",
    "logo_ui_path",
    "check_for_update",
    "compare_versions",
    "fetch_latest_json",
    "format_update_message",
    "update_status_message",
    "open_url",
    "apply_mobile_attribute",
    "is_android",
    "is_mobile",
    "is_touch_primary",
    "mobile_stylesheet_extras",
    "recommended_default_zoom",
    "recommended_window_size",
    "touch_target_px",
]
