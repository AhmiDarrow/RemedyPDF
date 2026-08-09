#!/usr/bin/env python3
"""RemedyPDF Application - Main window and controller."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional, Tuple

from PyQt5.QtCore import Qt, QByteArray
from PyQt5.QtGui import QIcon, QKeySequence, QPixmap, QImage, QWheelEvent
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QSpinBox,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
    QShortcut,
)

from .pdf_engine import OPEN_FILTER, SAVE_FILTER, PDFEngine, SUPPORTED_EXTENSIONS

try:
    from src import (
        GITHUB_OWNER,
        GITHUB_REPO,
        __app_name__ as APP_NAME,
        __version__ as VERSION,
    )
except ImportError:  # script-style / flat src on path
    try:
        from __init__ import (  # type: ignore
            GITHUB_OWNER,
            GITHUB_REPO,
            __app_name__ as APP_NAME,
            __version__ as VERSION,
        )
    except ImportError:
        APP_NAME = "RemedyPDF"
        VERSION = "1.2.0"
        GITHUB_OWNER = "AhmiDarrow"
        GITHUB_REPO = "RemedyPDF"

try:
    from ui.theme import DEFAULT_THEME, apply_theme, toggle_theme
    from ui.widgets import PDFCanvas, PageNavigator, SearchBar
    from ui.about import AboutDialog
    from utils.brand import apply_app_icon, resources_dir
    from utils.mobile import (
        apply_mobile_attribute,
        is_mobile,
        is_touch_primary,
        recommended_default_zoom,
        recommended_window_size,
        touch_target_px,
    )
    from utils.updater import check_for_update, format_update_message, open_url
except ImportError:  # script-style imports
    from src.ui.theme import DEFAULT_THEME, apply_theme, toggle_theme  # type: ignore
    from src.ui.widgets import PDFCanvas, PageNavigator, SearchBar  # type: ignore
    from src.ui.about import AboutDialog  # type: ignore
    from src.utils.brand import apply_app_icon, resources_dir  # type: ignore
    from src.utils.mobile import (  # type: ignore
        apply_mobile_attribute,
        is_mobile,
        is_touch_primary,
        recommended_default_zoom,
        recommended_window_size,
        touch_target_px,
    )
    from src.utils.updater import (  # type: ignore
        check_for_update,
        format_update_message,
        open_url,
    )

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RESOURCES_DIR = resources_dir()


class RemedyPDFApp(QMainWindow):
    """Main window — themes, fine zoom, both-sides book mode, mobile APK polish."""

    def __init__(self) -> None:
        super().__init__()
        self._mobile = is_mobile()
        self._touch = is_touch_primary() or self._mobile
        default_zoom = recommended_default_zoom()
        self.engine = PDFEngine(zoom=default_zoom)
        # Book mode always shows both sides (0+1, 2+3, …)
        self.engine.book_cover_alone = False
        self.current_path: Optional[str] = None
        self._theme = DEFAULT_THEME
        self._search_hits: List[Tuple[int, Tuple[float, float, float, float]]] = []
        self._search_index = -1
        self._search_fresh: bool = False  # Enter after find: don't skip first hit
        self._dirty: bool = False
        self._edit_dialog_open: bool = False
        self._build_ui()
        self._build_menus()
        self._build_toolbar()
        self._build_shortcuts()
        # Ctrl+wheel is often eaten by QScrollArea — filter viewport + canvas
        self.scroll.viewport().installEventFilter(self)
        self.canvas.installEventFilter(self)
        apply_theme(QApplication.instance() or self, self._theme, mobile=self._mobile or self._touch)
        self._update_status()

    # ----- UI construction -----

    def _build_ui(self) -> None:
        self.setWindowTitle(f"{APP_NAME} {VERSION}")
        w, h = recommended_window_size()
        self.resize(w, h)
        if self._mobile:
            self.setMinimumSize(320, 480)
        apply_app_icon(self)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.search_bar = SearchBar()
        self.search_bar.hide()
        self.search_bar.search_requested.connect(self._on_search)
        self.search_bar.next_result.connect(self._search_next)
        self.search_bar.prev_result.connect(self._search_prev)
        self.search_bar.closed.connect(self._on_search_closed)
        layout.addWidget(self.search_bar)

        self.scroll = QScrollArea()
        # False: canvas keeps full spread pixel size so both book pages show
        # (True squeezed the label to the viewport and clipped the right page).
        self.scroll.setWidgetResizable(False)
        self.scroll.setAlignment(Qt.AlignCenter)
        # Touch-friendly flick scrolling on APK / mobile
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        try:
            self.scroll.viewport().setAttribute(Qt.WA_AcceptTouchEvents, True)
        except Exception:  # noqa: BLE001
            pass

        self.canvas = PDFCanvas()
        # Edit: double-click (PC) / long-press (mobile) — ONLY edit_at (unified).
        # Do not also connect double_clicked_at / long_pressed_at or the dialog opens twice.
        self.canvas.set_touch_mode(self._touch or self._mobile)
        self.canvas.edit_at.connect(self._on_canvas_edit)
        if self._touch or self._mobile:
            self.canvas.setToolTip("Hold on the page to add text")
        else:
            self.canvas.setToolTip("Double-click the page to add text")
        self.scroll.setWidget(self.canvas)
        layout.addWidget(self.scroll, 1)

        self.navigator = PageNavigator()
        self.navigator.page_changed.connect(self._on_nav_page)
        layout.addWidget(self.navigator)

        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar())

    def _build_menus(self) -> None:
        menubar = self.menuBar()

        file_menu = menubar.addMenu("&File")
        open_act = QAction("&Open…", self)
        open_act.setShortcut(QKeySequence.Open)
        open_act.triggered.connect(lambda: self.open_document())
        file_menu.addAction(open_act)

        save_act = QAction("&Save", self)
        save_act.setShortcut(QKeySequence.Save)
        save_act.triggered.connect(self.save_document)
        file_menu.addAction(save_act)

        save_as_act = QAction("Save &As…", self)
        save_as_act.setShortcut(QKeySequence.SaveAs)
        save_as_act.triggered.connect(self.save_document_as)
        file_menu.addAction(save_as_act)

        file_menu.addSeparator()
        quit_act = QAction("&Quit", self)
        quit_act.setShortcut(QKeySequence.Quit)
        quit_act.triggered.connect(self.close)
        file_menu.addAction(quit_act)

        edit_menu = menubar.addMenu("&Edit")
        add_text_act = QAction("Add &Text…", self)
        add_text_act.setShortcut("Ctrl+T")
        add_text_act.triggered.connect(self.add_text)
        edit_menu.addAction(add_text_act)

        add_image_act = QAction("Add &Image…", self)
        add_image_act.triggered.connect(self.add_image)
        edit_menu.addAction(add_image_act)

        find_act = QAction("&Find…", self)
        find_act.setShortcut(QKeySequence.Find)
        find_act.triggered.connect(self._show_find)
        edit_menu.addAction(find_act)

        view_menu = menubar.addMenu("&View")
        zoom_in = QAction("Zoom &In", self)
        zoom_in.setShortcut(QKeySequence.ZoomIn)
        zoom_in.triggered.connect(lambda: self.adjust_zoom(PDFEngine.ZOOM_COARSE))
        view_menu.addAction(zoom_in)

        zoom_out = QAction("Zoom &Out", self)
        zoom_out.setShortcut(QKeySequence.ZoomOut)
        zoom_out.triggered.connect(lambda: self.adjust_zoom(-PDFEngine.ZOOM_COARSE))
        view_menu.addAction(zoom_out)

        fine_in = QAction("Fine Zoom In (1%)", self)
        fine_in.setShortcut("Ctrl+Shift+=")
        fine_in.triggered.connect(lambda: self.adjust_zoom(PDFEngine.ZOOM_FINE))
        view_menu.addAction(fine_in)

        fine_out = QAction("Fine Zoom Out (1%)", self)
        fine_out.setShortcut("Ctrl+Shift+-")
        fine_out.triggered.connect(lambda: self.adjust_zoom(-PDFEngine.ZOOM_FINE))
        view_menu.addAction(fine_out)

        fit_act = QAction("&Reset Zoom", self)
        fit_act.setShortcut("Ctrl+0")
        fit_act.setToolTip("Reset zoom to default (Ctrl+0)")
        fit_act.triggered.connect(self.reset_zoom)
        view_menu.addAction(fit_act)

        view_menu.addSeparator()
        self.book_act = QAction("&Book Mode", self)
        self.book_act.setCheckable(True)
        self.book_act.setShortcut("Ctrl+B")
        self.book_act.setToolTip("Two-page spread — both sides (0+1, 2+3, …)")
        self.book_act.triggered.connect(self.toggle_book_mode)
        view_menu.addAction(self.book_act)

        view_menu.addSeparator()
        theme_act = QAction("Toggle &Theme", self)
        theme_act.setShortcut("Ctrl+Shift+T")
        theme_act.triggered.connect(self._toggle_theme)
        view_menu.addAction(theme_act)

        go_menu = menubar.addMenu("&Go")
        prev_act = QAction("&Previous Page", self)
        prev_act.setShortcut(QKeySequence.MoveToPreviousPage)
        prev_act.triggered.connect(self.prev_page)
        go_menu.addAction(prev_act)

        next_act = QAction("&Next Page", self)
        next_act.setShortcut(QKeySequence.MoveToNextPage)
        next_act.triggered.connect(self.next_page)
        go_menu.addAction(next_act)

        first_act = QAction("&First Page", self)
        first_act.setShortcut("Home")
        first_act.triggered.connect(lambda: self._goto_page(0))
        go_menu.addAction(first_act)

        last_act = QAction("&Last Page", self)
        last_act.setShortcut("End")
        last_act.triggered.connect(
            lambda: self._goto_page(max(0, self.engine.page_count - 1))
        )
        go_menu.addAction(last_act)

        help_menu = menubar.addMenu("&Help")
        about_act = QAction("&About", self)
        about_act.triggered.connect(self.show_about)
        help_menu.addAction(about_act)

        update_act = QAction("Check for &Updates…", self)
        update_act.triggered.connect(self.check_for_updates)
        help_menu.addAction(update_act)

        shortcuts_act = QAction("&Keyboard Shortcuts", self)
        shortcuts_act.triggered.connect(self.show_shortcuts)
        help_menu.addAction(shortcuts_act)

    def _build_toolbar(self) -> None:
        tb = QToolBar("Main")
        tb.setMovable(False)
        self.addToolBar(tb)

        open_btn = QAction("Open", self)
        open_btn.setToolTip("Open document (Ctrl+O)")
        open_btn.triggered.connect(lambda: self.open_document())
        tb.addAction(open_btn)

        save_btn = QAction("Save", self)
        save_btn.setToolTip("Save (Ctrl+S)")
        save_btn.triggered.connect(self.save_document)
        tb.addAction(save_btn)
        tb.addSeparator()

        prev_btn = QAction("Prev", self)
        prev_btn.setToolTip("Previous page (← / PgUp)")
        prev_btn.triggered.connect(self.prev_page)
        tb.addAction(prev_btn)

        self.page_spin = QSpinBox()
        self.page_spin.setMinimum(1)
        self.page_spin.setMaximum(1)
        self.page_spin.setToolTip("Current page")
        self.page_spin.valueChanged.connect(self._on_page_spin)
        tb.addWidget(self.page_spin)

        next_btn = QAction("Next", self)
        next_btn.setToolTip("Next page (→ / PgDown)")
        next_btn.triggered.connect(self.next_page)
        tb.addAction(next_btn)
        tb.addSeparator()

        zin = QAction("Zoom+", self)
        zin.setToolTip("Zoom in 15% (Ctrl++) — hold Ctrl+Wheel for 1%")
        zin.triggered.connect(lambda: self.adjust_zoom(PDFEngine.ZOOM_COARSE))
        tb.addAction(zin)

        self.zoom_label = QLabel(" 125% ")
        self.zoom_label.setObjectName("mutedLabel")
        self.zoom_label.setMinimumWidth(52)
        self.zoom_label.setAlignment(Qt.AlignCenter)
        tb.addWidget(self.zoom_label)

        zout = QAction("Zoom-", self)
        zout.setToolTip("Zoom out 15% (Ctrl+-) — hold Ctrl+Wheel for 1%")
        zout.triggered.connect(lambda: self.adjust_zoom(-PDFEngine.ZOOM_COARSE))
        tb.addAction(zout)

        reset_zoom_btn = QAction("Reset", self)
        reset_zoom_btn.setToolTip("Reset zoom to default (Ctrl+0)")
        reset_zoom_btn.triggered.connect(self.reset_zoom)
        tb.addAction(reset_zoom_btn)
        tb.addSeparator()

        self.book_tb = QAction("Book", self)
        self.book_tb.setCheckable(True)
        self.book_tb.setToolTip("Book mode — both sides / two-page spread (Ctrl+B)")
        self.book_tb.triggered.connect(self.toggle_book_mode)
        tb.addAction(self.book_tb)

        find_btn = QAction("Find", self)
        find_btn.setToolTip("Find (Ctrl+F)")
        find_btn.triggered.connect(self._show_find)
        tb.addAction(find_btn)

    def _build_shortcuts(self) -> None:
        # Arrow / page navigation
        QShortcut(QKeySequence(Qt.Key_Left), self, activated=self.prev_page)
        QShortcut(QKeySequence(Qt.Key_Right), self, activated=self.next_page)
        QShortcut(QKeySequence(Qt.Key_PageUp), self, activated=self.prev_page)
        QShortcut(QKeySequence(Qt.Key_PageDown), self, activated=self.next_page)
        QShortcut(QKeySequence(Qt.Key_Space), self, activated=self.next_page)
        QShortcut(QKeySequence("Shift+Space"), self, activated=self.prev_page)

        # Coarse zoom — Ctrl++ / Ctrl+- (and = key without shift)
        QShortcut(QKeySequence.ZoomIn, self, activated=lambda: self.adjust_zoom(PDFEngine.ZOOM_COARSE))
        QShortcut(QKeySequence.ZoomOut, self, activated=lambda: self.adjust_zoom(-PDFEngine.ZOOM_COARSE))
        QShortcut(QKeySequence("Ctrl+="), self, activated=lambda: self.adjust_zoom(PDFEngine.ZOOM_COARSE))
        QShortcut(QKeySequence("Ctrl+-"), self, activated=lambda: self.adjust_zoom(-PDFEngine.ZOOM_COARSE))
        QShortcut(QKeySequence("Ctrl++"), self, activated=lambda: self.adjust_zoom(PDFEngine.ZOOM_COARSE))

        # Fine zoom — Ctrl+Alt +/- and Ctrl+Shift +/-
        QShortcut(QKeySequence("Ctrl+Alt+="), self, activated=lambda: self.adjust_zoom(PDFEngine.ZOOM_FINE))
        QShortcut(QKeySequence("Ctrl+Alt+-"), self, activated=lambda: self.adjust_zoom(-PDFEngine.ZOOM_FINE))
        QShortcut(QKeySequence("Ctrl+Shift+="), self, activated=lambda: self.adjust_zoom(PDFEngine.ZOOM_FINE))
        QShortcut(QKeySequence("Ctrl+Shift+-"), self, activated=lambda: self.adjust_zoom(-PDFEngine.ZOOM_FINE))
        QShortcut(QKeySequence("Ctrl+Shift++"), self, activated=lambda: self.adjust_zoom(PDFEngine.ZOOM_FINE))
        # Reset zoom
        QShortcut(QKeySequence("Ctrl+0"), self, activated=self.reset_zoom)

        # Wheel fine-zoom: wheelEvent + eventFilter (scroll area steals wheel)

    # ----- wheel: Ctrl = fine 1%; Ctrl+Shift = coarse 15% -----

    def _zoom_from_wheel(self, event: QWheelEvent) -> bool:
        """Handle Ctrl(+Shift)+wheel zoom. Returns True if consumed."""
        if not (event.modifiers() & Qt.ControlModifier):
            return False
        delta = event.angleDelta().y()
        if delta == 0:
            # Trackpads sometimes report pixelDelta only
            delta = event.pixelDelta().y()
        if delta == 0:
            return True
        if event.modifiers() & Qt.ShiftModifier:
            step = PDFEngine.ZOOM_COARSE if delta > 0 else -PDFEngine.ZOOM_COARSE
        else:
            step = PDFEngine.ZOOM_FINE if delta > 0 else -PDFEngine.ZOOM_FINE
        self.adjust_zoom(step)
        return True

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        if self._zoom_from_wheel(event):
            event.accept()
            return
        super().wheelEvent(event)

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        # QScrollArea viewport consumes wheel for panning — intercept Ctrl+wheel for zoom
        try:
            from PyQt5.QtCore import QEvent

            if event.type() == QEvent.Wheel and obj in (
                self.scroll.viewport(),
                self.canvas,
            ):
                if self._zoom_from_wheel(event):
                    return True
        except Exception:  # noqa: BLE001
            pass
        return super().eventFilter(obj, event)

    # ----- file ops -----

    def open_document(self, path: Optional[str] = None) -> None:
        if not path:
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Open Document",
                str(Path.home()),
                OPEN_FILTER,
            )
        if not path:
            return
        # Guard: don't silently discard unsaved edits when opening another file
        if self._dirty and self.engine.is_open and not self._is_headless():
            reply = QMessageBox.question(
                self,
                APP_NAME,
                "You have unsaved changes.\n\nSave before opening another document?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save,
            )
            if reply == QMessageBox.Cancel:
                return
            if reply == QMessageBox.Save:
                self.save_document()
                if self._dirty:
                    return  # save cancelled/failed
        if not self.engine.open(path):
            QMessageBox.critical(self, APP_NAME, f"Could not open:\n{path}")
            return
        self.current_path = path
        self._dirty = False
        self._search_hits = []
        self._search_index = -1
        self._sync_page_controls()
        self.render_current()
        self._update_status()

    # Back-compat alias used by older callers / tests
    def open_pdf(self, path: Optional[str] = None) -> None:
        self.open_document(path)

    def save_document(self) -> None:
        if not self.engine.is_open:
            QMessageBox.information(self, APP_NAME, "No document open.")
            return
        dest = self.current_path
        if not dest or not str(dest).lower().endswith(".pdf"):
            self.save_document_as()
            return
        if self.engine.save(dest):
            self._dirty = False
            self.statusBar().showMessage(f"Saved {dest}", 3000)
            self._update_status()
        else:
            QMessageBox.critical(self, APP_NAME, "Save failed.")

    def save_pdf(self) -> None:
        self.save_document()

    def save_document_as(self) -> None:
        if not self.engine.is_open:
            QMessageBox.information(self, APP_NAME, "No document open.")
            return
        default = self.current_path or str(Path.home() / "document.pdf")
        if not default.lower().endswith(".pdf"):
            default = str(Path(default).with_suffix(".pdf"))
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save As PDF",
            default,
            SAVE_FILTER,
        )
        if not path:
            return
        if self.engine.save(path):
            self.current_path = path
            self._dirty = False
            self.statusBar().showMessage(f"Saved {path}", 3000)
            self._update_status()
        else:
            QMessageBox.critical(self, APP_NAME, "Save failed.")

    def save_pdf_as(self) -> None:
        self.save_document_as()

    # ----- edit -----

    def add_text(self, x: Optional[float] = None, y: Optional[float] = None) -> None:
        if not self.engine.is_open:
            QMessageBox.information(self, APP_NAME, "Open a document first.")
            return
        text, ok = QInputDialog.getText(self, APP_NAME, "Text to insert:")
        if not ok or not text:
            return
        kwargs = {}
        if x is not None:
            kwargs["x"] = x
        if y is not None:
            kwargs["y"] = y
        # In book mode, place on left page of spread
        pages = self.engine.spread_pages()
        page = pages[0] if pages else self.engine.current_page
        if self.engine.add_text(text, page=page, **kwargs):
            self._dirty = True
            self.render_current()
            self.statusBar().showMessage("Text added (remember to Save)", 3000)
            self._update_status()
        else:
            QMessageBox.warning(
                self,
                APP_NAME,
                "Could not add text (format may be read-only — try Save As PDF).",
            )

    def add_image(self) -> None:
        if not self.engine.is_open:
            QMessageBox.information(self, APP_NAME, "Open a document first.")
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Insert Image",
            str(Path.home()),
            "Images (*.png *.jpg *.jpeg *.bmp *.webp)",
        )
        if not path:
            return
        if self.engine.add_image(path):
            self._dirty = True
            self.render_current()
            self.statusBar().showMessage("Image added (remember to Save)", 3000)
            self._update_status()
        else:
            QMessageBox.warning(self, APP_NAME, "Could not add image.")

    def _on_canvas_edit(self, pdf_x: float, pdf_y: float) -> None:
        """Edit gesture: double-click (PC) or long-press/hold (mobile)."""
        if not self.engine.is_open:
            return
        # Re-entrancy guard — unified edit_at must never stack dialogs
        if getattr(self, "_edit_dialog_open", False):
            return
        self._edit_dialog_open = True
        try:
            # Book spread: map view coords → page + local point (right half → right page)
            mapped = self.engine.map_view_xy_to_page(float(pdf_x), float(pdf_y))
            if mapped is None:
                return
            page, x, y = mapped
            hint = "hold" if (self._mobile or self._touch) else "double-click"
            text, ok = QInputDialog.getText(
                self,
                APP_NAME,
                f"Add text at ({x:.0f}, {y:.0f}) on page {page + 1}\n({hint} to edit):",
            )
            if not ok or not text:
                return
            if self.engine.add_text(text, page=page, x=x, y=y):
                self._dirty = True
                self.render_current()
                self.statusBar().showMessage("Text added (remember to Save)", 3000)
                self._update_status()
            else:
                QMessageBox.warning(self, APP_NAME, "Could not add text at that position.")
        finally:
            self._edit_dialog_open = False

    def _on_canvas_click(self, pdf_x: float, pdf_y: float) -> None:
        """Deprecated single-click path — edit is double-click / hold only."""
        return

    # ----- navigation -----

    def prev_page(self) -> None:
        if not self.engine.is_open:
            return
        if self.engine.prev_page():
            self._sync_page_controls()
            self.render_current()
            self._update_status()

    def next_page(self) -> None:
        if not self.engine.is_open:
            return
        if self.engine.next_page():
            self._sync_page_controls()
            self.render_current()
            self._update_status()

    def _goto_page(self, index: int) -> None:
        if not self.engine.is_open:
            return
        if self.engine.set_current_page(index):
            self._sync_page_controls()
            self.render_current()
            self._update_status()

    def _on_page_spin(self, value: int) -> None:
        if not self.engine.is_open:
            return
        # Book mode snaps odd pages to the left of the spread — resync spin after set
        if self.engine.set_current_page(value - 1):
            self._sync_page_controls()
            self.render_current()
            self._update_status()

    def _on_nav_page(self, index: int) -> None:
        if not self.engine.is_open:
            return
        if self.engine.set_current_page(index):
            self._sync_page_controls()
            self.render_current()
            self._update_status()

    def _sync_page_controls(self) -> None:
        total = max(1, self.engine.page_count)
        page = self.engine.current_page
        # Book mode: step by spread (2) so Prev/Next don't snap back to the same pair
        step = 2 if self.engine.book_mode else 1
        self.page_spin.blockSignals(True)
        self.page_spin.setMaximum(total)
        self.page_spin.setSingleStep(step)
        # Show left page of spread (engine may have snapped)
        self.page_spin.setValue(page + 1)
        self.page_spin.blockSignals(False)
        self.navigator.set_page_count(total)
        self.navigator.set_step(step)
        self.navigator.set_page(page)

    # ----- zoom / book / theme -----

    def adjust_zoom(self, delta: float) -> None:
        self.set_zoom(self.engine.zoom + delta)

    def set_zoom(self, zoom: float) -> None:
        self.engine.set_zoom(zoom)
        self.render_current()
        self._update_status()

    def reset_zoom(self) -> None:
        """Reset zoom to default (toolbar Reset / Ctrl+0)."""
        # Mobile/APK uses a slightly lower default so spreads fit
        if self._mobile:
            try:
                z = recommended_default_zoom()
            except Exception:  # noqa: BLE001
                z = PDFEngine.ZOOM_DEFAULT
            self.engine.reset_zoom(z)
        else:
            self.engine.reset_zoom()
        self.render_current()
        self._update_status()
        zpct = int(round(self.engine.zoom * 100))
        self.statusBar().showMessage(f"Zoom reset to {zpct}%", 2000)

    def toggle_book_mode(self, checked: Optional[bool] = None) -> None:
        if checked is None:
            enabled = self.engine.toggle_book_mode()
        else:
            enabled = bool(checked)
            self.engine.set_book_mode(enabled)
        self.book_act.blockSignals(True)
        self.book_act.setChecked(enabled)
        self.book_act.blockSignals(False)
        self.book_tb.blockSignals(True)
        self.book_tb.setChecked(enabled)
        self.book_tb.blockSignals(False)
        # When entering book mode, fit the two-page spread into the viewport
        # so both sides are visible without hunting for a scrollbar.
        if enabled and self.engine.is_open:
            self._fit_book_spread_in_view()
        self._sync_page_controls()
        self.render_current()
        self._update_status()
        if enabled:
            spread = self.engine.spread_pages()
            if len(spread) == 2:
                self.statusBar().showMessage(
                    f"Book mode — pages {spread[0] + 1} & {spread[1] + 1} (both sides)",
                    3000,
                )
            else:
                self.statusBar().showMessage("Book mode — both sides when available", 2500)

    def _fit_book_spread_in_view(self) -> None:
        """Shrink zoom so the full left+right spread fits the scroll viewport width."""
        if not self.engine.is_open or not self.engine.book_mode:
            return
        try:
            vp = self.scroll.viewport()
            avail_w = max(200, vp.width() - 24)
            avail_h = max(200, vp.height() - 24)
        except Exception:  # noqa: BLE001
            return
        vw, vh = self.engine.get_view_size()
        if vw <= 1 or vh <= 1:
            return
        # Target zoom so both pages fit; never blow past current zoom upward here
        fit_w = avail_w / vw
        fit_h = avail_h / vh
        target = min(fit_w, fit_h, self.engine.zoom)
        # Keep readable floor
        target = max(PDFEngine.ZOOM_MIN, min(target, PDFEngine.ZOOM_MAX))
        if abs(target - self.engine.zoom) > 0.005:
            self.engine.set_zoom(target)

    def _toggle_theme(self) -> None:
        app = QApplication.instance()
        if app is None:
            return
        self._theme = toggle_theme(self._theme)
        # Keep mobile/APK touch QSS when toggling themes
        apply_theme(app, self._theme, mobile=self._mobile or self._touch)
        self.statusBar().showMessage(f"Theme: {self._theme}", 2000)

    # ----- search -----

    def _show_find(self) -> None:
        self.search_bar.open_and_focus()

    def _on_search(self, query: str) -> None:
        """Run a fresh search. Enter in the find field also fires next_result —
        seed index at 0 here and skip the extra advance once (see _search_next)."""
        self._search_hits = self.engine.search(query)
        n = len(self._search_hits)
        self.search_bar.set_status(f"{n} match" + ("" if n == 1 else "es"))
        if n == 0:
            self._search_index = -1
            self._search_fresh = False
            return
        # Land on first hit immediately; SearchBar also emits next_result on Enter
        self._search_index = 0
        self._search_fresh = True
        self._jump_to_hit()

    def _search_next(self) -> None:
        if not self._search_hits:
            return
        # After a fresh search, Enter already jumped to hit 0 — don't skip to 1
        if getattr(self, "_search_fresh", False):
            self._search_fresh = False
            n = len(self._search_hits)
            self.search_bar.set_status(f"{self._search_index + 1}/{n}")
            return
        self._search_index = (self._search_index + 1) % len(self._search_hits)
        self._jump_to_hit()

    def _search_prev(self) -> None:
        if not self._search_hits:
            return
        self._search_fresh = False
        self._search_index = (self._search_index - 1) % len(self._search_hits)
        self._jump_to_hit()

    def _jump_to_hit(self) -> None:
        page, _rect = self._search_hits[self._search_index]
        self._goto_page(page)
        n = len(self._search_hits)
        self.search_bar.set_status(f"{self._search_index + 1}/{n}")

    def _on_search_closed(self) -> None:
        self.canvas.setFocus(Qt.OtherFocusReason)

    # ----- render / status -----

    def render_current(self) -> None:
        if not self.engine.is_open:
            if self._mobile or self._touch:
                tip = "Hold on a page to add text"
            else:
                tip = "Double-click a page to add text"
            self.canvas.clear_page(f"Open a PDF or EPUB to begin\n\n{tip}")
            return
        # Fast path: RGB24 → QImage (no PNG encode/decode on every paint)
        rgb = None
        try:
            rgb = self.engine.render_view_rgb()
        except Exception:  # noqa: BLE001
            rgb = None
        pix: Optional[QPixmap] = None
        if rgb is not None:
            w, h, data = rgb
            try:
                image = QImage(data, w, h, w * 3, QImage.Format_RGB888)
                if not image.isNull():
                    # Copy pixels — QImage does not own the Python bytes buffer
                    pix = QPixmap.fromImage(image.copy())
            except Exception:  # noqa: BLE001
                pix = None
        if pix is None or pix.isNull():
            data = self.engine.render_view()
            if not data:
                self.canvas.clear_page("Unable to render page")
                return
            image = QImage.fromData(QByteArray(data), "PNG")
            if image.isNull():
                self.canvas.clear_page("Invalid page image")
                return
            pix = QPixmap.fromImage(image)
        vw, vh = self.engine.get_view_size()
        self.canvas.set_page_metrics(vw, vh, self.engine.zoom)
        self.canvas.show_page(pix)
        # Ensure scroll area notices the new (possibly wider) spread size
        try:
            self.scroll.ensureWidgetVisible(self.canvas, 0, 0)
            # Center horizontally on the spine for two-page spreads
            if self.engine.book_mode and len(self.engine.spread_pages()) == 2:
                hbar = self.scroll.horizontalScrollBar()
                vbar = self.scroll.verticalScrollBar()
                if hbar is not None and hbar.maximum() > 0:
                    hbar.setValue(max(0, (hbar.maximum() - hbar.minimum()) // 2))
                if vbar is not None and vbar.maximum() > 0:
                    vbar.setValue(0)
        except Exception:  # noqa: BLE001
            pass
        # Warm adjacent page/spread into LRU for snappier next/prev
        try:
            self._prefetch_neighbors()
        except Exception:  # noqa: BLE001
            pass

    def _prefetch_neighbors(self) -> None:
        """Render next/prev page (or spread) into the engine LRU cache."""
        if not self.engine.is_open:
            return
        eng = self.engine
        cur = eng.current_page
        step = 2 if eng.book_mode else 1
        z = eng.zoom
        for idx in (cur + step, cur - step):
            if 0 <= idx < eng.page_count:
                try:
                    eng.render_view_rgb(page=idx, zoom=z)
                except Exception:  # noqa: BLE001
                    pass

    def _update_status(self) -> None:
        zpct = int(round(self.engine.zoom * 100))
        self.zoom_label.setText(f" {zpct}% ")
        if not self.engine.is_open:
            self.statusBar().showMessage("Ready — Open PDF, EPUB, XPS, CBZ…")
            self.setWindowTitle(f"{APP_NAME} {VERSION}")
            return
        name = Path(self.current_path or "document").name
        page = self.engine.current_page + 1
        total = self.engine.page_count
        fmt = (self.engine.format or "pdf").upper()
        mode = "Book" if self.engine.book_mode else "Single"
        dirty = " •" if self._dirty else ""
        spread = self.engine.spread_pages()
        if len(spread) == 2:
            page_label = f"Pages {spread[0] + 1}–{spread[1] + 1}/{total}"
        else:
            page_label = f"Page {page}/{total}"
        self.setWindowTitle(f"{name}{dirty} — {APP_NAME}")
        self.statusBar().showMessage(
            f"{name}{dirty}  |  {fmt}  |  {page_label}  |  Zoom {zpct}%  |  {mode}"
        )

    def show_about(self) -> None:
        """SecretSticky-style About: logo, hello, links, check for updates."""
        dlg = AboutDialog(self, version=VERSION)
        dlg.exec_()

    def check_for_updates(self, *, quiet_up_to_date: bool = False) -> None:
        """Manual update check (Help menu / About). Network failures are soft."""
        if self._is_headless():
            return
        info = check_for_update(
            owner=GITHUB_OWNER,
            repo=GITHUB_REPO,
            current_version=VERSION,
        )
        msg = format_update_message(info, VERSION)
        if info is None:
            if quiet_up_to_date:
                return
            QMessageBox.information(self, APP_NAME, msg)
            return
        box = QMessageBox(self)
        box.setWindowTitle(f"{APP_NAME} update")
        box.setIcon(QMessageBox.Information)
        box.setText(msg)
        open_btn = box.addButton("Open release", QMessageBox.AcceptRole)
        box.addButton(QMessageBox.Close)
        box.exec_()
        if box.clickedButton() is open_btn:
            url = str(info.get("url") or "")
            if url:
                open_url(url)

    def show_shortcuts(self) -> None:
        QMessageBox.information(
            self,
            "Keyboard Shortcuts",
            "<b>Navigation</b><br>"
            "← / → / PgUp / PgDown / Space — pages (spreads in Book mode)<br>"
            "Home / End — first / last<br><br>"
            "<b>Zoom</b><br>"
            "Ctrl++ / Ctrl+- — 15% steps<br>"
            "Ctrl+Scroll — <b>1% fine zoom</b><br>"
            "Ctrl+Shift++ / Ctrl+Shift+- — 1% fine zoom<br>"
            "Ctrl+0 / toolbar Reset — reset zoom<br><br>"
            "<b>View</b><br>"
            "Ctrl+B — Book mode (both sides)<br>"
            "Ctrl+Shift+T — toggle theme<br>"
            "Ctrl+F — find<br><br>"
            "<b>Edit</b><br>"
            "Double-click page (PC) — add text at point<br>"
            "Hold / long-press (mobile) — add text at point<br>"
            "Ctrl+T — add text<br>"
            "Ctrl+O / Ctrl+S — open / save",
        )

    def _is_headless(self) -> bool:
        """True under offscreen/minimal Qt (unit tests) — skip modal prompts."""
        import os

        plat = os.environ.get("QT_QPA_PLATFORM", "").strip().lower()
        if plat in ("offscreen", "minimal", "null"):
            return True
        app = QApplication.instance()
        if app is not None:
            try:
                name = (app.platformName() or "").lower()
                if name in ("offscreen", "minimal", "null"):
                    return True
            except Exception:  # noqa: BLE001
                pass
        return False

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self._dirty and self.engine.is_open and not self._is_headless():
            reply = QMessageBox.question(
                self,
                APP_NAME,
                "You have unsaved changes.\n\nSave before quitting?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save,
            )
            if reply == QMessageBox.Cancel:
                event.ignore()
                return
            if reply == QMessageBox.Save:
                self.save_document()
                if self._dirty:
                    # Save cancelled or failed — stay open
                    event.ignore()
                    return
        try:
            self.engine.close()
        except Exception:  # noqa: BLE001
            pass
        super().closeEvent(event)


def create_app(argv: Optional[list] = None) -> tuple:
    """Create QApplication + main window (for tests / embedding)."""
    args = list(sys.argv if argv is None else argv)
    qapp = QApplication.instance() or QApplication(args)
    qapp.setApplicationName(APP_NAME)
    qapp.setApplicationVersion(VERSION)
    qapp.setOrganizationName("AhmiDarrow")
    qapp.setOrganizationDomain("github.com/AhmiDarrow")
    apply_app_icon(qapp)
    # Theme before window so widgets pick up palette (mobile extras auto)
    mobile = False
    try:
        mobile = is_mobile() or is_touch_primary()
    except Exception:  # noqa: BLE001
        mobile = False
    apply_theme(qapp, DEFAULT_THEME, mobile=mobile)
    try:
        apply_mobile_attribute(qapp)
    except Exception:  # noqa: BLE001
        pass
    window = RemedyPDFApp()
    return qapp, window


def run(argv: Optional[list] = None) -> int:
    """Launch the GUI event loop."""
    qapp, window = create_app(argv)
    args = list(sys.argv if argv is None else argv)
    # Open first supported path argument
    for arg in args[1:]:
        if arg.startswith("-"):
            continue
        lower = arg.lower()
        if any(lower.endswith(ext) for ext in SUPPORTED_EXTENSIONS):
            window.open_document(arg)
            break
    window.show()
    return qapp.exec_()
