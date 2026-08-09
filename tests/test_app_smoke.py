import os

import pytest

# Headless-friendly for CI / smoke
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt5")


def test_create_app_smoke():
    from core.app import create_app

    app, window = create_app([])
    assert app is not None
    assert window.windowTitle().startswith("RemedyPDF")
    window.close()
    app.quit()


def test_main_importable():
    import main as main_mod

    assert callable(main_mod.main)
