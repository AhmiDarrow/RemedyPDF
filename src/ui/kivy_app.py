#!/usr/bin/env python3
"""Kivy-based Android PDF viewer for RemedyPDF.

Uses the existing PDFEngine (src/core/pdf_engine.py) for rendering.
PyQt5 is *not* imported here — this is a standalone Kivy UI for Android.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure project root is importable
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("REMEDYPDF_MOBILE", "1")

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics.texture import Texture
from kivy.properties import (
    BooleanProperty,
    NumericProperty,
    ObjectProperty,
    StringProperty,
)
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scatter import Scatter
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.textinput import TextInput

from src import __version__ as VERSION

# Try PyMuPDF engine first (desktop). On Android, use native PdfRenderer.
_PDF_ENGINE = None
_ANDROID_RENDERER = None
try:
    from src.core.pdf_engine import PDFEngine as _PDFEngine

    _PDF_ENGINE = _PDFEngine
except ImportError:
    pass
if _PDF_ENGINE is None:
    try:
        from src.ui.android_renderer import AndroidPdfRenderer as _AndroidRenderer

        _ANDROID_RENDERER = _AndroidRenderer
    except ImportError:
        pass


class PDFViewer(Scatter):
    """Pinch-zoomable, pannable PDF page display using a Kivy Image + Texture."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.do_rotation = False
        self.do_scale = True
        self.do_translation = True
        self.auto_bring_to_front = False
        self.scale_min = 0.3
        self.scale_max = 6.0

        self._image = Image(
            size_hint=(None, None),
            allow_stretch=True,
            keep_ratio=True,
        )
        self.add_widget(self._image)
        self._texture: Texture | None = None

    def show_rgb(self, w: int, h: int, data: bytes) -> None:
        """Display RGB24 bytes as a Kivy texture."""
        if not data or w <= 0 or h <= 0:
            self._image.texture = None
            return
        tex = Texture.create(size=(w, h), colorfmt="rgb", bufferfmt="ubyte")
        tex.blit_buffer(data, colorfmt="rgb", bufferfmt="ubyte")
        tex.flip_vertical()
        self._image.texture = tex
        self._image.size = (w, h)
        self._texture = tex
        self.transform = self.transform.identity()
        self._fit_to_window(w, h)

    def _fit_to_window(self, img_w: int, img_h: int) -> None:
        """Scale so the page fits width (initial view)."""
        win_w, win_h = Window.width, Window.height
        if img_w <= 0 or win_w <= 0:
            return
        scale = win_w / img_w
        self.scale = scale
        # Center vertically
        self.pos = (0, max(0, (win_h - img_h * scale) / 2))


