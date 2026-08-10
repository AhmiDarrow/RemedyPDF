#!/usr/bin/env python3
"""Android-native PDF renderer using android.graphics.pdf.PdfRenderer (API 21+).

Accessed via pyjnius. Falls back gracefully when not on Android.
Returns RGB24 bytes compatible with Kivy Texture.blit_buffer.
"""

from __future__ import annotations

import os
from typing import Optional, Tuple

_ANDROID = hasattr(os, "getenv") and os.environ.get("REMEDYPDF_MOBILE") == "1"


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
        try:
            from android.graphics.pdf import PdfRenderer
            from java.io import File as JFile
            from android.os import ParcelFileDescriptor
            jfile = JFile(path)
            self._fd = ParcelFileDescriptor.open(
                jfile, ParcelFileDescriptor.MODE_READ_ONLY
            )
            self._renderer = PdfRenderer(self._fd)
            self._page_count = self._renderer.getPageCount()
            self._current_page = 0
            self._path = path
            return True
        except Exception:
            return False

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
            from android.graphics import Bitmap, Canvas, Paint, Matrix
            from java.nio import ByteBuffer
            pg = self._renderer.openPage(page)
            w = int(pg.getWidth() * zoom)
            h = int(pg.getHeight() * zoom)
            if w <= 0 or h <= 0:
                pg.close()
                return None
            bitmap = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888)
            canvas = Canvas(bitmap)
            canvas.drawColor(0xFFFFFFFF)
            matrix = Matrix()
            matrix.setScale(zoom, zoom)
            pg.render(bitmap, None, matrix, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY)
            pg.close()
            buf = ByteBuffer.allocate(w * h * 4)
            bitmap.copyPixelsToBuffer(buf)
            buf.rewind()
            raw = bytearray(w * h * 4)
            buf.get(raw)
            buf_array = bytes(raw)
            rgb = bytearray(w * h * 3)
            for i in range(w * h):
                src = i * 4
                dst = i * 3
                rgb[dst] = buf_array[src + 2]
                rgb[dst + 1] = buf_array[src + 1]
                rgb[dst + 2] = buf_array[src]
            bitmap.recycle()
            return (w, h, bytes(rgb))
        except Exception:
            return None
