from pathlib import Path
import zipfile

import fitz
import pytest

from core.pdf_engine import PDFEngine, SUPPORTED_EXTENSIONS


@pytest.fixture()
def sample_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "sample.pdf"
    doc = fitz.open()
    page = doc.new_page(width=300, height=400)
    page.insert_text((72, 72), "Hello RemedyPDF", fontsize=14)
    doc.save(path)
    doc.close()
    return path


@pytest.fixture()
def multi_page_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "book.pdf"
    doc = fitz.open()
    for i in range(5):
        page = doc.new_page(width=300, height=400)
        page.insert_text((72, 72), f"Page {i + 1}", fontsize=14)
    doc.save(path)
    doc.close()
    return path


@pytest.fixture()
def sample_epub(tmp_path: Path) -> Path:
    """Minimal EPUB that MuPDF can open as a document."""
    path = tmp_path / "sample.epub"
    # Build a tiny valid-enough EPUB (ZIP with container + xhtml)
    container = """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""
    opf = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="uid">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>RemedyPDF Test</dc:title>
    <dc:identifier id="uid">remedy-test-epub</dc:identifier>
    <dc:language>en</dc:language>
  </metadata>
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml"/>
    <item id="c1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine>
    <itemref idref="c1"/>
  </spine>
</package>
"""
    chapter = """<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>Chapter 1</title></head>
<body><h1>Hello EPUB</h1><p>RemedyPDF multi-format test.</p></body>
</html>
"""
    nav = """<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>Nav</title></head>
<body><nav><ol><li><a href="chapter1.xhtml">Ch1</a></li></ol></nav></body>
</html>
"""
    mimetype = b"application/epub+zip"
    with zipfile.ZipFile(path, "w") as zf:
        # mimetype must be first and stored (no compression) for strict readers
        zf.writestr("mimetype", mimetype, compress_type=zipfile.ZIP_STORED)
        zf.writestr("META-INF/container.xml", container)
        zf.writestr("OEBPS/content.opf", opf)
        zf.writestr("OEBPS/chapter1.xhtml", chapter)
        zf.writestr("OEBPS/nav.xhtml", nav)
    return path


def test_open_and_page_count(sample_pdf: Path):
    eng = PDFEngine()
    assert eng.open(str(sample_pdf)) is True
    assert eng.get_page_count() == 1
    assert eng.path == str(sample_pdf)
    eng.close()


def test_render_page_png(sample_pdf: Path):
    eng = PDFEngine(zoom=1.0)
    assert eng.open(str(sample_pdf))
    png = eng.render_page(0)
    assert png is not None
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    eng.close()


def test_fit_render_zoom_capped(sample_pdf: Path):
    """Fit on huge screens must never rasterize unbounded buffers."""
    eng = PDFEngine(zoom=1.0)
    eng.open(str(sample_pdf))
    assert eng.MAX_RENDER_ZOOM < eng.ZOOM_MAX  # cap engages below the zoom ceiling
    rgb = eng.render_view_rgb(zoom=eng.ZOOM_MAX)  # 8.0 >> cap
    assert rgb is not None
    w, h, _data = rgb
    assert w <= 300 * eng.MAX_RENDER_ZOOM + 1
    assert h <= 400 * eng.MAX_RENDER_ZOOM + 1
    assert w * h <= eng.MAX_RENDER_PIXELS
    eng.close()


def test_export_render_not_capped(sample_pdf: Path):
    """Export keeps full requested resolution (cap is view-only)."""
    import io as _io

    from PIL import Image

    eng = PDFEngine(zoom=1.0)
    eng.open(str(sample_pdf))
    png = eng.render_page(0, zoom=eng.ZOOM_MAX)
    assert png is not None
    img = Image.open(_io.BytesIO(png))
    assert (img.width, img.height) == (2400, 3200)  # 300x400 pts @ 8.0
    eng.close()


def test_cache_byte_budget(multi_page_pdf: Path):
    """LRU evicts by memory, not just entry count, when renders are large."""
    eng = PDFEngine(zoom=1.0)
    eng.open(str(multi_page_pdf))
    eng.MAX_CACHE_BYTES = 10_000_000  # 10 MB — forces eviction at zoom 4.0 renders
    for i in range(eng.page_count):
        eng.render_view_rgb(page=i, zoom=4.0)
    assert eng._cache_bytes <= eng.MAX_CACHE_BYTES
    assert len(eng._page_cache) <= eng._cache_max
    eng.close()


def test_add_text_and_save(sample_pdf: Path, tmp_path: Path):
    eng = PDFEngine()
    assert eng.open(str(sample_pdf))
    assert eng.add_text("Annotation", page=0, x=72, y=120, fontsize=12) is True
    out = tmp_path / "out.pdf"
    assert eng.save(str(out)) is True
    assert out.is_file() and out.stat().st_size > 0
    eng.close()


