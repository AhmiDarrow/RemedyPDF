# RemedyPDF 1.4.6

Opening and saving are more careful with passwords, damaged files, and locked files. Updates install only from this repository, and the Windows build stays on PyMuPDF 1.x so PyInstaller can package it.

Hi I'm Ahmi, hope this helps!

## Fixes

- **Password-protected PDFs ask for the password** (up to three tries). A missing or wrong password no longer leaves open a document that fails on every redraw. On Android, the app says password-protected PDFs are not supported there yet.
- **Saving keeps the password.** A PDF unlocked with a password is written back with that same password using AES-256. Version 1.4.5 saved that file with no password. MuPDF's keep-encryption option is not used, because it can corrupt newly written content.
- **A failed open leaves the current document where it was.** Opening a damaged, empty, unsupported, or locked file keeps the document you already have open, on the same page, and the message says why the new file did not open.
- **Save reports a locked file.** If another program holds the PDF open, Save keeps your unsaved edits and reports the failure. It no longer writes a separate `-export.pdf` without those edits and reports success.
- **Saving an EPUB, XPS, or image again writes the same PDF.** Later saves overwrite that export. They do not add another `-export.pdf` each time. The window title follows the file that was written.
- **A page that cannot be read does not crash the viewer.**
- **The Android fallback renderer draws pages.** When PyMuPDF is unavailable, the native renderer produces a page, keeps red and blue in the right channels, and is faster. Arrow keys turn a single page when the main screen is opened again.
- **Update installers only come from this repository.** An installer URL is accepted only when it is `https://github.com/AhmiDarrow/RemedyPDF/releases/download/…` and ends in `.exe`. The updater starts that installer directly, without a command shell.

## Build/packaging

- **Windows packages stay on PyMuPDF 1.x** (`PyMuPDF>=1.24.3,<2`). PyMuPDF 2.x installs onnxruntime, and PyInstaller 6.22 crashes while importing onnxruntime on Windows (exit 3221225477). RemedyPDF does not use layout analysis. 1.4.5 shipped PyMuPDF 1.28.x. The Windows build also excludes `onnxruntime`, `pymupdf.layout`, `pymupdf4llm`, and `PyQt5.uic.port_v2`.
- Builds require Pillow 10.3.0 or newer, and PyMuPDF 1.24.3 or newer.
- The app imports PyMuPDF as `pymupdf`, and still accepts older builds that only provide the `fitz` name.
- `scripts/bump_version.py` keeps the version in the app, the Inno Setup script, the Android spec, and the docs on the same number. This release is 1.4.6.

## Install and update

- Windows setup: `RemedyPDF-1.4.6-windows-setup.exe` (per-user install, Start Menu, and an optional desktop shortcut).
- Portable: `RemedyPDF-1.4.6-windows.exe`, also attached as `RemedyPDF.exe`.
- Android: `RemedyPDF-1.4.6-android-src.zip` is the mobile source package. This release does not include an APK.
- Already installed: **Help → About → Check for updates**. Documents you open are not part of the app update.
