"""Reusable UI widgets — Remedy forms style + navigation + canvas."""

from __future__ import annotations

from typing import Optional, Tuple

from PyQt5.QtCore import QPoint, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QKeySequence, QMouseEvent, QPixmap
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QShortcut,
    QSpinBox,
    QWidget,
)


# Long-press threshold for mobile hold-to-edit (ms)
LONG_PRESS_MS = 450
# Touch target minimum (px) — Material / iOS HIG-ish
TOUCH_MIN_PX = 44


class PageNavigator(QWidget):
    """Prev / page spin / next control strip (touch-friendly)."""

    page_changed = pyqtSignal(int)  # 0-based page index

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("pageNavigator")
        self._step = 1
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(10)

        self.prev_btn = QPushButton("◀ Prev")
        self.prev_btn.setToolTip("Previous page (← or PgUp)")
        self.prev_btn.setMinimumHeight(TOUCH_MIN_PX)
        self.next_btn = QPushButton("Next ▶")
        self.next_btn.setToolTip("Next page (→ or PgDown)")
        self.next_btn.setMinimumHeight(TOUCH_MIN_PX)
        self.next_btn.setObjectName("primaryButton")
        self.page_spin = QSpinBox()
        self.page_spin.setMinimum(1)
        self.page_spin.setMaximum(1)
        self.page_spin.setToolTip("Go to page")
        self.page_spin.setMinimumWidth(72)
        self.page_spin.setMinimumHeight(TOUCH_MIN_PX)
        self.label = QLabel("Page")
        self.label.setObjectName("mutedLabel")
        self.count_label = QLabel("/ 1")
        self.count_label.setObjectName("mutedLabel")

        layout.addWidget(self.prev_btn)
        layout.addWidget(self.label)
        layout.addWidget(self.page_spin)
        layout.addWidget(self.count_label)
        layout.addWidget(self.next_btn)

        self.prev_btn.clicked.connect(self._prev)
        self.next_btn.clicked.connect(self._next)
        self.page_spin.valueChanged.connect(self._spin)

    def set_page_count(self, count: int) -> None:
        total = max(1, count)
        self.page_spin.blockSignals(True)
        self.page_spin.setMaximum(total)
        self.page_spin.blockSignals(False)
        self.count_label.setText(f"/ {total}")
        self.prev_btn.setEnabled(total > 1)
        self.next_btn.setEnabled(total > 1)

    def set_step(self, step: int) -> None:
        """Page step for Prev/Next (1 single, 2 book-mode spread)."""
        self._step = max(1, int(step))
        self.page_spin.setSingleStep(self._step)

    def set_page(self, index_zero_based: int) -> None:
        self.page_spin.blockSignals(True)
        self.page_spin.setValue(index_zero_based + 1)
        self.page_spin.blockSignals(False)

    def _prev(self) -> None:
        step = getattr(self, "_step", 1) or 1
        value = max(1, self.page_spin.value() - step)
        self.page_spin.setValue(value)

    def _next(self) -> None:
        step = getattr(self, "_step", 1) or 1
        value = min(self.page_spin.maximum(), self.page_spin.value() + step)
        self.page_spin.setValue(value)

    def _spin(self, value: int) -> None:
        self.page_changed.emit(value - 1)