def test_set_page_bounds(sample_pdf: Path):
    eng = PDFEngine()
    eng.open(str(sample_pdf))
    assert eng.set_current_page(0) is True
    assert eng.set_current_page(99) is False
    eng.close()


def test_open_missing_file():
    eng = PDFEngine()
    assert eng.open(str(Path("definitely_missing_file_xyz.pdf"))) is False


def test_fine_zoom_1_percent(sample_pdf: Path):
    eng = PDFEngine(zoom=1.0)
    eng.open(str(sample_pdf))
    assert eng.ZOOM_FINE == pytest.approx(0.01)
    z = eng.fine_zoom_in()
    assert z == pytest.approx(1.01)
    z = eng.fine_zoom_out()
    assert z == pytest.approx(1.00)
    eng.adjust_zoom(0.01)
    assert eng.zoom == pytest.approx(1.01)
    eng.close()


def test_coarse_zoom(sample_pdf: Path):
    eng = PDFEngine(zoom=1.0)
    eng.open(str(sample_pdf))
    eng.coarse_zoom_in()
    assert eng.zoom == pytest.approx(1.15)
    eng.coarse_zoom_out()
    assert eng.zoom == pytest.approx(1.0)
    eng.close()


def test_book_mode_spread_pages(multi_page_pdf: Path):
    eng = PDFEngine()
    eng.open(str(multi_page_pdf))
    assert eng.page_count == 5

    # Single page mode
    eng.set_book_mode(False)
    eng.set_current_page(0)
    assert eng.spread_pages() == [0]

    # Book mode both sides (default): pairs (0,1), (2,3), …
    eng.set_book_mode(True)
    assert eng.book_cover_alone is False
    eng.set_current_page(0)
    assert eng.spread_pages() == [0, 1]

    # Page 1 (odd) still maps to left=0 → both sides 0+1
    eng.set_current_page(1)
    assert eng.spread_pages() == [0, 1]

    # Page 2 → spread 2+3
    eng.set_current_page(2)
    assert eng.spread_pages() == [2, 3]

    # Page 3 → still 2+3
    eng.set_current_page(3)
    assert eng.spread_pages() == [2, 3]

    # Page 4 alone (odd last page)
    eng.set_current_page(4)
    assert eng.spread_pages() == [4]

    eng.close()


def test_book_mode_cover_alone_optional(multi_page_pdf: Path):
    eng = PDFEngine()
    eng.open(str(multi_page_pdf))
    eng.set_book_mode(True)
    eng.set_book_cover_alone(True)
    eng.set_current_page(0)
    assert eng.spread_pages() == [0]
    eng.set_current_page(1)
    assert eng.spread_pages() == [1, 2]
    eng.close()


def test_book_mode_navigation_steps(multi_page_pdf: Path):
    eng = PDFEngine()
    eng.open(str(multi_page_pdf))
    eng.set_book_mode(True)  # both sides
    eng.set_current_page(0)
    assert eng.spread_pages() == [0, 1]
    assert eng.next_page() is True
    assert eng.current_page == 2  # next both-sides spread
    assert eng.spread_pages() == [2, 3]
    assert eng.next_page() is True
    assert eng.current_page == 4
    assert eng.prev_page() is True
    assert eng.current_page == 2
    eng.close()


def test_render_view_spread(multi_page_pdf: Path):
    eng = PDFEngine(zoom=0.5)
    eng.open(str(multi_page_pdf))
    eng.set_book_mode(True)
    eng.set_current_page(1)
    assert eng.spread_pages() == [0, 1]
    data = eng.render_view()
    assert data is not None
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    # Spread must be wider than a single page (both sides composited)
    single = eng.render_page(0, zoom=0.5)
    assert single is not None
    assert len(data) > 0 and len(single) > 0
    from PIL import Image
    import io

    spread_img = Image.open(io.BytesIO(data))
    single_img = Image.open(io.BytesIO(single))
    # Two pages side-by-side + gutter → clearly wider than one page
    assert spread_img.width > single_img.width * 1.5
    assert spread_img.height == single_img.height or abs(spread_img.height - single_img.height) < 4
    eng.close()


def test_book_spread_view_size_both_sides(multi_page_pdf: Path):
    eng = PDFEngine(zoom=1.0)
    eng.open(str(multi_page_pdf))
    eng.set_book_mode(True)
    eng.set_current_page(0)
    vw, vh = eng.get_view_size()
    pw, ph = eng.get_page_size(0)
    # View width ≈ left + gutter + right
    assert vw > pw * 1.5
    assert vh == pytest.approx(ph)
    eng.close()


