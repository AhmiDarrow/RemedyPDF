"""Mobile QoL pass: tap zones, pinch zoom wiring, reader mode, buildozer config."""

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt5")

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def qapp():
    """One QApplication for canvas tests (Qt aborts without one)."""
    from PyQt5.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app
    app.quit()


# ----- pure helper: tap zones -----


def test_tap_zone_for_edges_and_middle():
    from utils.mobile import tap_zone_for

    assert tap_zone_for(0, 1000) == -1  # far left -> prev
    assert tap_zone_for(50, 1000) == -1  # left edge
    assert tap_zone_for(500, 1000) == 0  # middle -> nothing
    assert tap_zone_for(699, 1000) == 0  # just inside the middle (zone starts at 70%)
    assert tap_zone_for(700, 1000) == 1  # right edge zone
    assert tap_zone_for(949, 1000) == 1  # deep in the right zone
    assert tap_zone_for(1000, 1000) == 1
    assert tap_zone_for(10, 0) == 0  # degenerate width -> safe no-op


# ----- canvas gestures -----


def test_canvas_exposes_mobile_gestures(qapp):
    """Pinch is grabbed in __init__ and the mobile signals exist + are
    connectable. PyQt5 exposes no QWidget.gesture() getter, so we verify the
    pieces the gesture path needs: signals and touch acceptance."""
    from PyQt5.QtCore import Qt
    from ui.widgets import PDFCanvas

    canvas = PDFCanvas()
    for sig in ("tap_zone", "pinch_zoom", "pinch_finished"):
        assert hasattr(canvas, sig)
    assert canvas.testAttribute(Qt.WA_AcceptTouchEvents)
    canvas.deleteLater()


def _click(canvas, x, y, press=True):
    from PyQt5.QtCore import QEvent, QPointF, Qt
    from PyQt5.QtGui import QMouseEvent

    etype = QEvent.MouseButtonPress if press else QEvent.MouseButtonRelease
    button = Qt.LeftButton if press else Qt.LeftButton
    return QMouseEvent(
        etype, QPointF(x, y), button, button, Qt.NoModifier
    )


def test_tap_zone_release_emits_direction(qapp):
    """Touch-mode quick tap on the right edge emits +1, left edge -1; a drag
    or a desktop-mode tap must never emit."""
    from ui.widgets import PDFCanvas

    canvas = PDFCanvas()
    canvas.resize(1000, 800)
    canvas.set_touch_mode(True)
    zones = []
    canvas.tap_zone.connect(zones.append)

    canvas.mousePressEvent(_click(canvas, 950, 400))
    canvas.mouseReleaseEvent(_click(canvas, 950, 400, press=False))
    assert zones == [1]

    zones.clear()
    canvas.mousePressEvent(_click(canvas, 40, 400))
    canvas.mouseReleaseEvent(_click(canvas, 40, 400, press=False))
    assert zones == [-1]

    # Middle tap -> nothing
    zones.clear()
    canvas.mousePressEvent(_click(canvas, 500, 400))
    canvas.mouseReleaseEvent(_click(canvas, 500, 400, press=False))
    assert zones == []

    # Drag (moved > 12 px) -> no tap
    from PyQt5.QtCore import QEvent, QPointF, Qt
    from PyQt5.QtGui import QMouseEvent

    zones.clear()
    canvas.mousePressEvent(_click(canvas, 950, 400))
    move = QMouseEvent(
        QEvent.MouseMove, QPointF(700, 400), Qt.NoButton, Qt.NoButton, Qt.NoModifier
    )
    canvas.mouseMoveEvent(move)
    canvas.mouseReleaseEvent(_click(canvas, 700, 400, press=False))
    assert zones == []

    # Desktop mode (no touch) -> taps never emit
    canvas.set_touch_mode(False)
    zones.clear()
    canvas.mousePressEvent(_click(canvas, 950, 400))
    canvas.mouseReleaseEvent(_click(canvas, 950, 400, press=False))
    assert zones == []
    canvas.deleteLater()


# ----- app wiring -----


def _pdf(tmp_path, pages=3):
    import fitz

    path = tmp_path / "doc.pdf"
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page(width=300, height=400)
        page.insert_text((40, 40), f"PAGE {i + 1}", fontsize=24)
    doc.save(path)
    doc.close()
    return str(path)


def test_tap_zone_flips_pages(tmp_path):
    from core.app import create_app

    app, window = create_app([])
    window.open_document(_pdf(tmp_path, pages=3))
    assert window.engine.current_page == 0
    window._on_tap_zone(1)
    assert window.engine.current_page == 1
    window._on_tap_zone(-1)
    assert window.engine.current_page == 0
    window._on_tap_zone(0)  # middle -> no-op
    assert window.engine.current_page == 0
    window.close()
    app.quit()


def test_pinch_zoom_changes_zoom(tmp_path):
    from core.app import create_app

    app, window = create_app([])
    window.open_document(_pdf(tmp_path, pages=1))
    before = window.engine.zoom
    window._on_pinch_zoom(1.5, 150, 200)
    assert window.engine.zoom == pytest.approx(before * 1.5)
    window._on_pinch_finished()  # flush the debounced render without error
    window.close()
    app.quit()


def test_reader_mode_toggles_chrome(tmp_path):
    from core.app import create_app

    app, window = create_app([])
    window.open_document(_pdf(tmp_path, pages=1))
    window._set_reader_mode(True)
    assert window._reader_mode is True
    assert window.toolbar.isHidden() is True
    assert window.navigator.isHidden() is True
    # Esc-style exit restores the chrome
    window._exit_fullscreen_if_needed()
    assert window._reader_mode is False
    assert window.toolbar.isVisible() is True
    assert window.navigator.isVisible() is True
    window.close()
    app.quit()


def test_buildozer_matches_version_and_orientation():
    from src import __version__

    text = (ROOT / "buildozer.spec").read_text(encoding="utf-8")
    assert f"version = {__version__}" in text
    assert "orientation = all" in text
    assert "fullscreen = 1" in text