class SearchBar(QWidget):
    """Inline find bar — Ctrl+F style."""

    search_requested = pyqtSignal(str)
    closed = pyqtSignal()
    next_result = pyqtSignal()
    prev_result = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("searchBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        self.field = QLineEdit()
        self.field.setObjectName("searchField")
        self.field.setPlaceholderText("Find in document…")
        self.field.setClearButtonEnabled(True)
        self.field.setMinimumHeight(TOUCH_MIN_PX - 4)
        self.field.returnPressed.connect(self._emit_search)

        self.prev_btn = QPushButton("↑")
        self.prev_btn.setToolTip("Previous match (Shift+Enter)")
        self.prev_btn.setFixedWidth(TOUCH_MIN_PX)
        self.prev_btn.setMinimumHeight(TOUCH_MIN_PX)
        self.next_btn = QPushButton("↓")
        self.next_btn.setToolTip("Next match (Enter)")
        self.next_btn.setFixedWidth(TOUCH_MIN_PX)
        self.next_btn.setMinimumHeight(TOUCH_MIN_PX)
        self.next_btn.setObjectName("primaryButton")

        self.status = QLabel("")
        self.status.setObjectName("mutedLabel")

        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedWidth(TOUCH_MIN_PX)
        self.close_btn.setMinimumHeight(TOUCH_MIN_PX)
        self.close_btn.setToolTip("Close (Esc)")
        self.close_btn.clicked.connect(self._close)

        layout.addWidget(QLabel("Find"))
        layout.addWidget(self.field, 1)
        layout.addWidget(self.prev_btn)
        layout.addWidget(self.next_btn)
        layout.addWidget(self.status)
        layout.addWidget(self.close_btn)

        self.prev_btn.clicked.connect(self.prev_result.emit)
        self.next_btn.clicked.connect(self.next_result.emit)

        QShortcut(QKeySequence(Qt.Key_Escape), self, activated=self._close)
        QShortcut(QKeySequence("Shift+Return"), self.field, activated=self.prev_result.emit)

    def _emit_search(self) -> None:
        text = self.field.text().strip()
        if text:
            self.search_requested.emit(text)
            self.next_result.emit()

    def _close(self) -> None:
        self.hide()
        self.closed.emit()

    def open_and_focus(self) -> None:
        self.show()
        self.field.setFocus(Qt.ShortcutFocusReason)
        self.field.selectAll()

    def set_status(self, text: str) -> None:
        self.status.setText(text)


class PDFCanvas(QLabel):
    """Rendered PDF page canvas.

    Edit gestures:
      • Desktop: **double-click** to edit (single click does not edit)
      • Mobile / touch: **long-press (hold)** to edit
    Emits coordinates in PDF point space (spread-aware via parent).
    """

    clicked_at = pyqtSignal(float, float)  # kept for API; not used for edit
    double_clicked_at = pyqtSignal(float, float)  # PC edit
    long_pressed_at = pyqtSignal(float, float)  # mobile hold-to-edit
    edit_at = pyqtSignal(float, float)  # unified edit signal

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("pdfCanvas")
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(280, 360)
        self.setText(
            "Open a PDF or EPUB to begin\n\n"
            "Double-click (PC) or hold (mobile) to add text"
        )
        self.setCursor(Qt.ArrowCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAttribute(Qt.WA_AcceptTouchEvents, True)
        self._zoom: float = 1.0
        self._page_size: Tuple[float, float] = (0.0, 0.0)  # PDF points
        self._pixmap_size: Tuple[int, int] = (0, 0)
        self._edit_enabled: bool = True
        # Touch mode: long-press edit; desktop: double-click (no long-press dialog)
        self._touch_mode: bool = False

        # Long-press state
        self._press_pos: Optional[QPoint] = None
        self._long_timer = QTimer(self)
        self._long_timer.setSingleShot(True)
        self._long_timer.timeout.connect(self._fire_long_press)
        self._long_fired = False

    def set_touch_mode(self, enabled: bool) -> None:
        """When True, hold-to-edit is active; when False, only double-click edits."""
        self._touch_mode = bool(enabled)

    def set_edit_enabled(self, enabled: bool) -> None:
        self._edit_enabled = enabled
        self.setCursor(Qt.IBeamCursor if enabled else Qt.ArrowCursor)

    def set_page_metrics(self, width_pts: float, height_pts: float, zoom: float) -> None:
        self._page_size = (float(width_pts), float(height_pts))
        self._zoom = max(0.01, float(zoom))

    def show_page(self, pixmap: QPixmap) -> None:
        """Show a rendered page or full book-spread pixmap.

        Widget is sized to the pixmap so a two-page spread can exceed the
        viewport and scroll horizontally — both sides stay visible.
        """
        if pixmap is None or pixmap.isNull():
            self.clear_page("Unable to render page")
            return
        self.setText("")  # clear placeholder so pixmap paints fully
        self._pixmap_size = (pixmap.width(), pixmap.height())
        # Never scale-to-fit the label itself — that collapses book spreads
        self.setScaledContents(False)
        self.setPixmap(pixmap)
        # Critical: with QScrollArea(widgetResizable=False) the label must
        # report the full spread size or only one page appears clipped.
        size = pixmap.size()
        self.setMinimumSize(size)
        self.setMaximumSize(size)
        self.resize(size)
        self.updateGeometry()

    def clear_page(self, message: str = "Open a PDF to begin") -> None:
        self._pixmap_size = (0, 0)
        self._page_size = (0.0, 0.0)
        self.setPixmap(QPixmap())
        # Release fixed spread size so empty state can fill the scroll area
        self.setMinimumSize(280, 360)
        self.setMaximumSize(16777215, 16777215)
        self.setText(message)

    def _map_widget_to_pdf(self, pos: QPoint) -> Optional[Tuple[float, float]]:
        """Map a widget click to PDF point coordinates, or None if outside page."""
        pm = self.pixmap()
        if pm is None or pm.isNull() or self._zoom <= 0:
            return None

        pm_w, pm_h = pm.width(), pm.height()
        # Prefer stored pixmap size (set in show_page) — more reliable after resize
        if self._pixmap_size[0] > 0 and self._pixmap_size[1] > 0:
            pm_w, pm_h = self._pixmap_size

        # QLabel centers pixmap when larger than contents; compute offset
        x_off = max(0, (self.width() - pm_w) // 2)
        y_off = max(0, (self.height() - pm_h) // 2)

        lx = pos.x() - x_off
        ly = pos.y() - y_off
        if lx < 0 or ly < 0 or lx >= pm_w or ly >= pm_h:
            return None

        pdf_x = lx / self._zoom
        pdf_y = ly / self._zoom
        return (pdf_x, pdf_y)

    def _emit_edit(self, pos: QPoint) -> None:
        mapped = self._map_widget_to_pdf(pos)
        if mapped is None:
            return
        self.edit_at.emit(mapped[0], mapped[1])

    def _fire_long_press(self) -> None:
        if not self._edit_enabled or not self._touch_mode or self._press_pos is None:
            return
        self._long_fired = True
        mapped = self._map_widget_to_pdf(self._press_pos)
        if mapped is not None:
            # Emit only edit_at (unified). long_pressed_at is informational for tests/API.
            self.long_pressed_at.emit(mapped[0], mapped[1])
            self.edit_at.emit(mapped[0], mapped[1])

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._edit_enabled and event.button() == Qt.LeftButton:
            self._press_pos = event.pos()
            self._long_fired = False
            # Long-press only on touch/mobile — desktop uses double-click
            if self._touch_mode:
                self._long_timer.start(LONG_PRESS_MS)
            else:
                self._long_timer.stop()
            # Single click no longer opens edit — only notify clicked_at for optional use
            mapped = self._map_widget_to_pdf(event.pos())
            if mapped is not None:
                self.clicked_at.emit(mapped[0], mapped[1])
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        # Cancel long-press if finger/mouse drifts
        if self._press_pos is not None and self._long_timer.isActive():
            dx = abs(event.pos().x() - self._press_pos.x())
            dy = abs(event.pos().y() - self._press_pos.y())
            if dx > 12 or dy > 12:
                self._long_timer.stop()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._long_timer.stop()
        self._press_pos = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Desktop: double-click to edit (suppressed on pure touch mode)."""
        self._long_timer.stop()
        if self._edit_enabled and event.button() == Qt.LeftButton and not self._touch_mode:
            mapped = self._map_widget_to_pdf(event.pos())
            if mapped is not None:
                # Emit only edit_at (unified). double_clicked_at is informational.
                self.double_clicked_at.emit(mapped[0], mapped[1])
                self.edit_at.emit(mapped[0], mapped[1])
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def event(self, event) -> bool:  # noqa: N802
        # Accept touch so long-press works on mobile / touch laptops
        try:
            from PyQt5.QtCore import QEvent

            et = event.type()
            if et == QEvent.TouchBegin and self._touch_mode:
                self.setAttribute(Qt.WA_AcceptTouchEvents, True)
                points = event.touchPoints() if hasattr(event, "touchPoints") else []
                if points:
                    self._press_pos = points[0].pos().toPoint()
                    self._long_fired = False
                    if self._edit_enabled:
                        self._long_timer.start(LONG_PRESS_MS)
                return True
            if et == QEvent.TouchEnd and self._touch_mode:
                self._long_timer.stop()
                self._press_pos = None
                return True
            if et == QEvent.TouchUpdate and self._touch_mode and self._press_pos is not None:
                points = event.touchPoints() if hasattr(event, "touchPoints") else []
                if points:
                    p = points[0].pos().toPoint()
                    if abs(p.x() - self._press_pos.x()) > 12 or abs(p.y() - self._press_pos.y()) > 12:
                        self._long_timer.stop()
                return True
        except Exception:  # noqa: BLE001
            pass
        return super().event(event)