def test_supported_extensions_include_epub():
    exts = PDFEngine.supported_extensions()
    assert ".pdf" in exts
    assert ".epub" in exts
    assert ".xps" in exts
    assert ".cbz" in exts
    assert PDFEngine.is_supported_path("book.epub")
    assert not PDFEngine.is_supported_path("note.docx")


def test_open_epub(sample_epub: Path):
    eng = PDFEngine()
    ok = eng.open(str(sample_epub))
    if not ok:
        pytest.skip("MuPDF build cannot open this minimal EPUB")
    assert eng.format == "epub"
    assert eng.page_count >= 1
    png = eng.render_page(0)
    # Rendering may fail on some MuPDF builds; open success is the bar
    if png is not None:
        assert png[:8] == b"\x89PNG\r\n\x1a\n"
    eng.close()


def test_open_html_as_document(tmp_path: Path):
    html = tmp_path / "page.html"
    html.write_text(
        "<html><body><h1>Hello HTML</h1><p>RemedyPDF</p></body></html>",
        encoding="utf-8",
    )
    eng = PDFEngine()
    ok = eng.open(str(html))
    if not ok:
        pytest.skip("MuPDF cannot open HTML on this build")
    assert eng.page_count >= 1
    eng.close()


def test_reset_zoom_optional_target(sample_pdf: Path):
    eng = PDFEngine(zoom=2.0)
    eng.open(str(sample_pdf))
    eng.reset_zoom()
    assert eng.zoom == pytest.approx(PDFEngine.ZOOM_DEFAULT)
    eng.set_zoom(3.0)
    eng.reset_zoom(1.0)
    assert eng.zoom == pytest.approx(1.0)
    eng.close()


def test_render_cache_bounded(sample_pdf: Path):
    eng = PDFEngine(zoom=0.5)
    eng.open(str(sample_pdf))
    eng._cache_max = 3
    for i in range(6):
        eng.set_zoom(0.5 + i * 0.01)
        assert eng.render_page(0) is not None
    assert len(eng._page_cache) <= eng._cache_max
    eng.close()


def test_map_view_xy_to_page_spread(multi_page_pdf: Path):
    """Click mapping must land on left vs right page of a book spread."""
    eng = PDFEngine(zoom=1.0)
    eng.open(str(multi_page_pdf))
    eng.set_book_mode(True)
    eng.set_current_page(0)
    assert eng.spread_pages() == [0, 1]
    left_w, left_h = eng.get_page_size(0)
    gutter = eng.spread_gap_pts()
    # Left half → page 0
    m = eng.map_view_xy_to_page(left_w * 0.25, left_h * 0.5)
    assert m is not None
    assert m[0] == 0
    assert m[1] == pytest.approx(left_w * 0.25, abs=1.0)
    # Right half → page 1, local x near 0
    m2 = eng.map_view_xy_to_page(left_w + gutter + 10.0, left_h * 0.4)
    assert m2 is not None
    assert m2[0] == 1
    assert m2[1] == pytest.approx(10.0, abs=1.0)
    eng.close()


def test_book_spin_snap_resync(multi_page_pdf: Path):
    """Odd page requests in book mode snap to left of spread."""
    eng = PDFEngine()
    eng.open(str(multi_page_pdf))
    eng.set_book_mode(True)
    assert eng.set_current_page(1) is True
    assert eng.current_page == 0
    assert eng.spread_pages() == [0, 1]
    assert eng.set_current_page(3) is True
    assert eng.current_page == 2
    eng.close()


def test_render_view_rgb_and_lru(multi_page_pdf: Path):
    """RGB fast path + true LRU cache eviction / hit promotion."""
    eng = PDFEngine(zoom=0.5)
    eng.open(str(multi_page_pdf))
    eng.set_book_mode(True)
    eng.set_current_page(0)
    rgb = eng.render_view_rgb()
    assert rgb is not None
    w, h, data = rgb
    assert w > 0 and h > 0
    assert len(data) == w * h * 3
    # Spread wider than single
    single = eng._render_page_rgb(0, 0.5)
    assert single is not None
    assert w > single[0] * 1.5
    # LRU bound
    eng._cache_max = 3
    eng._page_cache.clear()
    for i in range(5):
        eng.set_zoom(0.4 + i * 0.02)
        assert eng.render_view_rgb(page=0) is not None
    assert len(eng._page_cache) <= eng._cache_max
    # Hit promotes (no crash); second call returns same dims
    eng._cache_max = 16
    a = eng.render_view_rgb(page=0, zoom=0.5)
    b = eng.render_view_rgb(page=0, zoom=0.5)
    assert a is not None and b is not None
    assert a[0] == b[0] and a[1] == b[1]
    eng.close()
