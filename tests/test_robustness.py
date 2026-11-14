"""Encrypted / damaged / empty documents, safe re-open, save fallbacks, update URL pinning."""

from __future__ import annotations

import os
from pathlib import Path

import pymupdf as fitz
import pytest

from core.pdf_engine import PDFEngine
from utils.updater import find_installer_url, is_trusted_installer_url


def _make_pdf(path: Path, text: str = "Hello", pages: int = 1, **save_kwargs) -> Path:
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page(width=300, height=400)
        page.insert_text((72, 72), f"{text} {i + 1}", fontsize=14)
    doc.save(path, **save_kwargs)
    doc.close()
    return path


@pytest.fixture()
def encrypted_pdf(tmp_path: Path) -> Path:
    return _make_pdf(
        tmp_path / "locked.pdf",
        text="Secret",
        encryption=fitz.PDF_ENCRYPT_AES_256,
        user_pw="pw123",
        owner_pw="owner456",
    )


# ----- open -----


def test_encrypted_pdf_requires_password(encrypted_pdf: Path):
    eng = PDFEngine()
    assert eng.open(str(encrypted_pdf)) is False
    assert eng.last_error == "password"
    assert not eng.is_open
    assert eng.open(str(encrypted_pdf), password="wrong") is False
    assert eng.last_error == "password"


def test_encrypted_pdf_opens_and_renders_with_password(encrypted_pdf: Path):
    eng = PDFEngine()
    assert eng.open(str(encrypted_pdf), password="pw123") is True
    assert eng.last_error == ""
    assert eng.is_password_protected
    assert eng.render_view_rgb() is not None
    assert eng.get_view_size()[0] > 0


@pytest.mark.parametrize(
    "name,payload",
    [("empty.pdf", b""), ("junk.pdf", b"definitely not a pdf " * 20)],
)
def test_failed_open_keeps_current_document(tmp_path: Path, name: str, payload: bytes):
    good = _make_pdf(tmp_path / "good.pdf", pages=3)
    bad = tmp_path / name
    bad.write_bytes(payload)
    eng = PDFEngine()
    assert eng.open(str(good))
    eng.set_current_page(2)
    assert eng.open(str(bad)) is False
    assert eng.last_error == "error"
    # The document the user was reading is still there, on the same page.
    assert eng.is_open
    assert eng.path == str(good)
    assert eng.page_count == 3
    assert eng.current_page == 2
    assert eng.render_view_rgb() is not None


def test_wrong_password_keeps_current_document(tmp_path: Path, encrypted_pdf: Path):
    good = _make_pdf(tmp_path / "good.pdf")
    eng = PDFEngine()
    assert eng.open(str(good))
    assert eng.open(str(encrypted_pdf), password="nope") is False
    assert eng.path == str(good)
    assert eng.is_open


def test_page_size_survives_broken_page_access(tmp_path: Path, monkeypatch):
    eng = PDFEngine()
    assert eng.open(str(_make_pdf(tmp_path / "a.pdf")))

    class Boom:
        def __getitem__(self, _i):
            raise RuntimeError("damaged page tree")

        def close(self):
            pass

    real = eng.doc
    monkeypatch.setattr(eng, "doc", Boom())
    assert eng.get_page_size(0) == (0.0, 0.0)
    assert eng.get_view_size() == (0.0, 0.0)
    eng.doc = real


# ----- save -----


def test_save_keeps_password_protection(tmp_path: Path, encrypted_pdf: Path):
    eng = PDFEngine()
    assert eng.open(str(encrypted_pdf), password="pw123")
    assert eng.add_text("Added later", x=72, y=150)
    out = tmp_path / "copy.pdf"
    assert eng.save(str(out))
    check = fitz.open(str(out))
    try:
        assert check.needs_pass
        assert check.authenticate("pw123")
        text = check[0].get_text()
        assert "Secret" in text and "Added later" in text
    finally:
        check.close()


def test_save_in_place_encrypted_stays_open_and_protected(encrypted_pdf: Path):
    eng = PDFEngine()
    assert eng.open(str(encrypted_pdf), password="pw123")
    assert eng.add_text("In place", x=72, y=150)
    assert eng.save()
    assert eng.is_open
    assert eng.render_view_rgb() is not None
    check = fitz.open(str(encrypted_pdf))
    try:
        assert check.needs_pass
        assert check.authenticate("pw123")
        assert "In place" in check[0].get_text()
    finally:
        check.close()


