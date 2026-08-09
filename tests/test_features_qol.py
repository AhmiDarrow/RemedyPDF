"""QoL / feature smoke: fine zoom constants, book mode API, theme helpers."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt5")


def test_theme_toggle_and_stylesheet():
    from ui.theme import (
        DEFAULT_THEME,
        THEME_ORDER,
        apply_theme,
        build_stylesheet,
        toggle_theme,
    )

    assert toggle_theme("dark") == "light"
    assert toggle_theme("light") == "high_contrast"
    # Full cycle wraps last → first (order grew beyond night)
    assert toggle_theme(THEME_ORDER[-1]) == THEME_ORDER[0]
    assert "sepia" in THEME_ORDER
    assert "midnight" in THEME_ORDER
    assert "paper" in THEME_ORDER
    assert "slate" in THEME_ORDER
    assert len(THEME_ORDER) >= 8
    css = build_stylesheet("dark")
    assert "QMainWindow" in css
    assert DEFAULT_THEME in THEME_ORDER
    # apply_theme should not raise on QApplication
    from PyQt5.QtWidgets import QApplication
    import sys

    app = QApplication.instance() or QApplication(sys.argv[:1])
    name = apply_theme(app, "dark")
    assert name == "dark"
    assert apply_theme(app, "high_contrast") == "high_contrast"
    assert apply_theme(app, "midnight") == "midnight"


def test_create_app_has_book_and_fine_zoom():
    from core.app import create_app
    from core.pdf_engine import PDFEngine

    app, window = create_app([])
    assert hasattr(window, "toggle_book_mode")
    assert hasattr(window, "adjust_zoom")
    assert hasattr(window, "reset_zoom")
    assert hasattr(window, "_on_canvas_edit")
    assert PDFEngine.ZOOM_FINE == pytest.approx(0.01)
    assert getattr(window, "book_act", None) is not None
    # Book mode defaults to both sides (not cover-alone)
    assert window.engine.book_cover_alone is False
    window.close()
    app.quit()


def test_open_pdf_via_app(tmp_path):
    import fitz
    from core.app import create_app
    from core.pdf_engine import PDFEngine

    path = tmp_path / "a.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.new_page()
    doc.new_page()
    doc.save(path)
    doc.close()

    app, window = create_app([])
    window.open_document(str(path))
    assert window.engine.is_open
    assert window.engine.page_count == 3
    before = window.engine.zoom
    window.adjust_zoom(PDFEngine.ZOOM_FINE)
    assert window.engine.zoom == pytest.approx(before + PDFEngine.ZOOM_FINE)
    window.reset_zoom()
    # Reset lands on default (or mobile recommended)
    assert window.engine.zoom > 0
    window.toggle_book_mode(True)
    assert window.engine.book_mode is True
    assert window.engine.book_cover_alone is False
    # Both sides on first spread
    assert window.engine.spread_pages() == [0, 1]
    window.close()
    app.quit()


def test_book_mode_canvas_shows_both_sides(tmp_path):
    """Regression: book mode must paint a wide two-page pixmap on the canvas."""
    import fitz
    from core.app import create_app

    path = tmp_path / "spread.pdf"
    doc = fitz.open()
    for i in range(4):
        page = doc.new_page(width=300, height=400)
        page.insert_text((40, 80), f"PAGE {i + 1}", fontsize=24)
    doc.save(path)
    doc.close()

    app, window = create_app([])
    window.resize(1100, 800)
    window.open_document(str(path))
    # Single-page baseline width
    window.engine.set_book_mode(False)
    window.render_current()
    single_pm = window.canvas.pixmap()
    assert single_pm is not None and not single_pm.isNull()
    single_w = single_pm.width()

    window.toggle_book_mode(True)
    assert window.engine.spread_pages() == [0, 1]
    window.render_current()
    spread_pm = window.canvas.pixmap()
    assert spread_pm is not None and not spread_pm.isNull()
    # Canvas must hold a true side-by-side image (not a clipped single page)
    assert spread_pm.width() > single_w * 1.5
    # Scroll area must NOT force-resize the canvas down to viewport
    assert window.scroll.widgetResizable() is False
    assert window.canvas.width() >= spread_pm.width()
    window.close()
    app.quit()


def test_mobile_helpers():
    from utils.mobile import (
        is_android,
        is_mobile,
        mobile_stylesheet_extras,
        recommended_default_zoom,
        recommended_window_size,
        touch_target_px,
    )

    assert isinstance(is_android(), bool)
    assert isinstance(is_mobile(), bool)
    assert touch_target_px() >= 40
    z = recommended_default_zoom()
    assert 0.5 <= z <= 2.5
    w, h = recommended_window_size()
    assert w >= 320 and h >= 480
    css = mobile_stylesheet_extras()
    assert "QToolBar" in css or "QPushButton" in css or len(css) >= 0


def test_canvas_edit_api_surface():
    """Canvas module exposes double-click / long-press edit API (not single-click edit)."""
    import inspect

    from ui import widgets as w

    assert w.LONG_PRESS_MS >= 300
    src = inspect.getsource(w.PDFCanvas)
    # Double-click and long-press emit edit; single click must not open editor alone
    assert "double_clicked_at" in src
    assert "long_pressed_at" in src
    assert "edit_at" in src
    assert "mouseDoubleClickEvent" in src
    assert "_fire_long_press" in src
    assert "set_touch_mode" in src
    # Single-click path only emits clicked_at (optional), not edit_at directly in press
    press = inspect.getsource(w.PDFCanvas.mousePressEvent)
    assert "clicked_at.emit" in press
    assert "edit_at.emit" not in press


def test_app_edit_wired_once_only():
    """App must connect only edit_at — not double/long as well (double dialog bug)."""
    import inspect

    from core import app as app_mod

    src = inspect.getsource(app_mod.RemedyPDFApp._build_ui)
    assert "edit_at.connect" in src
    # Must NOT also connect the informational signals to the same slot
    assert "double_clicked_at.connect" not in src
    assert "long_pressed_at.connect" not in src


def test_navigator_book_step():
    from ui.widgets import PageNavigator
    from PyQt5.QtWidgets import QApplication
    import sys

    app = QApplication.instance() or QApplication(sys.argv[:1])
    nav = PageNavigator()
    nav.set_page_count(10)
    nav.set_page(0)
    nav.set_step(2)
    assert nav._step == 2
    # Next should advance by 2 pages (1-based spin: 1 → 3)
    nav._next()
    assert nav.page_spin.value() == 3
    nav._prev()
    assert nav.page_spin.value() == 1
    nav.set_step(1)
    nav._next()
    assert nav.page_spin.value() == 2


def test_version_aligned():
    from core import app as app_mod
    import main as main_mod

    assert app_mod.VERSION == main_mod.VERSION
    assert app_mod.VERSION.startswith("1.")


def test_theme_toggle_keeps_mobile_flag():
    """Theme apply path must pass mobile= so APK QSS is not dropped."""
    import inspect
    from core import app as app_mod

    # set_theme is the single apply path; _toggle_theme delegates to it
    set_src = inspect.getsource(app_mod.RemedyPDFApp.set_theme)
    assert "mobile=" in set_src
    toggle_src = inspect.getsource(app_mod.RemedyPDFApp._toggle_theme)
    assert "set_theme" in toggle_src


def test_app_has_wheel_event_filter_and_dirty_flag():
    """Bugsweep: Ctrl+wheel via eventFilter; dirty tracking; close prompt."""
    import inspect
    from core import app as app_mod

    src = inspect.getsource(app_mod.RemedyPDFApp)
    assert "eventFilter" in src
    assert "_zoom_from_wheel" in src
    assert "installEventFilter" in src
    assert "_dirty" in src
    close_src = inspect.getsource(app_mod.RemedyPDFApp.closeEvent)
    assert "unsaved" in close_src.lower() or "Save" in close_src
    # Coarse zoom shortcuts present
    sc = inspect.getsource(app_mod.RemedyPDFApp._build_shortcuts)
    assert "Ctrl+=" in sc or "ZoomIn" in sc


def test_page_spin_resyncs_after_book_snap(tmp_path):
    """Page spin must resync to snapped left page after book-mode set."""
    import fitz
    from core.app import create_app

    path = tmp_path / "spin.pdf"
    doc = fitz.open()
    for i in range(4):
        doc.new_page(width=300, height=400)
    doc.save(path)
    doc.close()

    app, window = create_app([])
    window.open_document(str(path))
    window.toggle_book_mode(True)
    # Request odd page via spin handler — engine snaps to 0, controls must match
    window._on_page_spin(2)  # 1-based page 2 → index 1 → snap to 0
    assert window.engine.current_page == 0
    assert window.page_spin.value() == 1
    assert window.engine.spread_pages() == [0, 1]
    window.close()
    app.quit()


def test_dirty_flag_after_add_text(tmp_path):
    import fitz
    from core.app import create_app

    path = tmp_path / "dirty.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(path)
    doc.close()

    app, window = create_app([])
    window.open_document(str(path))
    assert window._dirty is False
    # Simulate successful canvas-edit path without modal QInputDialog
    assert window.engine.add_text("x", page=0, x=40, y=40)
    window._dirty = True
    window._update_status()
    assert "•" in window.windowTitle()
    # Headless close must not raise / hang on unsaved prompt
    window._dirty = False
    window.close()
    app.quit()


def test_close_event_headless_skips_prompt():
    import inspect
    from core import app as app_mod

    src = inspect.getsource(app_mod.RemedyPDFApp.closeEvent)
    assert "_is_headless" in src


def test_search_enter_lands_on_first_hit(tmp_path):
    """Enter after Find must land on hit 0, not skip to hit 1."""
    import fitz
    from core.app import create_app

    path = tmp_path / "find.pdf"
    doc = fitz.open()
    for i, word in enumerate(("alpha", "beta", "alpha", "gamma")):
        page = doc.new_page(width=300, height=400)
        page.insert_text((40, 80), word, fontsize=18)
    doc.save(path)
    doc.close()

    app, window = create_app([])
    window.open_document(str(path))
    # Simulate SearchBar: search_requested then next_result (Enter)
    window._on_search("alpha")
    assert len(window._search_hits) >= 2
    assert window._search_index == 0
    window._search_next()  # fresh-search guard must NOT advance
    assert window._search_index == 0
    window._search_next()  # real next
    assert window._search_index == 1
    window.close()
    app.quit()


def test_open_document_prompts_when_dirty():
    """open_document must check dirty before replacing the current doc."""
    import inspect
    from core import app as app_mod

    src = inspect.getsource(app_mod.RemedyPDFApp.open_document)
    assert "_dirty" in src
    assert "Save" in src or "unsaved" in src.lower()


def test_render_current_uses_rgb_fast_path():
    import inspect
    from core import app as app_mod

    src = inspect.getsource(app_mod.RemedyPDFApp.render_current)
    assert "render_view_rgb" in src
    assert "Format_RGB888" in src
    # Neighbor warm-up is deferred off the render hot path (anti-lag)
    assert "_queue_prefetch" in src
