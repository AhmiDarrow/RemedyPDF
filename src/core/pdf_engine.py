"""Document engine using PyMuPDF (fitz) — PDF, EPUB, XPS, CBZ, and more."""

from __future__ import annotations

import io
import math
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import fitz

# Formats PyMuPDF can open as page-based documents.
# DOCX / SVG / plain images open through MuPDF's office+image handlers —
# no extra dependencies, no rebuild.
SUPPORTED_EXTENSIONS = (
    ".pdf",
    ".epub",
    ".xps",
    ".oxps",
    ".cbz",
    ".cbr",
    ".fb2",
    ".mobi",  # best-effort; depends on MuPDF build
    ".svg",
    ".docx",  # MuPDF >= 1.23 office input; view + save-as PDF
    ".html",
    ".htm",
    ".xhtml",
    ".txt",
    ".png",
    ".jpg",
    ".jpeg",
    ".bmp",
    ".gif",
    ".tif",
    ".tiff",
    ".webp",
)

OPEN_FILTER = (
    "Documents (*.pdf *.epub *.xps *.oxps *.cbz *.cbr *.fb2 *.mobi *.svg *.docx "
    "*.html *.htm *.xhtml *.txt *.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.webp);;"
    "PDF (*.pdf);;"
    "EPUB (*.epub);;"
    "XPS (*.xps *.oxps);;"
    "Comic Book (*.cbz *.cbr);;"
    "FictionBook (*.fb2);;"
    "MOBI (*.mobi);;"
    "SVG (*.svg);;"
    "Word (*.docx);;"
    "HTML (*.html *.htm *.xhtml);;"
    "Text (*.txt);;"
    "Images (*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.webp);;"
    "All Files (*)"
)

SAVE_FILTER = "PDF Files (*.pdf);;All Files (*)"


