#!/usr/bin/env python3
"""Android-native PDF renderer using android.graphics.pdf.PdfRenderer (API 21+).

Accessed via pyjnius. Falls back gracefully when not on Android.
Returns RGB24 bytes compatible with Kivy Texture.blit_buffer.
"""

from __future__ import annotations

import os
from typing import Optional, Tuple

_ANDROID = hasattr(os, "getenv") and os.environ.get("REMEDYPDF_MOBILE") == "1"

# android.graphics.pdf.PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY
_RENDER_MODE_FOR_DISPLAY = 1


def _jclass(name: str):
    """Load a Java class through pyjnius (Python has no `import android.graphics`)."""
    from jnius import autoclass  # type: ignore

    return autoclass(name)


def _rgba_to_rgb(raw: bytes, w: int, h: int) -> bytes:
    """Drop alpha from tightly packed RGBA bytes (Bitmap ARGB_8888 memory order)."""
    n = w * h
    rgb = bytearray(n * 3)
    rgb[0::3] = raw[0 : n * 4 : 4]
    rgb[1::3] = raw[1 : n * 4 : 4]
    rgb[2::3] = raw[2 : n * 4 : 4]
    return bytes(rgb)


class AndroidPdfRenderer:
    """Render PDF pages using Android's native PdfRenderer."""

    def __init__(self):
        self._renderer = None
        self._fd = None
        self._page_count = 0
        self._current_page = 0
        self._path: Optional[str] = None
        self.zoom: float = 1.0

    @property
    def is_open(self) -> bool:
        return self._renderer is not None

    @property
    def page_count(self) -> int:
        return self._page_count

    @property
    def current_page(self) -> int:
        return self._current_page

    def open(self, path: str) -> bool:
        if not _ANDROID:
            return False
        fd = None
        try:
            PdfRenderer = _jclass("android.graphics.pdf.PdfRenderer")
            JFile = _jclass("java.io.File")
            ParcelFileDescriptor = _jclass("android.os.ParcelFileDescriptor")
            fd = ParcelFileDescriptor.open(
                JFile(path), ParcelFileDescriptor.MODE_READ_ONLY
            )
            renderer = PdfRenderer(fd)
            count = int(renderer.getPageCount())
        except Exception:
            if fd is not None:
                try:
                    fd.close()
                except Exception:
                    pass
            return False
        # Only replace the open document once the new one is usable.
        self.close()
        self._fd = fd
        self._renderer = renderer
        self._page_count = count
        self._current_page = 0
        self._path = path
        return True

    def close(self):
        if self._renderer:
            try:
                self._renderer.close()
            except Exception:
                pass
            self._renderer = None
        if self._fd:
            try:
                self._fd.close()
            except Exception:
                pass
            self._fd = None
        self._page_count = 0
        self._current_page = 0

    def next_page(self) -> bool:
        if self._current_page + 1 < self._page_count:
            self._current_page += 1
            return True
        return False

    def prev_page(self) -> bool:
        if self._current_page > 0:
            self._current_page -= 1
            return True
        return False

    def set_current_page(self, page: int) -> bool:
        if 0 <= page < self._page_count:
            self._current_page = page
            return True
        return False

    def adjust_zoom(self, delta: float):
        self.zoom = max(0.3, min(6.0, self.zoom + delta))

    def _render_page_rgb(
        self, page: int, zoom: float
    ) -> Optional[Tuple[int, int, bytes]]:
        if not self._renderer or not (0 <= page < self._page_count):
            return None
        try:
            Bitmap = _jclass("android.graphics.Bitmap")
            BitmapConfig = _jclass("android.graphics.Bitmap$Config")
            Canvas = _jclass("android.graphics.Canvas")
            Matrix = _jclass("android.graphics.Matrix")
            ByteBuffer = _jclass("java.nio.ByteBuffer")
            pg = self._renderer.openPage(page)
            try:
                w = int(pg.getWidth() * zoom)
                h = int(pg.getHeight() * zoom)
                if w <= 0 or h <= 0:
                    return None
                bitmap = Bitmap.createBitmap(w, h, BitmapConfig.ARGB_8888)
                canvas = Canvas(bitmap)
                canvas.drawColor(-1)  # opaque white (0xFFFFFFFF as a Java int)
                matrix = Matrix()
                matrix.setScale(float(zoom), float(zoom))
                pg.render(bitmap, None, matrix, _RENDER_MODE_FOR_DISPLAY)
            finally:
                pg.close()
            buf = ByteBuffer.allocate(w * h * 4)
            bitmap.copyPixelsToBuffer(buf)
            arr = buf.array()
            raw = arr.tostring() if hasattr(arr, "tostring") else bytes(
                b & 0xFF for b in arr
            )
            bitmap.recycle()
            return (w, h, _rgba_to_rgb(raw, w, h))
        except Exception:
            return None
