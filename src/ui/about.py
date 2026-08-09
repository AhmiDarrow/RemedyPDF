"""About dialog — modeled after SecretSticky/SecretFolder About panel."""

from __future__ import annotations

import webbrowser
from typing import Optional

from PyQt5.QtCore import Qt, QThread, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices, QPixmap
from PyQt5.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

try:
    from src import (
        GITHUB_OWNER,
        GITHUB_PROFILE,
        GITHUB_RELEASES_URL,
        GITHUB_REPO,
        GITHUB_REPO_URL,
        PATREON_URL,
        __app_name__,
        __author__,
        __version__,
    )
except ImportError:
    try:
        from __init__ import (  # type: ignore
            GITHUB_OWNER,
            GITHUB_PROFILE,
            GITHUB_RELEASES_URL,
            GITHUB_REPO,
            GITHUB_REPO_URL,
            PATREON_URL,
            __app_name__,
            __author__,
            __version__,
        )
    except ImportError:
        GITHUB_OWNER = "AhmiDarrow"
        GITHUB_REPO = "RemedyPDF"
        GITHUB_PROFILE = "https://github.com/AhmiDarrow"
        GITHUB_REPO_URL = "https://github.com/AhmiDarrow/RemedyPDF"
        GITHUB_RELEASES_URL = "https://github.com/AhmiDarrow/RemedyPDF/releases"
        PATREON_URL = "https://www.patreon.com/cw/AhmiDarrow"
        __app_name__ = "RemedyPDF"
        __author__ = "Ahmi Darrow"
        __version__ = "1.3.5"

try:
    from utils.brand import about_mark_path
    from utils.updater import check_for_update, update_status_message
except ImportError:  # package-style
    from src.utils.brand import about_mark_path  # type: ignore
    from src.utils.updater import check_for_update, update_status_message  # type: ignore


def open_external_url(url: str) -> bool:
    """Open https URL in the system browser (allowlisted schemes only)."""
    u = (url or "").strip()
    if not (u.startswith("https://") or u.startswith("http://")):
        return False
    try:
        if QDesktopServices.openUrl(QUrl(u)):
            return True
    except Exception:  # noqa: BLE001
        pass
    try:
        return bool(webbrowser.open(u))
    except Exception:  # noqa: BLE001
        return False


