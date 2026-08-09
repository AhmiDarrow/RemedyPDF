"""Brand asset wiring tests."""

from pathlib import Path

from utils.brand import (
    about_mark_path,
    apply_app_icon,
    brand_assets,
    brand_files_present,
    icon_ico_path,
    icon_path,
    logo_path,
    logo_ui_path,
    required_brand_files,
    resources_dir,
    window_icon_path,
)


def test_resources_dir_exists():
    res = resources_dir()
    assert res.is_dir()
    assert res.name == "resources"


def test_core_brand_files_present():
    present = brand_files_present()
    assert present.get("icon.png") is True
    assert present.get("icon.ico") is True
    assert present.get("logo.png") is True
    assert present.get("logo_ui.png") is True


def test_required_brand_files():
    files = required_brand_files()
    assert files
    missing = [p for p in files if not p.is_file()]
    assert missing == [], f"missing brand files: {missing}"


def test_icon_and_logo_paths():
    assert icon_path().is_file()
    assert icon_ico_path().is_file()
    assert logo_path().is_file()
    assert logo_ui_path().is_file()
    assert window_icon_path() is not None
    assert about_mark_path() is not None


def test_brand_assets_dict():
    assets = brand_assets()
    assert isinstance(assets, dict)
    assert "icon.png" in assets or "icon" in assets or len(assets) >= 4


def test_apply_app_icon_smoke():
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt5.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    ok = apply_app_icon(app)
    assert ok is True
    icon = app.windowIcon()
    assert icon is not None and not icon.isNull()