def test_unencrypted_save_stays_unencrypted(tmp_path: Path):
    eng = PDFEngine()
    assert eng.open(str(_make_pdf(tmp_path / "plain.pdf")))
    out = tmp_path / "plain-out.pdf"
    assert eng.save(str(out))
    check = fitz.open(str(out))
    try:
        assert not check.needs_pass
    finally:
        check.close()


def test_save_in_place_swap_failure_keeps_edits(tmp_path: Path, monkeypatch):
    """A locked destination must report failure, not lose edits or fake success."""
    src = _make_pdf(tmp_path / "doc.pdf")
    eng = PDFEngine()
    assert eng.open(str(src))
    assert eng.add_text("Unsaved edit", x=72, y=150)

    def locked(*_a, **_k):
        raise PermissionError("file is in use")

    monkeypatch.setattr("core.pdf_engine.os.replace", locked)
    assert eng.save() is False
    assert eng.is_open
    assert "Unsaved edit" in eng.doc[0].get_text()
    # No stray temp sibling or misleading "-export.pdf" left behind.
    leftovers = sorted(p.name for p in tmp_path.iterdir())
    assert leftovers == ["doc.pdf"]
    # Once the lock is gone, saving in place works and keeps the edit.
    monkeypatch.undo()
    assert eng.save() is True
    check = fitz.open(str(src))
    try:
        assert "Unsaved edit" in check[0].get_text()
    finally:
        check.close()


def test_non_pdf_repeat_save_overwrites_same_export(tmp_path: Path):
    """Saving an image-based document twice writes the same .pdf, not -export copies."""
    from PIL import Image

    png = tmp_path / "scan.png"
    Image.new("RGB", (120, 80), (200, 30, 30)).save(png)
    eng = PDFEngine()
    assert eng.open(str(png))
    out = tmp_path / "scan.pdf"
    assert eng.save(str(out))
    assert eng.path == str(out)
    assert eng.save()  # Ctrl+S again
    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == ["scan.pdf", "scan.png"]


# ----- updater URL pinning -----


@pytest.mark.parametrize(
    "url,ok",
    [
        ("https://github.com/AhmiDarrow/RemedyPDF/releases/download/v1.4.6/RemedyPDF-1.4.6-windows-setup.exe", True),
        ("https://github.com/ahmidarrow/remedypdf/releases/download/v1.4.6/Setup.EXE", True),
        ("http://github.com/AhmiDarrow/RemedyPDF/releases/download/v1.4.6/setup.exe", False),
        ("https://evil.example/AhmiDarrow/RemedyPDF/releases/download/v1/setup.exe", False),
        ("https://github.com.evil.example/AhmiDarrow/RemedyPDF/releases/download/v1/setup.exe", False),
        ("https://github.com/someone-else/RemedyPDF/releases/download/v1/setup.exe", False),
        ("https://github.com/AhmiDarrow/RemedyPDF/releases/download/../../x/setup.exe", False),
        ("https://user:pw@github.com/AhmiDarrow/RemedyPDF/releases/download/v1/setup.exe", False),
        ("https://github.com/AhmiDarrow/RemedyPDF/releases/download/v1/notes.zip", False),
        ("", False),
    ],
)
def test_is_trusted_installer_url(url: str, ok: bool):
    assert is_trusted_installer_url(url) is ok


def test_find_installer_url_ignores_foreign_hosts():
    info = {
        "platforms": {"windows-x86_64": {"url": "https://evil.example/setup.exe"}},
        "assets": [
            {"name": "RemedyPDF-setup.exe", "browser_download_url": "https://evil.example/s.exe"},
        ],
        "url": "https://evil.example/other.exe",
    }
    assert find_installer_url(info) is None
    good = "https://github.com/AhmiDarrow/RemedyPDF/releases/download/v2.0.0/RemedyPDF-2.0.0-windows-setup.exe"
    info["assets"].append({"name": "RemedyPDF-2.0.0-windows-setup.exe", "browser_download_url": good})
    assert find_installer_url(info) == good


# ----- desktop UI: failed open does not desync the window -----


def test_app_failed_open_keeps_document(tmp_path: Path, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt5.QtWidgets import QMessageBox

    from core.app import create_app

    shown = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: shown.append(a))
    _qapp, win = create_app(["remedy-pdf"])
    try:
        good = _make_pdf(tmp_path / "good.pdf", pages=2)
        bad = tmp_path / "bad.pdf"
        bad.write_bytes(b"\x00garbage" * 50)
        win.open_document(str(good))
        assert win.current_path == str(good)
        win.open_document(str(bad))
        assert shown, "user should be told the open failed"
        assert win.current_path == str(good)
        assert win.engine.is_open and win.engine.path == str(good)
    finally:
        win.close()