class PDFEngine:
    """Core multi-format rendering and editing engine."""

    # Zoom bounds and step sizes
    ZOOM_MIN = 0.1
    ZOOM_MAX = 8.0
    ZOOM_FINE = 0.01  # 1%
    ZOOM_COARSE = 0.15  # 15%
    ZOOM_DEFAULT = 1.25
    # Render safety caps: 'fit' must never rasterize absurdly large buffers.
    # The UI rescales the (capped) pixmap to the exact logical view size, so
    # layout and click hit-testing stay exact while big screens stay fast.
    # View renders rasterize at most MAX_RENDER_ZOOM (defensive ceiling) and
    # always stay under MAX_RENDER_PIXELS (real memory guard). 6.0 covers
    # fit-width on 1080p+ without the old 4.0 cap forcing a costly Smooth
    # rescale on every fit; pixel budget still binds on huge pages.
    MAX_RENDER_ZOOM = 6.0
    MAX_RENDER_PIXELS = 24_000_000  # per page, e.g. 6000x4000
    MAX_CACHE_BYTES = 256 * 1024 * 1024  # LRU memory budget (fit zoom ~13 MB/page)

    def __init__(self, zoom: float = 1.25) -> None:
        self.zoom = float(zoom)
        self.doc: Optional[fitz.Document] = None
        self.path: Optional[str] = None
        self.page_count = 0
        self.current_page = 0
        self.book_mode: bool = False
        # Book spreads always show both sides when possible: (0,1), (2,3), …
        self.book_cover_alone: bool = False
        # True LRU of rendered RGB pages / spreads (avoids PNG encode on every paint)
        self._page_cache: "OrderedDict[tuple, dict]" = OrderedDict()
        self._cache_max: int = 64  # soft entry bound on long reading sessions
        self._cache_bytes: int = 0  # real memory budget: renders grow with zoom
        self._format: str = ""
        # Page appearance filters (view-only — never baked into saved PDF)
        self.page_filter: str = "none"  # none|invert|sepia|grayscale|warm|cool
        self.brightness: float = 1.0  # 0.5 .. 1.5
        self.contrast: float = 1.0  # 0.5 .. 1.5
        # Theme-linked document recolor (ink + paper). None = keep source colors.
        self.page_ink: Optional[Tuple[int, int, int]] = None
        self.page_paper: Optional[Tuple[int, int, int]] = None
        self.theme_recolor: bool = False
        # View-only rotation in degrees (0/90/180/270) — never baked into saves.
        self.rotation: int = 0

    # ----- lifecycle -----

    def open(self, path: str) -> bool:
        """Open a PDF/EPUB/XPS/CBZ/… file. Returns True on success."""
        try:
            self.close()
            p = Path(path)
            # MuPDF opens EPUB/XPS/CBZ/etc. the same way as PDF
            self.doc = fitz.open(str(p))
            self.path = str(p)
            self.page_count = len(self.doc)
            self.current_page = 0
            self._page_cache.clear()
            self._cache_bytes = 0
            self._format = p.suffix.lower().lstrip(".") or "pdf"
            return True
        except Exception as exc:  # noqa: BLE001 - surface open failures cleanly
            print(f"Error opening document: {exc}")
            self.doc = None
            self.path = None
            self.page_count = 0
            self._format = ""
            return False

    def close(self) -> None:
        """Close the document and clear caches."""
        if self.doc is not None:
            try:
                self.doc.close()
            except Exception:  # noqa: BLE001
                pass
        self.doc = None
        self.path = None
        self.page_count = 0
        self.current_page = 0
        self._page_cache.clear()
        self._cache_bytes = 0
        self._format = ""
        self.rotation = 0

    @property
    def is_open(self) -> bool:
        return self.doc is not None

    @property
    def format(self) -> str:
        return self._format

    @property
    def is_pdf(self) -> bool:
        return self._format == "pdf" or (
            self.doc is not None and bool(getattr(self.doc, "is_pdf", False))
        )

    @staticmethod
    def supported_extensions() -> Tuple[str, ...]:
        return SUPPORTED_EXTENSIONS

    @staticmethod
    def is_supported_path(path: str) -> bool:
        return Path(path).suffix.lower() in SUPPORTED_EXTENSIONS

    # ----- navigation -----

    def get_page_count(self) -> int:
        return self.page_count

    def get_current_page(self) -> int:
        return self.current_page

    def set_current_page(self, page: int) -> bool:
        if self.doc is None or self.page_count <= 0:
            return False
        # Clamp out-of-range requests instead of hard-failing near last spread
        idx = int(page)
        if idx < 0 or idx >= self.page_count:
            return False
        # In both-sides book mode, snap to the left page of the spread
        if self.book_mode and not self.book_cover_alone:
            idx = self._spread_left(idx)
        elif self.book_mode and self.book_cover_alone and idx > 0:
            # Odd-left pairs after cover: 1,3,5…
            if idx % 2 == 0:
                idx = max(1, idx - 1)
        # Guard: snap must still land in-range (odd last page alone is fine)
        if idx < 0 or idx >= self.page_count:
            return False
        self.current_page = idx
        return True

    def next_page(self) -> bool:
        """Advance one page, or one spread (both sides) in book mode."""
        if self.doc is None:
            return False
        if self.book_mode:
            left = self._spread_left(self.current_page)
            # Both-sides default: jump to next even left page
            if not self.book_cover_alone:
                nxt = left + 2
            else:
                # Cover-alone: 0 → 1, then +2
                nxt = 1 if left == 0 else left + 2
            if nxt >= self.page_count:
                return False
            return self.set_current_page(nxt)
        return self.set_current_page(min(self.page_count - 1, self.current_page + 1))

    def prev_page(self) -> bool:
        if self.doc is None:
            return False
        if self.book_mode:
            left = self._spread_left(self.current_page)
            if not self.book_cover_alone:
                prv = left - 2
            else:
                prv = 0 if left <= 1 else left - 2
            if prv < 0:
                return False
            return self.set_current_page(prv)
        return self.set_current_page(max(0, self.current_page - 1))

    def _nav_step(self) -> int:
        """Pages advanced per next/prev (1 single, 2 book spread)."""
        if not self.book_mode:
            return 1
        if self.book_cover_alone and self.current_page == 0:
            return 1
        return 2

    def _spread_left(self, idx: int) -> int:
        """Left page index of the both-sides spread containing idx."""
        if idx < 0:
            return 0
        return idx if idx % 2 == 0 else idx - 1

    # ----- book mode -----

    def set_book_mode(self, enabled: bool) -> None:
        """Enable two-page (both sides) book spreads."""
        self.book_mode = bool(enabled)
        if self.book_mode and self.doc is not None:
            # Always snap to left side so both pages of the pair show
            if self.book_cover_alone and self.current_page == 0:
                pass
            else:
                self.current_page = self._spread_left(self.current_page)
        self._page_cache.clear()
        self._cache_bytes = 0

    def set_book_cover_alone(self, enabled: bool) -> None:
        """Optional: show cover alone, then (1,2)/(3,4)… Default is both sides."""
        self.book_cover_alone = bool(enabled)
        if self.book_mode and self.doc is not None and not self.book_cover_alone:
            self.current_page = self._spread_left(self.current_page)
        self._page_cache.clear()
        self._cache_bytes = 0

    def toggle_book_mode(self) -> bool:
        self.set_book_mode(not self.book_mode)
        return self.book_mode

    def spread_pages(self, page: Optional[int] = None) -> List[int]:
        """Return page indices for the current view.

        Book mode **both sides** (default): pairs (0,1), (2,3), (4,5), …
        Optional cover-alone: page 0 alone; then (1,2), (3,4), …
        Last page may appear alone when the document length is odd.
        """
        if self.doc is None:
            return []
        idx = self.current_page if page is None else page
        if not (0 <= idx < self.page_count):
            return []
        if not self.book_mode:
            return [idx]

        if self.book_cover_alone:
            if idx == 0:
                return [0]
            left = idx if idx % 2 == 1 else idx - 1
            if left < 1:
                left = 1
        else:
            # Both sides from the start: even left pages 0,2,4…
            left = self._spread_left(idx)

        pages = [left]
        right = left + 1
        if right < self.page_count:
            pages.append(right)
        return pages

    # ----- view rotation (view-only; never baked into saved output) -----

    def set_rotation(self, degrees: int) -> int:
        """Set the view rotation in degrees (0/90/180/270 — any int normalized)."""
        self.rotation = int(degrees) % 360
        self._page_cache.clear()
        self._cache_bytes = 0
        return self.rotation

    def rotate_right(self) -> int:
        """Rotate the view 90° clockwise."""
        return self.set_rotation(self.rotation + 90)

    def rotate_left(self) -> int:
        """Rotate the view 90° counter-clockwise."""
        return self.set_rotation(self.rotation - 90)

    @property
    def is_rotated(self) -> bool:
        """True when the view is at 90° or 270° (aspect swapped)."""
        return self.rotation % 180 != 0

    def _rotated_size(self, w: float, h: float) -> Tuple[float, float]:
        """Page (w, h) after the current view rotation."""
        if self.rotation % 180 == 0:
            return float(w), float(h)
        return float(h), float(w)

    # ----- zoom -----

    def set_zoom(self, zoom: float) -> None:
        self.zoom = max(self.ZOOM_MIN, min(float(zoom), self.ZOOM_MAX))
        self._page_cache.clear()
        self._cache_bytes = 0

    # ----- reading / visibility filters (view-only) -----

    FILTER_NAMES: Tuple[str, ...] = (
        "none",
        "invert",
        "sepia",
        "grayscale",
        "warm",
        "cool",
    )

    @staticmethod
    def _parse_rgb(color) -> Optional[Tuple[int, int, int]]:
        """Accept #hex, (r,g,b), or None → optional 0–255 RGB tuple."""
        if color is None:
            return None
        if isinstance(color, (tuple, list)) and len(color) >= 3:
            return (
                max(0, min(255, int(color[0]))),
                max(0, min(255, int(color[1]))),
                max(0, min(255, int(color[2]))),
            )
        if isinstance(color, str):
            h = color.strip().lstrip("#")
            if len(h) == 3:
                h = "".join(ch * 2 for ch in h)
            if len(h) == 6:
                try:
                    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
                except ValueError:
                    return None
        return None

    def set_theme_page_colors(
        self,
        ink=None,
        paper=None,
        *,
        enabled: Optional[bool] = None,
    ) -> None:
        """Set theme-linked document ink/paper recolor (view-only).

        When enabled (default True if either color given), grayscale luminance
        of each pixel is mapped from paper (light) → ink (dark) so dark themes
        get light text on dark paper and light themes keep dark text on light paper.
        """
        new_ink = self._parse_rgb(ink)
        new_paper = self._parse_rgb(paper)
        if enabled is None:
            enabled = new_ink is not None or new_paper is not None
        changed = (
            new_ink != self.page_ink
            or new_paper != self.page_paper
            or bool(enabled) != self.theme_recolor
        )
        self.page_ink = new_ink
        self.page_paper = new_paper
        self.theme_recolor = bool(enabled) and (new_ink is not None or new_paper is not None)
        if changed:
            self._page_cache.clear()
            self._cache_bytes = 0

    def clear_theme_page_colors(self) -> None:
        """Disable theme page recolor (source document colors)."""
        if self.theme_recolor or self.page_ink is not None or self.page_paper is not None:
            self.page_ink = None
            self.page_paper = None
            self.theme_recolor = False
            self._page_cache.clear()
            self._cache_bytes = 0

    def set_page_filter(self, name: str) -> str:
        """Set view filter: none | invert | sepia | grayscale | warm | cool."""
        key = (name or "none").lower().strip()
        if key not in self.FILTER_NAMES:
            key = "none"
        if key != self.page_filter:
            self.page_filter = key
            self._page_cache.clear()
            self._cache_bytes = 0
        return self.page_filter

    def set_brightness(self, value: float) -> float:
        self.brightness = max(0.5, min(1.5, float(value)))
        self._page_cache.clear()
        self._cache_bytes = 0
        return self.brightness

    def set_contrast(self, value: float) -> float:
        self.contrast = max(0.5, min(1.5, float(value)))
        self._page_cache.clear()
        self._cache_bytes = 0
        return self.contrast

    def adjust_brightness(self, delta: float) -> float:
        return self.set_brightness(self.brightness + float(delta))

    def adjust_contrast(self, delta: float) -> float:
        return self.set_contrast(self.contrast + float(delta))

    def reset_page_appearance(self) -> None:
        """Clear filters + brightness/contrast to defaults (keeps theme recolor)."""
        self.page_filter = "none"
        self.brightness = 1.0
        self.contrast = 1.0
        self._page_cache.clear()
        self._cache_bytes = 0

    def _appearance_key(self) -> tuple:
        """Cache key fragment for current view filters + theme recolor."""
        ink = self.page_ink or (None,)
        paper = self.page_paper or (None,)
        return (
            self.page_filter,
            round(self.brightness, 3),
            round(self.contrast, 3),
            bool(self.theme_recolor),
            ink,
            paper,
        )

    def _apply_theme_recolor(self, img):
        """Map page luminance onto theme paper/ink colors (PIL Image → Image)."""
        if not self.theme_recolor:
            return img
        from PIL import Image

        ink = self.page_ink or (0, 0, 0)
        paper = self.page_paper or (255, 255, 255)
        # Luminance: light source pixels → paper, dark → ink
        gray = img.convert("L")
        ir, ig, ib = ink
        pr, pg, pb = paper
        # Linear ramp out = ink + (paper - ink) * (lum/255) via 256-entry LUTs.
        # point() with a list runs at C speed — the old per-pixel Python loop
        # (float math per channel) cost seconds on fit-capped pages.
        lut_r = [int(ir + (pr - ir) * i / 255.0 + 0.5) for i in range(256)]
        lut_g = [int(ig + (pg - ig) * i / 255.0 + 0.5) for i in range(256)]
        lut_b = [int(ib + (pb - ib) * i / 255.0 + 0.5) for i in range(256)]
        return Image.merge(
            "RGB", (gray.point(lut_r), gray.point(lut_g), gray.point(lut_b))
        )

    def _apply_rgb_filter(
        self, w: int, h: int, data: bytes
    ) -> Tuple[int, int, bytes]:
        """Apply theme recolor + brightness/contrast + named filter to RGB24 bytes."""
        need = (
            self.theme_recolor
            or self.page_filter != "none"
            or abs(self.brightness - 1.0) > 1e-3
            or abs(self.contrast - 1.0) > 1e-3
        )
        if not need or w <= 0 or h <= 0 or not data:
            return (w, h, data)
        try:
            from PIL import Image, ImageEnhance, ImageOps

            img = Image.frombytes("RGB", (w, h), data)
            # Theme ink/paper first so named filters layer on top
            if self.theme_recolor:
                img = self._apply_theme_recolor(img)
            if abs(self.brightness - 1.0) > 1e-3:
                img = ImageEnhance.Brightness(img).enhance(self.brightness)
            if abs(self.contrast - 1.0) > 1e-3:
                img = ImageEnhance.Contrast(img).enhance(self.contrast)
            f = self.page_filter
            if f == "invert":
                img = ImageOps.invert(img)
            elif f == "grayscale":
                img = ImageOps.grayscale(img).convert("RGB")
            elif f == "sepia":
                g = ImageOps.grayscale(img)
                img = Image.merge(
                    "RGB",
                    (
                        g.point([min(255, int(x * 1.05)) for x in range(256)]),
                        g.point([min(255, int(x * 0.92)) for x in range(256)]),
                        g.point([min(255, int(x * 0.72)) for x in range(256)]),
                    ),
                )
            elif f == "warm":
                r, g, b = img.split()
                img = Image.merge(
                    "RGB",
                    (
                        r.point([min(255, int(x * 1.08)) for x in range(256)]),
                        g,
                        b.point([max(0, int(x * 0.90)) for x in range(256)]),
                    ),
                )
            elif f == "cool":
                r, g, b = img.split()
                img = Image.merge(
                    "RGB",
                    (
                        r.point([max(0, int(x * 0.92)) for x in range(256)]),
                        g,
                        b.point([min(255, int(x * 1.08)) for x in range(256)]),
                    ),
                )
            return (w, h, img.tobytes())
        except Exception as exc:  # noqa: BLE001
            print(f"page filter skipped: {exc}")
            return (w, h, data)

    def reset_zoom(self, zoom: Optional[float] = None) -> float:
        """Reset zoom to ZOOM_DEFAULT, or an explicit platform default."""
        target = self.ZOOM_DEFAULT if zoom is None else float(zoom)
        self.set_zoom(target)
        return self.zoom

    def adjust_zoom(self, delta: float) -> float:
        self.set_zoom(self.zoom + delta)
        return self.zoom

    def fine_zoom_in(self) -> float:
        return self.adjust_zoom(self.ZOOM_FINE)

    def fine_zoom_out(self) -> float:
        return self.adjust_zoom(-self.ZOOM_FINE)

    def coarse_zoom_in(self) -> float:
        return self.adjust_zoom(self.ZOOM_COARSE)

    def coarse_zoom_out(self) -> float:
        return self.adjust_zoom(-self.ZOOM_COARSE)

    def fit_zoom_for_viewport(
        self,
        avail_w: float,
        avail_h: float,
        *,
        mode: str = "width",
        margin: float = 24.0,
    ) -> float:
        """Compute zoom so the current view fits width, height, or page (both).

        mode: 'width' | 'height' | 'page' (min of both). Uses page/spread size at zoom=1.
        """
        if self.doc is None or self.page_count <= 0:
            return self.zoom
        w_pts, h_pts = self.get_view_size_at_zoom(1.0)
        if w_pts <= 1 or h_pts <= 1:
            return self.zoom
        aw = max(50.0, float(avail_w) - float(margin))
        ah = max(50.0, float(avail_h) - float(margin))
        zw = aw / float(w_pts)
        zh = ah / float(h_pts)
        m = (mode or "width").lower()
        if m in ("height", "fit_height"):
            target = zh
        elif m in ("page", "fit", "fit_page", "best"):
            target = min(zw, zh)
        else:
            target = zw  # width
        self.set_zoom(target)
        return self.zoom

    def get_view_size_at_zoom(self, zoom: float) -> Tuple[float, float]:
        """Page or spread size in points scaled by zoom (width, height)."""
        if self.doc is None:
            return (0.0, 0.0)
        pages = self.spread_pages()
        if not pages:
            return (0.0, 0.0)
        z = max(self.ZOOM_MIN, min(float(zoom), self.ZOOM_MAX))
        try:
            r0 = self.doc[pages[0]].rect
            w0, h0 = self._rotated_size(float(r0.width), float(r0.height))
            w = w0 * z
            h = h0 * z
            if len(pages) >= 2:
                r1 = self.doc[pages[1]].rect
                w1, h1 = self._rotated_size(float(r1.width), float(r1.height))
                # Side-by-side + spine gutter. Keep in lockstep with
                # _compose_spread_rgb's gap (max(10, int(14*z)) px) so the
                # logical size equals the rendered spread — otherwise
                # render_current smooth-scales EVERY book-mode frame.
                gutter = max(10.0, 14.0 * z)
                w = w + w1 * z + gutter
                h = max(h, h1 * z)
            return (w, h)
        except Exception:  # noqa: BLE001
            return (0.0, 0.0)

    # ----- rendering -----

    def _cache_get(self, key) -> Optional[dict]:
        """LRU get — moves hit to newest end."""
        item = self._page_cache.get(key)
        if item is not None:
            try:
                self._page_cache.move_to_end(key)
            except Exception:  # noqa: BLE001
                pass
        return item

    @staticmethod
    def _item_bytes(item: dict) -> int:
        """Approx heap cost of one cached RGB render."""
        return max(1, int(item.get("w", 0)) * int(item.get("h", 0)) * 3)

    def _cache_put(self, key, item: dict) -> None:
        """Store render payload with true LRU eviction under a byte budget."""
        if key in self._page_cache:
            self._cache_bytes = max(
                0, self._cache_bytes - self._item_bytes(self._page_cache[key])
            )
        self._page_cache[key] = item
        self._cache_bytes += self._item_bytes(item)
        try:
            self._page_cache.move_to_end(key)
        except Exception:  # noqa: BLE001
            pass
        # Evict oldest until under BOTH the byte budget and the entry cap.
        # Runs after inserts AND updates so a single oversized render is
        # dropped instead of silently blowing past MAX_CACHE_BYTES.
        while len(self._page_cache) and (
            self._cache_bytes > self.MAX_CACHE_BYTES
            or len(self._page_cache) >= self._cache_max
        ):
            try:
                _, victim = self._page_cache.popitem(last=False)
            except Exception:  # noqa: BLE001
                break
            self._cache_bytes = max(0, self._cache_bytes - self._item_bytes(victim))

    def _pixmap_to_rgb(self, pix) -> Optional[Tuple[int, int, bytes]]:
        """Normalize a fitz Pixmap to contiguous RGB24 bytes."""
        try:
            src = pix
            owned = False
            if getattr(pix, "alpha", False) or getattr(pix, "n", 3) != 3:
                # Gray (n==1) / CMYK / alpha → RGB in C (MuPDF). The old
                # pure-Python gray→RGB loop ran O(pixels) Python — seconds on
                # fit-capped pages. This path is now C-speed.
                src = fitz.Pixmap(fitz.csRGB, pix)
                owned = True
            w, h = int(src.width), int(src.height)
            n = int(getattr(src, "n", 3))
            samples = bytes(src.samples)
            if owned:
                try:
                    src = None  # noqa: F841 — drop ref for MuPDF
                except Exception:  # noqa: BLE001
                    pass
            if n == 1:
                # Expand gray → RGB
                out = bytearray(w * h * 3)
                si = 0
                di = 0
                for _ in range(w * h):
                    g = samples[si]
                    out[di] = g
                    out[di + 1] = g
                    out[di + 2] = g
                    si += 1
                    di += 3
                return (w, h, bytes(out))
            if n == 3:
                return (w, h, samples)
            return None
        except Exception as exc:  # noqa: BLE001
            print(f"Error converting pixmap: {exc}")
            return None

    def _effective_render_zoom(self, page: int, zoom: float, *, uncapped: bool) -> float:
        """Clamp a requested zoom to a sane rasterization budget.

        'Fit' zooms on large screens can exceed MAX_RENDER_ZOOM; rasterizing at
        that scale is pure waste since the pixmap is downscaled to the viewport.
        Export paths pass uncapped=True for full-quality output.
        """
        if uncapped:
            return round(float(zoom), 4)
        rz = min(float(zoom), self.MAX_RENDER_ZOOM)
        try:
            r = self.doc[page].rect  # page size in points
            area_pts = max(1.0, float(r.width) * float(r.height))
            max_z = math.sqrt(self.MAX_RENDER_PIXELS / area_pts)
            rz = min(rz, max_z)
        except Exception:  # noqa: BLE001
            pass
        return round(rz, 4)

    def _render_page_rgb(
        self, page: int, zoom: float, *, uncapped: bool = False
    ) -> Optional[Tuple[int, int, bytes]]:
        """Render one page to (width, height, RGB24 bytes), LRU-cached.

        View renders are capped (see _effective_render_zoom) so 'fit' never
        rasterizes absurd buffers; the caller rescales to the logical size.
        """
        if self.doc is None or not (0 <= page < self.page_count):
            return None
        z = self._effective_render_zoom(page, float(zoom), uncapped=uncapped)
        key = (page, z, "rgb", self._appearance_key(), self.rotation)
        hit = self._cache_get(key)
        if hit is not None:
            return (hit["w"], hit["h"], hit["rgb"])
        try:
            mat = fitz.Matrix(z, z)  # effective (capped) zoom — key and buffer agree
            if self.rotation:
                mat = mat.prerotate(self.rotation)  # view-only; +90 = clockwise
            pix = self.doc[page].get_pixmap(matrix=mat, alpha=False)
            rgb = self._pixmap_to_rgb(pix)
            if rgb is None:
                return None
            w, h, data = rgb
            w, h, data = self._apply_rgb_filter(w, h, data)
            self._cache_put(key, {"w": w, "h": h, "rgb": data})
            return (w, h, data)
        except Exception as exc:  # noqa: BLE001
            print(f"Error rendering page {page}: {exc}")
            return None

    def render_page(
        self, page: Optional[int] = None, zoom: Optional[float] = None
    ) -> Optional[bytes]:
        """Render a single page to PNG bytes (tests / export)."""
        if self.doc is None:
            return None
        idx = self.current_page if page is None else page
        if not (0 <= idx < self.page_count):
            return None
        z = self.zoom if zoom is None else float(zoom)
        rgb = self._render_page_rgb(idx, z, uncapped=True)
        if rgb is None:
            return None
        w, h, data = rgb
        # Prefer PIL PNG (fast enough, consistent); fallback to fitz
        try:
            from PIL import Image

            img = Image.frombytes("RGB", (w, h), data)
            buf = io.BytesIO()
            img.save(buf, format="PNG", optimize=False, compress_level=1)
            return buf.getvalue()
        except Exception:  # noqa: BLE001
            try:
                mat = fitz.Matrix(z, z)
                pix = self.doc[idx].get_pixmap(matrix=mat, alpha=False)
                return pix.tobytes("png")
            except Exception as exc:  # noqa: BLE001
                print(f"Error encoding PNG page {idx}: {exc}")
                return None

    def render_view_rgb(
        self, page: Optional[int] = None, zoom: Optional[float] = None
    ) -> Optional[Tuple[int, int, bytes]]:
        """Render current view (single or book spread) as RGB24 — no PNG round-trip."""
        if self.doc is None:
            return None
        pages = self.spread_pages(page)
        if not pages:
            return None
        z = self.zoom if zoom is None else float(zoom)
        if len(pages) == 1:
            return self._render_page_rgb(pages[0], z)

        # Key on the effective render zoom so capped fit zooms share one spread.
        zkey = self._effective_render_zoom(pages[0], float(z), uncapped=False)
        key = (tuple(pages), zkey, "spread-rgb", self._appearance_key(), self.rotation)
        hit = self._cache_get(key)
        if hit is not None:
            return (hit["w"], hit["h"], hit["rgb"])

        rgb = self._compose_spread_rgb(pages, z)
        if rgb is None:
            return self._render_page_rgb(pages[0], z)
        w, h, data = rgb
        self._cache_put(key, {"w": w, "h": h, "rgb": data})
        return (w, h, data)

    def render_view(
        self, page: Optional[int] = None, zoom: Optional[float] = None
    ) -> Optional[bytes]:
        """Render current view (single page or book spread) to PNG bytes."""
        rgb = self.render_view_rgb(page=page, zoom=zoom)
        if rgb is None:
            return None
        w, h, data = rgb
        try:
            from PIL import Image

            img = Image.frombytes("RGB", (w, h), data)
            buf = io.BytesIO()
            img.save(buf, format="PNG", optimize=False, compress_level=1)
            return buf.getvalue()
        except Exception:  # noqa: BLE001
            # Fallback: left page PNG only
            pages = self.spread_pages(page)
            if pages:
                return self.render_page(pages[0], zoom=zoom)
            return None

    def _compose_spread_rgb(
        self, pages: Sequence[int], z: float
    ) -> Optional[Tuple[int, int, bytes]]:
        """Stitch left+right pages to one RGB24 buffer with spine gutter."""
        parts: List[Tuple[int, int, bytes]] = []
        for i in pages:
            rgb = self._render_page_rgb(int(i), z)
            if rgb is None:
                return None
            parts.append(rgb)
        if not parts:
            return None
        gap = max(10, int(14 * z))
        total_w = sum(p[0] for p in parts) + gap * (len(parts) - 1)
        total_h = max(p[1] for p in parts)
        # Prefer PIL paste (fast C path); pure-Python row copy as fallback
        try:
            from PIL import Image

            board_img = Image.new("RGB", (total_w, total_h), (36, 40, 48))
            x = 0
            for wi, hi, data in parts:
                img = Image.frombytes("RGB", (wi, hi), data)
                y0 = (total_h - hi) // 2
                board_img.paste(img, (x, y0))
                x += wi + gap
            return (total_w, total_h, board_img.tobytes())
        except Exception:  # noqa: BLE001
            pass
        # bytes-multiply in C (no giant Python int list) then wrap — the old
        # [36, 40, 48] * N built a 3·pixels-int list first (huge on big spreads).
        board = bytearray(b"\x24\x28\x30" * (total_w * total_h))
        x = 0
        for wi, hi, data in parts:
            y0 = (total_h - hi) // 2
            row_src = wi * 3
            for row in range(hi):
                src_off = row * row_src
                dst_off = ((y0 + row) * total_w + x) * 3
                board[dst_off : dst_off + row_src] = data[src_off : src_off + row_src]
            x += wi + gap
        return (total_w, total_h, bytes(board))

    def get_page_size(self, page: Optional[int] = None) -> Tuple[float, float]:
        """Return (width, height) in points for a page."""
        if self.doc is None:
            return (0.0, 0.0)
        idx = self.current_page if page is None else page
        if not (0 <= idx < self.page_count):
            return (0.0, 0.0)
        rect = self.doc[idx].rect
        return (float(rect.width), float(rect.height))

    def spread_gap_pts(self) -> float:
        """Logical gutter between left/right pages in book mode (points).

        Kept in lockstep with the pixel gap used in ``_compose_spread_rgb``
        (``max(10, int(14 * z))`` → 14 pts at zoom 1.0).
        """
        return 14.0 if self.book_mode else 0.0

    def map_view_xy_to_page(self, x: float, y: float) -> Optional[Tuple[int, float, float]]:
        """Map a point in view/PDF-point space to (page_index, local_x, local_y).

        View space is the (rotated) page space: rotation moves the rendered
        image, and this mapping inverts it so click-to-edit still targets the
        right page spot. Used by click-to-edit so the right half of a book
        spread targets the right page. Returns None when nothing is open.
        """
        if self.doc is None:
            return None
        pages = self.spread_pages()
        if not pages:
            return None
        rot = self.rotation % 360

        def _local(pw: float, ph: float, vx: float, vy: float) -> Tuple[float, float]:
            """View-space (vx, vy) -> page-local (px, py) for one page."""
            if rot == 90:  # clockwise: page top-left lands image top-right
                px = vy
                py = ph - vx
            elif rot == 270:  # counter-clockwise
                px = pw - vy
                py = vx
            elif rot == 180:
                px = pw - vx
                py = ph - vy
            else:
                px, py = vx, vy
            if pw > 0:
                px = max(0.0, min(px, pw - 1.0))
            if ph > 0:
                py = max(0.0, min(py, ph - 1.0))
            return px, py

        if len(pages) == 1:
            pw, ph = self.get_page_size(pages[0])
            lx, ly = _local(pw, ph, float(x), float(y))
            return (pages[0], lx, ly)
        left = pages[0]
        right = pages[1]
        left_w, left_h = self.get_page_size(left)
        right_w, right_h = self.get_page_size(right)
        lw_rot, _ = self._rotated_size(left_w, left_h)
        gutter = self.spread_gap_pts()
        if float(x) <= lw_rot + gutter / 2.0:
            lx, ly = _local(left_w, left_h, float(x), float(y))
            return (left, lx, ly)
        lx, ly = _local(right_w, right_h, float(x) - lw_rot - gutter, float(y))
        return (right, lx, ly)

    def get_view_size(self, page: Optional[int] = None) -> Tuple[float, float]:
        """Logical size of current view in points (spread-aware, rotation-aware).

        Must stay in lockstep with ``get_view_size_at_zoom(1.0)`` so canvas
        hit-testing / set_page_metrics match the rendered pixmap after
        view-only rotation (90/270 swap width and height).
        """
        pages = self.spread_pages(page)
        if not pages:
            return (0.0, 0.0)
        sizes = [self._rotated_size(*self.get_page_size(i)) for i in pages]
        gap_pts = self.spread_gap_pts() if len(pages) > 1 else 0.0
        w = sum(s[0] for s in sizes) + gap_pts * (len(pages) - 1)
        h = max(s[1] for s in sizes)
        return (w, h)

    # ----- editing (PDF-oriented; best-effort on others) -----

    def add_text(
        self,
        text: str,
        page: Optional[int] = None,
        x: float = 72.0,
        y: float = 72.0,
        fontsize: float = 12.0,
        color: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> bool:
        """Insert text on a page (PDF write-back; may be limited on EPUB)."""
        if self.doc is None or not text:
            return False
        idx = self.current_page if page is None else page
        if not (0 <= idx < self.page_count):
            return False
        try:
            pg = self.doc[idx]
            pg.insert_text((x, y), text, fontsize=fontsize, color=color)
            self._page_cache.clear()
            self._cache_bytes = 0
            return True
        except Exception as exc:  # noqa: BLE001
            print(f"Error adding text: {exc}")
            return False

    def add_image(
        self,
        image_path: str,
        page: Optional[int] = None,
        rect: Optional[Tuple[float, float, float, float]] = None,
    ) -> bool:
        """Embed an image on a page. rect = (x0, y0, x1, y1) in points."""
        if self.doc is None:
            return False
        idx = self.current_page if page is None else page
        if not (0 <= idx < self.page_count):
            return False
        img = Path(image_path)
        if not img.is_file():
            return False
        try:
            pg = self.doc[idx]
            if rect is None:
                w, h = self.get_page_size(idx)
                box = fitz.Rect(72, 72, min(w - 72, 72 + 200), min(h - 72, 72 + 200))
            else:
                box = fitz.Rect(*rect)
            pg.insert_image(box, filename=str(img))
            self._page_cache.clear()
            self._cache_bytes = 0
            return True
        except Exception as exc:  # noqa: BLE001
            print(f"Error adding image: {exc}")
            return False

    def save(self, path: Optional[str] = None) -> bool:
        """Save/export the document. Non-PDF sources export to PDF when needed."""
        if self.doc is None:
            return False
        dest = path or self.path
        if not dest:
            return False
        dest_path = Path(dest)
        try:
            # If original wasn't PDF and destination is PDF (or unspecified non-pdf), export
            if dest_path.suffix.lower() != ".pdf" and not self.is_pdf:
                dest_path = dest_path.with_suffix(".pdf")
                dest = str(dest_path)
            if self.is_pdf and dest_path.suffix.lower() == ".pdf":
                self.doc.save(dest, incremental=False, encryption=fitz.PDF_ENCRYPT_NONE)
            else:
                # Convert / export via write
                self.doc.save(dest, incremental=False, encryption=fitz.PDF_ENCRYPT_NONE)
            self.path = str(dest)
            return True
        except Exception as exc:  # noqa: BLE001
            # Fallback: export pages to a fresh PDF
            try:
                return self._export_as_pdf(str(dest_path.with_suffix(".pdf")))
            except Exception as exc2:  # noqa: BLE001
                print(f"Error saving document: {exc} / {exc2}")
                return False

    def _export_as_pdf(self, dest: str) -> bool:
        if self.doc is None:
            return False
        out = fitz.open()
        try:
            if bool(getattr(self.doc, "is_pdf", False)):
                out.insert_pdf(self.doc)
            if len(out) == 0:
                # Rasterize each page into a PDF page (EPUB/XPS/etc.)
                for i in range(self.page_count):
                    pix = self.doc[i].get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                    w, h = pix.width, pix.height
                    page = out.new_page(width=w, height=h)
                    page.insert_image(page.rect, pixmap=pix)
            out.save(dest)
            self.path = dest
            return True
        finally:
            out.close()

    def export_page_png(
        self, dest: str, page: Optional[int] = None, zoom: float = 2.0
    ) -> bool:
        data = self.render_page(page=page, zoom=zoom)
        if not data:
            return False
        Path(dest).write_bytes(data)
        return True

    def get_metadata(self) -> dict:
        if self.doc is None:
            return {}
        meta = dict(self.doc.metadata or {})
        meta["page_count"] = self.page_count
        meta["path"] = self.path
        meta["format"] = self._format
        meta["book_mode"] = self.book_mode
        return meta

    def search(
        self, query: str, page: Optional[int] = None
    ) -> List[Tuple[int, Tuple[float, float, float, float]]]:
        """Search text; returns list of (page_index, rect_tuple)."""
        results: List[Tuple[int, Tuple[float, float, float, float]]] = []
        if self.doc is None or not query:
            return results
        pages: Sequence[int] = range(self.page_count) if page is None else [page]
        for idx in pages:
            if not (0 <= idx < self.page_count):
                continue
            try:
                for rect in self.doc[idx].search_for(query):
                    results.append((idx, (rect.x0, rect.y0, rect.x1, rect.y1)))
            except Exception:  # noqa: BLE001
                continue
        return results

    def render_page_qimage_bytes(self, page: Optional[int] = None) -> Optional[io.BytesIO]:
        """Convenience: PNG bytes in a BytesIO buffer for Qt loaders."""
        data = self.render_view(page=page) if self.book_mode else self.render_page(page=page)
        if not data:
            return None
        buf = io.BytesIO(data)
        buf.seek(0)
        return buf