class _UpdateCheckWorker(QThread):
    finished_ok = pyqtSignal(object)  # Optional[dict]
    failed = pyqtSignal(str)

    def __init__(self, current_version: str, parent=None) -> None:
        super().__init__(parent)
        self._version = current_version

    def run(self) -> None:  # noqa: D401
        try:
            info = check_for_update(
                owner=GITHUB_OWNER,
                repo=GITHUB_REPO,
                current_version=self._version,
            )
            self.finished_ok.emit(info)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class AboutDialog(QDialog):
    """About panel: hello, version, brand mark, links, check-for-updates."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        version: Optional[str] = None,
    ) -> None:
        super().__init__(parent)
        self._version = version or __version__
        self.setWindowTitle(f"About {__app_name__}")
        self.setModal(True)
        self.setMinimumWidth(440)
        self._worker: Optional[_UpdateCheckWorker] = None
        self._pending: Optional[dict] = None
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(12)

        row = QHBoxLayout()
        row.setSpacing(14)

        mark = QLabel()
        mark.setObjectName("aboutMark")
        path = about_mark_path()
        if path is not None:
            pix = QPixmap(str(path))
            if not pix.isNull():
                mark.setPixmap(
                    pix.scaled(72, 72, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
        mark.setFixedSize(80, 80)
        mark.setAlignment(Qt.AlignCenter)
        row.addWidget(mark, 0, Qt.AlignTop)

        body = QVBoxLayout()
        body.setSpacing(6)

        title = QLabel(f"<h2 style='margin:0'>About {__app_name__}</h2>")
        body.addWidget(title)

        hello = QLabel("Hi I'm Ahmi, hope this helps!")
        hello.setObjectName("aboutHello")
        hello.setWordWrap(True)
        body.addWidget(hello)

        blurb = QLabel(
            "Fast multi-format document viewer and editor — PDF, EPUB, XPS, CBZ, and more. "
            "Remedy themes, both-sides book mode, fine zoom, mobile/APK polish. MIT licensed."
        )
        blurb.setWordWrap(True)
        blurb.setObjectName("aboutBlurb")
        body.addWidget(blurb)

        ver = QLabel(f"Version {self._version}")
        ver.setObjectName("aboutVersion")
        body.addWidget(ver)

        # Platform / channel tags (SecretSticky-style meta chips)
        tags_row = QHBoxLayout()
        tags_row.setSpacing(6)
        for chip in (
            "Windows installer",
            "Android APK",
            "PDF · EPUB",
            "Fit · Fullscreen",
            "HC · Sepia · Night",
            "Auto-update",
            "MIT",
        ):
            tag = QLabel(chip)
            tag.setObjectName("aboutTag")
            tag.setStyleSheet(
                "QLabel#aboutTag {"
                "  padding: 2px 8px;"
                "  border-radius: 8px;"
                "  border: 1px solid rgba(128,128,128,0.45);"
                "  font-size: 11px;"
                "}"
            )
            tags_row.addWidget(tag)
        tags_row.addStretch(1)
        body.addLayout(tags_row)

        author = QLabel(f"by {__author__}")
        author.setObjectName("aboutAuthor")
        body.addWidget(author)

        links = QHBoxLayout()
        links.setSpacing(8)
        self._add_link_btn(links, "GitHub profile", GITHUB_PROFILE, primary=True)
        self._add_link_btn(links, "Project repo", GITHUB_REPO_URL)
        self._add_link_btn(links, "Releases", GITHUB_RELEASES_URL)
        body.addLayout(links)

        patreon_row = QHBoxLayout()
        self._add_link_btn(patreon_row, "Patreon", PATREON_URL)
        body.addLayout(patreon_row)

        upd_row = QHBoxLayout()
        self.check_btn = QPushButton("Check for updates")
        self.check_btn.clicked.connect(self._on_check_updates)
        upd_row.addWidget(self.check_btn)
        self.open_release_btn = QPushButton("Get update")
        self.open_release_btn.setEnabled(False)
        self.open_release_btn.clicked.connect(self._on_open_release)
        upd_row.addWidget(self.open_release_btn)
        upd_row.addStretch(1)
        body.addLayout(upd_row)

        self.status = QLabel("")
        self.status.setObjectName("aboutUpdateStatus")
        self.status.setWordWrap(True)
        body.addWidget(self.status)

        row.addLayout(body, 1)
        root.addLayout(row)

        footer = QHBoxLayout()
        meta = QLabel(
            "Local app · Windows Setup + Android APK · GitHub Releases auto-update"
        )
        meta.setObjectName("aboutFooterMeta")
        footer.addWidget(meta)
        footer.addStretch(1)
        close_btn = QPushButton("Close")
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)
        footer.addWidget(close_btn)
        root.addLayout(footer)

    def _add_link_btn(
        self, layout: QHBoxLayout, label: str, url: str, primary: bool = False
    ) -> QPushButton:
        btn = QPushButton(label)
        if primary:
            btn.setObjectName("aboutPrimaryLink")
        btn.clicked.connect(lambda _=False, u=url: open_external_url(u))
        layout.addWidget(btn)
        return btn

    def _on_check_updates(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        self.check_btn.setEnabled(False)
        self.check_btn.setText("Checking…")
        self.status.setText("Checking GitHub Releases…")
        self.open_release_btn.setEnabled(False)
        self._pending = None
        self._worker = _UpdateCheckWorker(self._version, self)
        self._worker.finished_ok.connect(self._on_update_result)
        self._worker.failed.connect(self._on_update_failed)
        self._worker.start()

    def _on_update_result(self, info: object) -> None:
        self.check_btn.setEnabled(True)
        self.check_btn.setText("Check for updates")
        data = info if isinstance(info, dict) else None
        self._pending = data
        msg = update_status_message(data, self._version)
        self.status.setText(msg)
        if data and data.get("url"):
            self.open_release_btn.setEnabled(True)
            self.open_release_btn.setText(f"Get v{data.get('tag', '')}")
        else:
            self.open_release_btn.setEnabled(False)
            self.open_release_btn.setText("Get update")

    def _on_update_failed(self, err: str) -> None:
        self.check_btn.setEnabled(True)
        self.check_btn.setText("Check for updates")
        self.status.setText(f"Update check failed: {err}")

    def _on_open_release(self) -> None:
        url = ""
        if self._pending:
            url = str(self._pending.get("url") or "")
        if not url:
            url = GITHUB_RELEASES_URL
        open_external_url(url)


def show_about(parent: Optional[QWidget] = None, version: Optional[str] = None) -> None:
    """Show the About dialog (preferred). Falls back to QMessageBox if needed."""
    try:
        dlg = AboutDialog(parent, version=version)
        dlg.exec_()
    except Exception:  # noqa: BLE001
        QMessageBox.about(
            parent,
            f"About {__app_name__}",
            f"<b>{__app_name__}</b> {version or __version__}<br>"
            "Hi I'm Ahmi, hope this helps!<br><br>"
            f'<a href="{GITHUB_PROFILE}">GitHub profile</a> · '
            f'<a href="{GITHUB_REPO_URL}">Repo</a> · '
            f'<a href="{GITHUB_RELEASES_URL}">Releases</a>',
        )
