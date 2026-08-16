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


def test_cache_drops_oversized_render(sample_pdf: Path):
    """A single render bigger than the whole budget must not blow the cap."""
    eng = PDFEngine(zoom=1.0)
    eng.open(str(sample_pdf))
    eng.MAX_CACHE_BYTES = 4096  # tiny — the zoom-4 render (~11 MB) exceeds it alone
    eng.render_view_rgb(zoom=4.0)
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


def test_save_in_place_keeps_document_open(sample_pdf: Path):
    """Saving onto the currently-open path must succeed and stay usable."""
    eng = PDFEngine()
    assert eng.open(str(sample_pdf))
    assert eng.add_text("In-place", page=0, x=72, y=140, fontsize=12) is True
    assert eng.save(str(sample_pdf)) is True
    assert eng.is_open
    assert eng.page_count >= 1
    rgb = eng.render_view_rgb()
    assert rgb is not None and rgb[0] > 0 and rgb[1] > 0
    # No leftover temp sibling
    leftovers = list(sample_pdf.parent.glob("*.__remedy_save__.pdf"))
    assert leftovers == []
    eng.close()


def test_cache_entry_cap_is_inclusive(multi_page_pdf: Path):
    """_cache_max entries are allowed; only max+1 forces eviction."""
    eng = PDFEngine(zoom=1.0)
    eng.open(str(multi_page_pdf))
    eng.MAX_CACHE_BYTES = 10**12  # only entry cap binds
    eng._cache_max = 2
    eng.render_view_rgb(page=0, zoom=1.0)
    eng.render_view_rgb(page=1, zoom=1.0)
    assert len(eng._page_cache) == 2
    eng.render_view_rgb(page=2, zoom=1.0)
    assert len(eng._page_cache) == 2
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


def test_book_mode_clears_cache_byte_counter(multi_page_pdf: Path):
    """Toggling book mode must zero _cache_bytes or the LRU budget drifts."""
    eng = PDFEngine(zoom=1.0)
    eng.open(str(multi_page_pdf))
    eng.render_view_rgb(zoom=2.0)
    assert eng._cache_bytes > 0
    eng.set_book_mode(True)
    assert eng._page_cache == {}
    assert eng._cache_bytes == 0
    eng.render_view_rgb(zoom=2.0)
    assert eng._cache_bytes > 0
    eng.set_book_cover_alone(True)
    assert eng._page_cache == {}
    assert eng._cache_bytes == 0
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
    # Extra formats added in 1.3.9 (MuPDF page-document input — no rebuild)
    assert PDFEngine.is_supported_path("note.docx")
    assert PDFEngine.is_supported_path("diagram.svg")
    assert PDFEngine.is_supported_path("photo.jpg")
    assert PDFEngine.is_supported_path("photo.png")
    assert PDFEngine.is_supported_path("cover.mobi")
    assert not PDFEngine.is_supported_path("unknown.xyz")


def test_open_epub(sample_epub: Path):
    eng = PDFEngine()
    ok = eng.open(str(sample_epub))
    if not ok:
        pytest.skip("MuPDF build cannot open this minimal EPUB")
    assert eng.format == "epub"
    assert eng.page_count >= 1
    png = eng.render_page(0)
    # Rendering may fail on some MuPDF builds; open success is the bar
    if png is not None:        assert png[:8] == b"\x89PNG\r\n\x1a\n"
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


def test_open_extra_formats_svg_png_docx(tmp_path: Path):
    """1.3.9: SVG / plain images / DOCX open as page documents (best-effort)."""
    import base64
    import zipfile

    svg = tmp_path / "pic.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="120" height="60">'
        '<rect width="120" height="60" fill="#2e5f9e"/>'
        "<text x=\"10\" y=\"40\">Remedy</text></svg>",
        encoding="utf-8",
    )
    png = tmp_path / "pix.png"
    png.write_bytes(
        base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/q842iQAAAABJRU5ErkJggg=="
        )
    )
    docx = tmp_path / "note.docx"
    with zipfile.ZipFile(docx, "w") as z:
        z.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
            '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
            "</Types>",
        )
        z.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
            '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
            "</Relationships>",
        )
        z.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body><w:p><w:r><w:t>Hello Remedy</w:t></w:r></w:p></w:body></w:document>",
        )
        z.writestr(
            "docProps/core.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/">'
            "<dc:title>Remedy note</dc:title><dc:creator>Ahmi</dc:creator></cp:coreProperties>",
        )
        z.writestr(
            "docProps/app.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
            "<Application>RemedyPDF</Application></Properties>",
        )

    for p, fmt in ((svg, "svg"), (png, "png"), (docx, "docx")):
        eng = PDFEngine()
        ok = eng.open(str(p))
        if not ok:
            pytest.skip(f"MuPDF build cannot open {fmt} on this build")
        assert eng.page_count >= 1
        assert eng.format == fmt
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


