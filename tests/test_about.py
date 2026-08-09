import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt5")


def test_about_dialog_builds():
    from PyQt5.QtWidgets import QApplication

    from ui.about import AboutDialog

    app = QApplication.instance() or QApplication([])
    dlg = AboutDialog(None, version="1.2.0")
    assert "About" in dlg.windowTitle()
    assert dlg._version == "1.2.0"
    # brand mark may or may not load pixmap; dialog must still construct
    dlg.close()
    app.processEvents()


def test_open_external_url_rejects_non_http():
    from ui.about import open_external_url

    assert open_external_url("file:///etc/passwd") is False
    assert open_external_url("javascript:alert(1)") is False
