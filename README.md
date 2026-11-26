# RemedyPDF

A multi-format document viewer and editor for Windows, Linux and Android.

**Hi I'm Ahmi, hope this helps!**

- Download: https://github.com/AhmiDarrow/RemedyPDF/releases/latest
- Patreon: https://www.patreon.com/cw/AhmiDarrow

Version 2 is a native app written in Rust on RemedyUI, with PDFium for PDFs. Everything in it
uses a permissive licence.

## What it does

- **Opens** PDF, EPUB, XPS/OXPS, CBZ, CBR, FB2, HTML, TXT, SVG, DOCX, MOBI and images
  (PNG, JPG, BMP, GIF, TIFF, WEBP). Anything it opens can be saved as a PDF.
- **Edits** PDFs: add text and images. Password-protected PDFs stay protected when saved
  (AES-256).
- **Reads comfortably:** book mode (two pages side by side), reader mode, nine themes, page
  filters, brightness and contrast, view rotation, fit modes, and zoom in 1% or 15% steps.
- **Updates itself.** An update is installed only if it is signed with RemedyPDF's update key.
  Help, "Install Updates Automatically" turns automatic installing off.

Help, "Keyboard Shortcuts" lists every shortcut.

## Install

| System | File | Updates |
|---|---|---|
| Windows 10 and later (64-bit) | `RemedyPDF_<version>_x64-setup.exe`, or the portable zip | The installed app updates with no clicks and reopens your document |
| Linux x86-64 (glibc 2.28 and later) | `RemedyPDF_<version>_linux-x86_64`, or the `.tar.gz` | The program replaces itself and restarts |
| Android 8 and later (ARM) | `RemedyPDF_<version>_universal.apk` | Android asks you to confirm each update |

RemedyPDF 1.x on Windows updates to version 2 from inside the app.

The Windows installer is not code-signed, so Windows may warn you the first time.

## Good to know (Android)

- Android asks you once to allow RemedyPDF to install updates. Google Play Protect may also
  offer to scan the app, because it has not seen it before.
- Secure connections are checked against the certificates built into Android. Certificates
  you add or switch off in Android's settings are not taken into account, and a revoked
  website certificate is not detected. Updates are protected separately: only a file signed
  with RemedyPDF's update key is offered for install.
- **Known issue:** text that arrives in a very fast burst, as from a barcode scanner or an
  automated tool, can lose letters. Typing on the on-screen keyboard one key at a time lost
  none in testing.

## Building

The app is in `remedyui/`. It expects the RemedyUI engine beside this repository, at the
path in `remedyui/Cargo.toml`, and PDFium from
[pdfium-binaries](https://github.com/bblanchon/pdfium-binaries) in `remedyui/pdfium/`
(`pdfium.dll` for Windows, and `linux-x64/`, `arm64-v8a/`, `armeabi-v7a/` for the others).

```bash
cd remedyui
cargo test
python tests/pdf.py        # also encryption, formats, reflow, xps
```

The Python tests use PyMuPDF only as a reference to compare against. It is not part of the app.

Packaging uses `cargo remedy package` (see `remedyui/remedy.toml`). `pack/build-linux.sh`
builds the Linux package in WSL, and `pack/latest_json.py` collects the signed files and
writes the update list.

## License

MIT, © Ahmi Darrow. Third-party notices ship with each package.