def test_theme_recolor_fast(tmp_path: Path):
    """Theme ink/paper recolor must run at LUT (C) speed, not per-pixel Python.

    Regression guard: the old _apply_theme_recolor looped every pixel in pure
    Python (seconds on fit-capped pages). With the 256-entry LUT path a
    5+ MP render must complete well under a second.
    """
    import time

    path = tmp_path / "big.pdf"
    doc = fitz.open()
    page = doc.new_page(width=500, height=700)
    page.draw_rect(page.rect, color=(1, 1, 1), fill=(1, 1, 1))
    for i in range(150):
        page.insert_text((40 + (i % 20) * 22, 60 + (i // 20) * 22), f"L{i}", fontsize=10)
    doc.save(path)
    doc.close()

    eng = PDFEngine(zoom=1.0)
    assert eng.open(str(path))
    eng.set_theme_page_colors(ink=(30, 32, 40), paper=(245, 246, 250), enabled=True)
    t0 = time.perf_counter()
    rgb = eng.render_view_rgb(zoom=4.0)  # 2000x2800 = 5.6 MP
    dt = time.perf_counter() - t0
    assert rgb is not None
    w, h, _data = rgb
    assert w * h >= 5_000_000  # big enough to catch a per-pixel Python loop
    assert dt < 1.0, f"theme recolor too slow: {dt * 1000:.0f} ms"
    eng.close()


def test_book_spread_logical_matches_render(multi_page_pdf: Path):
    """Book-mode logical size must equal the rendered spread (no forced rescale).

    Regression guard: get_view_size_at_zoom used an 8.0*z gutter while
    _compose_spread_rgb painted a max(10, int(14*z)) gap, so render_current
    smooth-scaled EVERY book-mode frame. Sizes must now agree to ~2 px.
    """
    eng = PDFEngine(zoom=1.25)
    eng.open(str(multi_page_pdf))
    eng.set_book_mode(True)
    eng.set_current_page(0)
    rgb = eng.render_view_rgb()  # zoom 1.25
    assert rgb is not None
    rw, rh, _data = rgb
    lw, lh = eng.get_view_size_at_zoom(eng.zoom)
    assert abs(rw - lw) <= 2.0, f"spread width mismatch: render {rw} vs logical {lw}"
    assert abs(rh - lh) <= 2.0, f"spread height mismatch: render {rh} vs logical {lh}"
    eng.close()


def test_gray_pixmap_converts_fast_and_correct(tmp_path: Path):
    """Grayscale pages (n==1) must render to RGB via the C path."""
    import time

    path = tmp_path / "gray.pdf"
    doc = fitz.open()
    page = doc.new_page(width=300, height=400)
    # Set colorspace to gray so the pixmap comes back as n==1
    page.draw_rect(page.rect, color=(0.5,), fill=(0.5,))
    page.insert_text((72, 72), "Gray", fontsize=14, color=(0.0,))
    doc.save(path)
    doc.close()

    eng = PDFEngine(zoom=1.0)
    assert eng.open(str(path))
    t0 = time.perf_counter()
    rgb = eng.render_view_rgb(zoom=3.0)
    dt = time.perf_counter() - t0
    assert rgb is not None
    w, h, data = rgb
    assert len(data) == w * h * 3  # RGB24, not gray
    assert dt < 1.0, f"gray convert too slow: {dt * 1000:.0f} ms"
    eng.close()


def test_filter_clear_zeros_cache_bytes():
    """Appearance toggles must not leave stale _cache_bytes after clear."""
    eng = PDFEngine()
    eng._page_cache[("k",)] = {"w": 100, "h": 100, "rgb": b"\x00" * 30000}
    eng._cache_bytes = eng._item_bytes(eng._page_cache[("k",)])
    assert eng._cache_bytes > 0
    eng.set_page_filter("sepia")
    assert eng._page_cache == {}
    assert eng._cache_bytes == 0
    eng._page_cache[("k2",)] = {"w": 10, "h": 10, "rgb": b"\x00" * 300}
    eng._cache_bytes = 9999
    eng.set_brightness(1.1)
    assert eng._cache_bytes == 0
    eng._page_cache[("k3",)] = {"w": 5, "h": 5, "rgb": b"\x00" * 75}
    eng._cache_bytes = 42
    eng.reset_page_appearance()
    assert eng._cache_bytes == 0
