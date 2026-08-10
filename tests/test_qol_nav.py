"""QoL nav pass: wheel page-flip, mouse side-button nav, view rotation, close doc."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt5")


def _make_pdf(tmp_path, pages=3, width=300, height=400):
    import fitz

    path = tmp_path / "doc.pdf"
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page(width=width, height=height)
        page.insert_text((40, 40), f"PAGE {i + 1}", fontsize=24)
    doc.save(path)
    doc.close()
    return str(path)


def _app(tmp_path, pages=3):
    from core.app import create_app

    app, window = create_app([])
    window.open_document(_make_pdf(tmp_path, pages=pages))
    return app, window


def _wheel(angle_x=0, angle_y=-120, modifiers=0):
    from PyQt5.QtCore import QPoint, QPointF, Qt
    from PyQt5.QtGui import QWheelEvent

    return QWheelEvent(
        QPointF(50, 50),
        QPointF(50, 50),
        QPoint(0, 0),
        QPoint(angle_x, angle_y),
        Qt.NoButton,
        Qt.KeyboardModifiers(modifiers),
        Qt.NoScrollPhase,
        False,
    )


def _press(button):
    from PyQt5.QtCore import QEvent, QPointF, Qt
    from PyQt5.QtGui import QMouseEvent

    return QMouseEvent(
        QEvent.MouseButtonPress, QPointF(10, 10), button, button, Qt.NoModifier
    )


def test_wheel_flips_page_when_page_fits(tmp_path):
    """Plain wheel flips pages in fit view; Ctrl+wheel stays zoom territory."""
    from PyQt5.QtCore import Qt

    app, window = _app(tmp_path, pages=3)
    window.engine.set_zoom(0.1)  # tiny page → nothing to scroll
    assert window.engine.current_page == 0
    assert window._wheel_flips_page(_wheel(angle_y=-120)) is True
    assert window.engine.current_page == 1
    assert window._wheel_flips_page(_wheel(angle_y=120)) is True
    assert window.engine.current_page == 0
    # Horizontal swipe flips forward
    assert window._wheel_flips_page(_wheel(angle_x=-120)) is True
    assert window.engine.current_page == 1
    # Ctrl+wheel must NOT be consumed by page flip
    assert (
        window._wheel_flips_page(
            _wheel(angle_y=-120, modifiers=int(Qt.ControlModifier))
        )
        is False
    )
    assert window.engine.current_page == 1
    window.close()
    app.quit()


def test_wheel_does_not_flip_when_scrolling_inside_zoomed_page(tmp_path):
    app, window = _app(tmp_path, pages=2)
    window.engine.set_zoom(4.0)  # zoomed in → vertical scrollbar exists
    window.render_current()
    vbar = window.scroll.verticalScrollBar()
    if vbar.maximum() <= vbar.minimum():
        window.close()
        app.quit()
        pytest.skip("viewport larger than zoomed page — no scrollbar")
    vbar.setValue(vbar.maximum())  # at bottom edge
    before = window.engine.current_page
    # Wheel down at the bottom edge flips to the next page
    assert window._wheel_flips_page(_wheel(angle_y=-120)) is True
    assert window.engine.current_page == before + 1
    # Mid-scroll wheel must scroll, not flip
    vbar.setValue(vbar.minimum())
    before = window.engine.current_page
    assert window._wheel_flips_page(_wheel(angle_y=-120)) is False
    assert window.engine.current_page == before
    window.close()
    app.quit()


def test_mouse_side_buttons_flip_pages(tmp_path):
    from PyQt5.QtCore import Qt

    app, window = _app(tmp_path, pages=3)
    assert window.engine.current_page == 0
    # Forward button (XButton2) → next page
    assert window.eventFilter(window.canvas, _press(Qt.XButton2)) is True
    assert window.engine.current_page == 1
    # Back button (XButton1) → previous page
    assert window.eventFilter(window.canvas, _press(Qt.XButton1)) is True
    assert window.engine.current_page == 0
    window.close()
    app.quit()


def test_close_document(tmp_path):
    app, window = _app(tmp_path, pages=2)
    assert window.engine.is_open
    window.close_document()
    assert not window.engine.is_open
    assert window.engine.page_count == 0
    assert window.current_path is None
    # Reopen works after closing
    window.open_document(_make_pdf(tmp_path, pages=1))
    assert window.engine.is_open
    assert window.engine.page_count == 1
    window.close()
    app.quit()


def test_rotate_view_size_and_edit_mapping(tmp_path):
    from core.pdf_engine import PDFEngine

    eng = PDFEngine()
    assert eng.open(_make_pdf(tmp_path, pages=1))
    assert eng.get_view_size_at_zoom(1.0) == pytest.approx((300.0, 400.0))
    eng.rotate_right()
    assert eng.rotation == 90
    assert eng.get_view_size_at_zoom(1.0) == pytest.approx((400.0, 300.0))
    # View point (200, 150) ↔ page point (150, 200) under clockwise rotation
    page, px, py = eng.map_view_xy_to_page(200.0, 150.0)
    assert page == 0
    assert px == pytest.approx(150.0, abs=1.0)
    assert py == pytest.approx(200.0, abs=1.0)
    # 180 keeps aspect; rotate_left back to 90; then 270 swaps again
    eng.rotate_right()
    assert eng.rotation == 180
    assert eng.get_view_size_at_zoom(1.0) == pytest.approx((300.0, 400.0))
    eng.rotate_left()
    assert eng.rotation == 90
    assert eng.get_view_size_at_zoom(1.0) == pytest.approx((400.0, 300.0))
    eng.set_rotation(0)
    eng.rotate_left()
    assert eng.rotation == 270
    assert eng.get_view_size_at_zoom(1.0) == pytest.approx((400.0, 300.0))
    eng.close()


def test_rotation_render_direction_is_clockwise(tmp_path):
    """Text at page top-left must land top-RIGHT of the rotated render."""
    import fitz
    from core.pdf_engine import PDFEngine

    path = tmp_path / "mark.pdf"
    doc = fitz.open()
    page = doc.new_page(width=300, height=400)
    page.insert_text((40, 40), "X", fontsize=36, color=(0, 0, 0))
    doc.save(path)
    doc.close()

    eng = PDFEngine()
    assert eng.open(str(path))
    eng.set_zoom(1.0)
    w, h, data = eng.render_view_rgb()
    assert (w, h) == (300, 400)

    eng.rotate_right()
    w2, h2, data2 = eng.render_view_rgb()
    assert (w2, h2) == (400, 300)

    def dark_quadrant(data, w, h, qx, qy):
        x0, x1 = (0, w // 2) if qx == 0 else (w // 2, w)
        y0, y1 = (0, h // 2) if qy == 0 else (h // 2, h)
        n = 0
        for y in range(y0, y1, 2):
            row = y * w * 3
            for x in range(x0, x1, 2):
                off = row + x * 3
                if data[off] < 128 and data[off + 1] < 128 and data[off + 2] < 128:
                    n += 1
        return n

    tr = dark_quadrant(data2, w2, h2, 1, 0)
    tl = dark_quadrant(data2, w2, h2, 0, 0)
    assert tr > 0, "rotated mark should appear top-right (clockwise)"
    assert tl == 0, "top-left must be empty after clockwise rotation"
    eng.close()


def test_extra_formats_in_picker_and_engine():
    from core.pdf_engine import OPEN_FILTER, SUPPORTED_EXTENSIONS

    for ext in (".svg", ".docx", ".mobi", ".png", ".jpg", ".webp", ".tiff", ".cbr"):
        assert ext in SUPPORTED_EXTENSIONS, ext
    for pat in ("*.svg", "*.docx", "*.mobi", "*.png", "*.webp", "*.cbr"):
        assert pat in OPEN_FILTER, pat
    assert "Word (*.docx)" in OPEN_FILTER
    assert "Images (*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.webp)" in OPEN_FILTER


def test_qol_api_surface():
    import inspect

    from core import app as app_mod

    src = inspect.getsource(app_mod.RemedyPDFApp)
    for name in (
        "_wheel_flips_page",
        "close_document",
        "_goto_page_dialog",
        "rotate_right",
        "rotate_left",
    ):
        assert f"def {name}" in src, name
    assert 'QShortcut(QKeySequence("Ctrl+G")' in src
    assert 'QShortcut(QKeySequence("Ctrl+W")' in src
    assert 'QShortcut(QKeySequence("Ctrl+R")' in src
    assert 'QShortcut(QKeySequence("Alt+Left")' in src
    # Side buttons handled in eventFilter
    assert "Qt.XButton1" in src
    assert "Qt.XButton2" in src
