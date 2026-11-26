# RemedyPDF

**A fast, multi-format document viewer and editor for Windows, Linux and Android.**

Read PDFs, e-books, comics, Office documents and images in one place, and add text and pictures to your PDFs.

[![Latest release](https://img.shields.io/github/v/release/AhmiDarrow/RemedyPDF)](https://github.com/AhmiDarrow/RemedyPDF/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20Android-0078D6)](https://github.com/AhmiDarrow/RemedyPDF/releases/latest)
[![Built with RemedyUI](https://img.shields.io/badge/built%20with-RemedyUI-8A2BE2)](#built-with-remedyui)

<p align="center">
  <img src="resources/icon.png" alt="RemedyPDF icon" width="96" height="96" />
</p>

<p align="center">
  <strong>Book mode · Reader mode · Nine themes · Signed auto-update</strong>
</p>

<p align="center">
  <strong>Built with <a href="#built-with-remedyui">RemedyUI</a></strong>: a native Rust app on every platform.
</p>

---

## Why

Most of us keep several programs around just to open documents: one for PDFs, another for e-books, another for comics. **RemedyPDF** opens them all, reads comfortably, and makes the small PDF edits without getting in the way.

## Built with RemedyUI

Since 2.0, RemedyPDF runs on **RemedyUI**, Ahmi Darrow's own Rust UI engine. The window, the page view, text rendering, accessibility and the signed updater come from RemedyUI:

- **Native, with no Python.** The 1.x releases were a Python app; 2.0 replaced all of it.
- **One app on Windows, Linux and Android**, drawn by the same engine. Linux and the native Android app are new in 2.0.
- **Permissive licences throughout.** PDFs are handled by PDFium.
- **Same engine as [Hearth](https://github.com/AhmiDarrow/Hearth)**, [SecretSticky](https://github.com/AhmiDarrow/SecretSticky) and [SecretFolder](https://github.com/AhmiDarrow/SecretFolder).

RemedyUI is not public yet.

## Features

| Area | Details |
|------|---------|
| **Formats** | PDF, EPUB, XPS/OXPS, CBZ, CBR, FB2, HTML, TXT, SVG, DOCX, MOBI, and PNG, JPG, BMP, GIF, TIFF and WEBP images |
| **Save as PDF** | Anything RemedyPDF opens can be saved as a PDF |
| **Edit** | Add text and images to a PDF; hold a page to add text on a touch screen |
| **Passwords** | Password-protected PDFs stay protected when saved (AES-256) |
| **Reading** | Book mode (two pages side by side), reader mode, fit modes, view rotation |
| **Comfort** | Nine themes, page filters (invert, sepia and more), brightness and contrast |
| **Zoom** | 15% steps, or 1% for fine control |
| **Find** | Search the text of a document |
| **Keyboard** | Help → Keyboard Shortcuts lists every shortcut |
| **Updates** | Signed updates from GitHub Releases, installed automatically unless you turn that off |

## Install

Download from **[Releases](https://github.com/AhmiDarrow/RemedyPDF/releases/latest)**.

### Windows (10 or later, 64-bit)

Run `RemedyPDF_<version>_x64-setup.exe`, or unpack the portable zip. The installer is not code-signed, so Windows may warn you the first time. RemedyPDF 1.x updates to 2.0 from inside the app.

### Linux (x86-64)

Needs glibc 2.28 or newer (Debian 10, RHEL 8, Ubuntu 20.04 and later).

```bash
tar -xzf RemedyPDF-<version>-linux-x86_64.tar.gz --strip-components=1 -C ~/.local
```

### Android (8 or later, ARM)

Install `RemedyPDF_<version>_universal.apk`. Android asks you once to allow RemedyPDF to install updates, and Google Play Protect may offer to scan the app.

### Updates

RemedyPDF checks for updates and installs only files signed with its update key. On Windows and Linux it installs them by itself and reopens your document, and it never restarts over unsaved changes. Android asks you to confirm each one. Turn this off with **Help → Install Updates Automatically**.

## Known issues

- **Android:** text that arrives in a very fast burst can lose letters. Typing one key at a time lost none in testing.
- **Android:** secure connections are checked against the certificates built into Android. Certificates you add or switch off in Android's settings are not taken into account, and revoked website certificates are not detected. Updates are still protected by their signature.

## Development

RemedyPDF 2.0 and later is the Rust app in `remedyui/`. RemedyUI is not public yet, so building needs a checkout of it at the path in `remedyui/Cargo.toml`, and PDFium from [pdfium-binaries](https://github.com/bblanchon/pdfium-binaries) in `remedyui/pdfium/`.

```bash
cd remedyui
cargo test              # the app's screens and updates
python tests/pdf.py     # also encryption, formats, reflow and xps
cargo run --release
```

The Python tests use PyMuPDF only as a reference to compare against. It is not part of the app. Packages are built with `cargo remedy package` (see `remedyui/remedy.toml`).

## Stack

- **Rust** + **RemedyUI** (windows, text, pages, accessibility, updates)
- **Documents:** PDFium for PDFs, with RemedyPDF's own readers for e-books, DOCX and XPS
- **Updates:** minisign-signed GitHub Releases

## About

Hi I'm Ahmi, hope this helps!

- GitHub: [github.com/AhmiDarrow](https://github.com/AhmiDarrow)
- This project: [AhmiDarrow/RemedyPDF](https://github.com/AhmiDarrow/RemedyPDF)
- Releases: [github.com/AhmiDarrow/RemedyPDF/releases](https://github.com/AhmiDarrow/RemedyPDF/releases)
- Support: [patreon.com/cw/AhmiDarrow](https://www.patreon.com/cw/AhmiDarrow) — thank you!

## License

[MIT](LICENSE) © Ahmi Darrow. Third-party notices ship with each package.
