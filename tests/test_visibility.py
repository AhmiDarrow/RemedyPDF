"""Visibility / reading experience: themes, page filters, brightness."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt5")
pytest.importorskip("fitz")
pytest.importorskip("PIL")


def test_theme_order_has_eight_readable_themes():
    from ui.theme import (
        THEME_ORDER,
        THEMES,
        build_stylesheet,
        list_page_filters,
        list_themes,
        page_colors_for_theme,
        page_filter_label,
        theme_is_dark,
        theme_label,
        toggle_theme,
    )

    assert len(THEME_ORDER) >= 8
    for key in ("dark", "light", "high_contrast", "sepia", "night", "midnight", "paper", "slate"):
        assert key in THEME_ORDER
        assert key in THEMES
        css = build_stylesheet(key)
        assert "QMainWindow" in css
        assert THEMES[key]["text"] in css or "color:" in css
        # Every theme defines readable chrome + page text colors
        assert THEMES[key]["text"].startswith("#")
        assert THEMES[key]["text_muted"].startswith("#")
        assert "page_ink" in THEMES[key]
        assert "page_paper" in THEMES[key]
        colors = page_colors_for_theme(key)
        assert colors["ink"] == THEMES[key]["page_ink"]
        assert colors["paper"] == THEMES[key]["page_paper"]
        assert theme_label(key)
        # Dark themes should report dark paper; light ones should not
        if key in ("dark", "night", "midnight", "slate", "high_contrast"):
            assert theme_is_dark(key)
        if key in ("light", "sepia", "paper"):
            assert not theme_is_dark(key)
    # Full cycle returns to start
    cur = THEME_ORDER[0]
    seen = {cur}
    for _ in range(len(THEME_ORDER)):
        cur = toggle_theme(cur)
        seen.add(cur)
    assert seen == set(THEME_ORDER)
    assert list_themes() == THEME_ORDER
    assert "invert" in list_page_filters()
    assert "Invert" in page_filter_label("invert")


def test_normal_theme_is_no_theme():
    """'normal' must be the default and mean a plain system look (no QSS)."""
    from ui.theme import (
        DEFAULT_THEME,
        THEME_ORDER,
        apply_theme,
        build_stylesheet,
        page_colors_for_theme,
        theme_is_dark,
    )

    assert DEFAULT_THEME == "normal"
    assert THEME_ORDER[0] == "normal"
    # Empty stylesheet = no custom chrome
    assert build_stylesheet("normal") == ""
    # No forced document recolor: ink/paper fall back to the neutral light palette
    colors = page_colors_for_theme("normal")
    assert colors["paper"].startswith("#")
    assert not theme_is_dark("normal")

    from PyQt5.QtWidgets import QApplication
    import sys

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setStyleSheet("QMainWindow { background-color: #000000; }")
    name = apply_theme(app, "normal")
    assert name == "normal"
    assert app.styleSheet() == ""  # cleared back to plain system look


def test_theme_stylesheet_sets_text_colors():
    """Chrome QSS must paint labels, menus, inputs with theme text colors."""
    from ui.theme import THEMES, build_stylesheet

    for key, pal in THEMES.items():
        css = build_stylesheet(key)
        assert pal["text"] in css
        assert pal["text_muted"] in css
        assert pal["canvas_text"] in css
        # Explicit text roles for common chrome
        assert "QLabel" in css
        assert "QMenuBar" in css
        assert "QStatusBar" in css
        assert "color:" in css


def test_engine_page_filters_change_pixels(tmp_path):
    import fitz
    from core.pdf_engine import PDFEngine

    path = tmp_path / "vis.pdf"
    doc = fitz.open()
    page = doc.new_page(width=200, height=200)
    # Bright white-ish page with black text area
    page.draw_rect(page.rect, color=(1, 1, 1), fill=(1, 1, 1))
    page.insert_text((40, 100), "HELLO", fontsize=28, color=(0, 0, 0))
    doc.save(path)
    doc.close()

    eng = PDFEngine(zoom=1.0)
    assert eng.open(str(path))
    base = eng.render_view_rgb()
    assert base is not None
    bw, bh, bdata = base
    assert bw > 0 and bh > 0 and len(bdata) == bw * bh * 3

    eng.set_page_filter("invert")
    inv = eng.render_view_rgb()
    assert inv is not None
    iw, ih, idata = inv
    assert (iw, ih) == (bw, bh)
    # Inverted buffer must differ from original
    assert idata != bdata

    eng.set_page_filter("sepia")
    sep = eng.render_view_rgb()
    assert sep is not None and sep[2] != bdata

    eng.set_page_filter("grayscale")
    gray = eng.render_view_rgb()
    assert gray is not None
    # Sample a few pixels: R==G==B for grayscale
    gd = gray[2]
    assert gd[0] == gd[1] == gd[2]

    eng.set_brightness(1.2)
    eng.set_contrast(1.1)
    adj = eng.render_view_rgb()
    assert adj is not None and adj[2] != gray[2]

    eng.reset_page_appearance()
    assert eng.page_filter == "none"
    assert eng.brightness == pytest.approx(1.0)
    assert eng.contrast == pytest.approx(1.0)
    eng.close()


def test_theme_page_recolor_maps_ink_and_paper(tmp_path):
    """Theme ink/paper recolor turns white paper + black ink into theme colors."""
    import fitz
    from core.pdf_engine import PDFEngine
    from ui.theme import page_colors_for_theme

    path = tmp_path / "recolor.pdf"
    doc = fitz.open()
    page = doc.new_page(width=100, height=100)
    page.draw_rect(page.rect, color=(1, 1, 1), fill=(1, 1, 1))
    # Solid black block (ink)
    page.draw_rect(fitz.Rect(10, 10, 40, 40), color=(0, 0, 0), fill=(0, 0, 0))
    doc.save(path)
    doc.close()

    eng = PDFEngine(zoom=1.0)
    assert eng.open(str(path))
    base = eng.render_view_rgb()
    assert base is not None

    colors = page_colors_for_theme("night")
    eng.set_theme_page_colors(ink=colors["ink"], paper=colors["paper"], enabled=True)
    assert eng.theme_recolor is True
    themed = eng.render_view_rgb()
    assert themed is not None
    tw, th, tdata = themed
    assert (tw, th) == (base[0], base[1])
    assert tdata != base[2]

    # Corner should be near paper (dark for night); ink block near ink color
    # Sample top-left (paper) and inside black rect (ink) after recolor
    def px(data, w, x, y):
        i = (y * w + x) * 3
        return (data[i], data[i + 1], data[i + 2])

    paper_px = px(tdata, tw, 2, 2)
    # Night paper is near black
    assert sum(paper_px) < 80, paper_px

    eng.clear_theme_page_colors()
    assert eng.theme_recolor is False
    restored = eng.render_view_rgb()
    assert restored is not None and restored[2] == base[2]
    eng.close()


def test_app_reading_controls(tmp_path):
    import fitz
    from core.app import create_app

    path = tmp_path / "read.pdf"
    doc = fitz.open()
    for _ in range(2):
        doc.new_page()
    doc.save(path)
    doc.close()

    app, window = create_app([])
    window.open_document(str(path))
    assert hasattr(window, "set_page_filter")
    assert hasattr(window, "set_ui_scale")
    assert hasattr(window, "adjust_brightness")

    window.set_theme("midnight")
    assert window._theme == "midnight"
    # Theme must push page ink/paper so document text follows chrome
    assert window.engine.theme_recolor is True
    assert window.engine.page_ink is not None
    assert window.engine.page_paper is not None
    window.set_theme("paper")
    assert window._theme == "paper"
    assert window.engine.page_ink is not None

    window.set_page_filter("invert")
    assert window.engine.page_filter == "invert"
    window.toggle_page_filter("invert")
    assert window.engine.page_filter == "none"

    window.adjust_brightness(0.1)
    assert window.engine.brightness == pytest.approx(1.1)
    window.adjust_contrast(-0.1)
    assert window.engine.contrast == pytest.approx(0.9)
    window.reset_page_appearance()
    assert window.engine.page_filter == "none"
    # Reset appearance keeps theme text/paper recolor
    assert window.engine.theme_recolor is True

    window.set_ui_scale(1.3)
    assert window._ui_scale == pytest.approx(1.3)

    window.close()
    app.quit()