class MainScreen(Screen):
    """Main PDF viewer screen with toolbar."""

    engine: PDFEngine = ObjectProperty(None)
    current_label: Label = ObjectProperty(None)
    viewer: PDFViewer = ObjectProperty(None)
    page_input: TextInput = ObjectProperty(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if _PDF_ENGINE is not None:
            self.engine = _PDF_ENGINE(zoom=1.0)
        elif _ANDROID_RENDERER is not None:
            self.engine = _ANDROID_RENDERER()
        else:
            self.engine = None
        self._last_touch_x: float = 0.0
        self._touch_start_x: float = 0.0
        self._swipe_threshold: int = 80  # px for page turn swipe

    def on_enter(self, *args):
        """Build UI programmatically when the screen is entered."""
        self.clear_widgets()

        # Main vertical layout
        root = BoxLayout(orientation="vertical")

        # ---- Toolbar ----
        toolbar = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=52,
            padding=[6, 4],
            spacing=6,
        )

        btn_open = Button(text="Open", size_hint_x=None, width=70)
        btn_open.bind(on_release=self._on_open)
        toolbar.add_widget(btn_open)

        btn_prev = Button(text="◀", size_hint_x=None, width=52)
        btn_prev.bind(on_release=lambda _: self._go_prev())
        toolbar.add_widget(btn_prev)

        self.page_input = TextInput(
            text="1",
            size_hint_x=None,
            width=60,
            multiline=False,
            input_filter="int",
            halign="center",
        )
        self.page_input.bind(on_text_validate=self._on_page_input)
        toolbar.add_widget(self.page_input)

        self.current_label = Label(
            text="/ 1",
            size_hint_x=None,
            width=60,
            halign="left",
            valign="middle",
        )
        self.current_label.bind(size=self.current_label.setter("text_size"))
        toolbar.add_widget(self.current_label)

        btn_next = Button(text="▶", size_hint_x=None, width=52)
        btn_next.bind(on_release=lambda _: self._go_next())
        toolbar.add_widget(btn_next)

        btn_zoom_out = Button(text="−", size_hint_x=None, width=44)
        btn_zoom_out.bind(on_release=lambda _: self._zoom(-0.15))
        toolbar.add_widget(btn_zoom_out)

        btn_zoom_in = Button(text="+", size_hint_x=None, width=44)
        btn_zoom_in.bind(on_release=lambda _: self._zoom(0.15))
        toolbar.add_widget(btn_zoom_in)

        toolbar.add_widget(Label(size_hint_x=1))  # spacer

        root.add_widget(toolbar)

        # ---- PDF Viewer (pinch-zoom scatter) ----
        self.viewer = PDFViewer()
        root.add_widget(self.viewer)

        # ---- Status bar ----
        status = Label(
            text=f"RemedyPDF {VERSION} — Android",
            size_hint_y=None,
            height=28,
            halign="center",
            valign="middle",
            font_size=11,
            color=(0.5, 0.5, 0.5, 1),
        )
        status.bind(size=status.setter("text_size"))
        root.add_widget(status)

        self.add_widget(root)
        self._update_page_display()

        # Keyboard: left/right for page turns
        if Window:
            Window.bind(on_key_down=self._on_key_down)

    # ---- Input handlers ----

    def on_touch_down(self, touch):
        if touch.is_double_tap:
            self._zoom(0.3 if self.engine.zoom < 2.0 else -0.5)
            return True
        self._touch_start_x = touch.x
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        dx = touch.x - self._touch_start_x
        # Swipe detection (not if the scatter is zoomed in and panning)
        if self.viewer.scale <= 1.5 and abs(dx) > self._swipe_threshold:
            if dx < 0:
                self._go_next()
            else:
                self._go_prev()
            return True
        return super().on_touch_up(touch)

    def _on_key_down(self, window, key, *args):
        """Keyboard navigation (useful for desktop testing)."""
        from kivy.core.window import Keyboard

        if key == Keyboard.keycodes.get("right", 275):
            self._go_next()
            return True
        elif key == Keyboard.keycodes.get("left", 276):
            self._go_prev()
            return True
        return False

    # ---- Navigation ----

    def _go_next(self):
        if self.engine.next_page():
            self._update_page_display()

    def _go_prev(self):
        if self.engine.prev_page():
            self._update_page_display()

    def _on_page_input(self, instance):
        try:
            page = int(instance.text) - 1  # 0-based
            if self.engine.set_current_page(page):
                self._update_page_display()
        except ValueError:
            pass
        # Always reset to current
        Clock.schedule_once(lambda dt: self._sync_page_input(), 0.05)

    def _zoom(self, delta: float):
        self.engine.adjust_zoom(delta)
        self._update_page_display()

    # ---- Display update ----

    def _update_page_display(self):
        """Render current page and update the viewer."""
        if self.engine is None or not self.engine.is_open:
            self.viewer.show_rgb(0, 0, b"")
            self.current_label.text = "/ 0"
            return

        page = self.engine.current_page
        zoom = self.engine.zoom
        total = self.engine.page_count

        # Render via the engine's internal RGB24 method (no PyQt5 dependency)
        result = self.engine._render_page_rgb(page, zoom)
        if result is not None:
            w, h, data = result
            self.viewer.show_rgb(w, h, data)
        else:
            self.viewer.show_rgb(0, 0, b"")

        self._sync_page_input()
        self.current_label.text = f"/ {total}"

    def _sync_page_input(self):
        if self.page_input and self.engine is not None and self.engine.is_open:
            self.page_input.text = str(self.engine.current_page + 1)

    # ---- File open ----

    def _on_open(self, instance):
        """Open a file chooser popup."""
        content = BoxLayout(orientation="vertical", spacing=8, padding=8)

        filechooser = FileChooserListView(
            filters=["*.pdf", "*.epub", "*.xps", "*.cbz", "*.cbr", "*.fb2",
                      "*.mobi", "*.svg", "*.docx", "*.txt",
                      "*.png", "*.jpg", "*.jpeg", "*.bmp", "*.gif", "*.webp"],
            path=str(Path.home() / "Documents") if os.name == "nt" else "/sdcard",
        )
        content.add_widget(filechooser)

        buttons = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=48,
            spacing=8,
        )
        btn_cancel = Button(text="Cancel")
        btn_open_sel = Button(text="Open Selected")

        popup = Popup(
            title="Open Document",
            content=content,
            size_hint=(0.95, 0.85),
            auto_dismiss=False,
        )

        def _cancel(btn):
            popup.dismiss()

        def _open_selected(btn):
            sel = filechooser.selection
            if sel:
                path = sel[0]
                if self.engine.open(path):
                    self._update_page_display()
                else:
                    err = Popup(
                        title="Error",
                        content=Label(text=f"Could not open:\n{path}"),
                        size_hint=(0.7, 0.3),
                    )
                    err.open()
            popup.dismiss()

        btn_cancel.bind(on_release=_cancel)
        btn_open_sel.bind(on_release=_open_selected)
        buttons.add_widget(btn_cancel)
        buttons.add_widget(btn_open_sel)
        content.add_widget(buttons)

        popup.open()


class RemedyPDFApp(App):
    """Kivy application entry for Android (and desktop test)."""

    title = "RemedyPDF"

    def build(self):
        self.icon = str(ROOT / "resources" / "icon.png")
        sm = ScreenManager()
        sm.add_widget(MainScreen(name="main"))
        return sm

    def on_start(self):
        """Load a test PDF if passed as argument."""
        if len(sys.argv) > 1:
            path = sys.argv[1]
            screen = self.root.get_screen("main")
            if screen.engine.open(path):
                screen._update_page_display()


def main() -> int:
    """Entry point — run the Kivy app."""
    app = RemedyPDFApp()
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
