# RemedyPDF

A sleek, fast multi-format document viewer and editor with Remedy themes, both-sides book mode, reader mode, mobile/APK polish, and **GitHub Releases auto-update**.

**Hi I'm Ahmi, hope this helps!**

- Profile: https://github.com/AhmiDarrow
- Repo: https://github.com/AhmiDarrow/RemedyPDF
- Releases: https://github.com/AhmiDarrow/RemedyPDF/releases
- Patreon: https://www.patreon.com/cw/AhmiDarrow

## Features

- **View documents** — Fast rendering with zoom, pan, and scroll (PyMuPDF)
- **Multi-format** — PDF, EPUB, XPS/OXPS, CBZ, CBR, FB2, HTML, TXT — plus SVG, DOCX (MuPDF office input), MOBI and images (PNG/JPG/BMP/GIF/TIFF/WEBP) as page-based documents. Everything saves as PDF.
- **Fine zoom** — Ctrl+Scroll / Ctrl+Shift+/- for **1%** steps; Ctrl+/- for 15%
- **Zoom reset** — Toolbar **Reset** or **Ctrl+0**
- **Book mode** — **Both sides** two-page spreads (0+1, 2+3, …) via Ctrl+B
- **Edit** — **Double-click** (PC) or **hold / long-press** (mobile) to add text at a point
- **View rotation** — Ctrl+R / Ctrl+Shift+R rotate the view 90° (view-only — great for scanned portrait PDFs; edit hit-testing stays exact)
- **Wheel & mouse nav** — in fit view the wheel turns the page like a book; mouse side buttons go back/forward; two-finger trackpad swipe flips pages
- **9 themes** — Default **Normal (no theme)** keeps the plain system look; Dark, Light, High contrast, Sepia, Night OLED, Midnight, Soft paper and Slate are one click away (`Ctrl+Shift+T` cycles Normal → Dark → … → Slate → Normal)
- **Page appearance** — Invert / sepia / grayscale / warm / cool filters + brightness & contrast (view-only)
- **UI Scale** — Chrome font 90–150% independent of page zoom
- **Fit modes** — Width / page / height (`Ctrl+1/2/3`) + full screen (`F11`)
- **Reader mode** — toolbar toggle hides the toolbar, navigator, search bar and status bar for distraction-free reading (Esc exits)
- **Mobile / APK** — Larger touch targets, flick scroll, **tap zones** flip pages (tap right/left third), **pinch-to-zoom** around your fingers, hold-to-edit, mobile default zoom
- **Brand assets** — Window icon (`resources/icon.ico` / `icon.png`) + About logo (`logo_ui.png`)
- **About + Auto-Update** — SecretSticky-style About (hello, platform tags, Check for updates) against GitHub Releases + `latest.json`
- **Windows installer** — Inno Setup `*-windows-setup.exe` (built **onedir** — no temp-extraction bootloader crash on auto-update relaunch) + portable onefile exe
- **Android package** — every release ships `*-android-src.zip` (fast CI); full APK via opt-in Buildozer

## Requirements

- Python 3.10+
- PyQt5, PyMuPDF, Pillow

```bash
pip install -r requirements.txt
```

## Dev launch

```bash
python src/main.py
# or open a file directly:
python src/main.py path\to\file.pdf
```

## Brand assets

| File | Use |
|------|-----|
| `resources/icon.png` | Window / app icon (PNG) |
| `resources/icon.ico` | Windows exe + PyInstaller |
| `resources/logo.png` / `logo_ui.png` | About dialog mark |
| `resources/icons/icon_*.png` | Multi-size favicons |

Rebuild from Remedy references:

```bash
python scripts/build_brand_assets.py
python scripts/_verify_brand.py
```

## Hotkeys (summary)

| Action | Shortcut |
|--------|----------|
| Open / Save | Ctrl+O / Ctrl+S |
| Zoom ±15% | Ctrl++ / Ctrl+- |
| Fine zoom 1% | Ctrl+Scroll, Ctrl+Shift+/- |
| Reset zoom | Ctrl+0 / toolbar Reset |
| Book mode (both sides) | Ctrl+B |
| Rotate view 90° | Ctrl+R / Ctrl+Shift+R |
| Fit width / page / height | Ctrl+1 / Ctrl+2 / Ctrl+3 |
| Full screen / Reader mode | F11 / toolbar toggle (Esc exits) |
| Go to page | Ctrl+G |
| Close document | Ctrl+W |
| First / last page | Ctrl+Home / Ctrl+End |
| Page up / down | Ctrl+PgUp / Ctrl+PgDn |
| Re-render | F5 |
| Wheel flips pages | in fit view (or scroll edge when zoomed) |
| Side buttons | back / forward |
| Cycle theme (9 incl. Normal) | Ctrl+Shift+T |
| High contrast / Sepia / Night | Ctrl+Shift+H / S / N |
| Invert page | Ctrl+Shift+I |
| Brightness ± | Ctrl+Shift+↑ / ↓ |
| Contrast ± | Ctrl+Alt+↑ / ↓ |
| Reset page appearance | Ctrl+Shift+0 |
| Find | Ctrl+F |
| Pages | ← → PgUp PgDown Space |
| Edit text at point | Double-click (PC) / Hold (mobile) |
| About | Help → About |
| Check for updates | Help → Check for Updates… |

## Auto-update

Installed / release builds check **GitHub Releases** (and optional `latest.json` on the release):

1. **Help → About** → **Check for updates**
2. Or **Help → Check for Updates…**
3. If a newer tag exists, **Open release** / **Get update** opens the Releases page

Channel constants live in `src/__init__.py` (`GITHUB_OWNER`, `GITHUB_REPO`, version).

Release workflow publishes:

- `RemedyPDF-*-windows-setup.exe` — Inno Setup installer (onedir app folder — reliable auto-update relaunch)
- `RemedyPDF-*-windows.exe` / `RemedyPDF.exe` — portable onefile
- `RemedyPDF-*-android-src.zip` (always) and optional `*-android.apk`
- `latest.json` — multi-platform `{ version, platforms.windows-x86_64, platforms.android-arm64 }`
- `icon.png`

## Tests

```bash
pytest -q
```

CI runs the same suite on Windows + Ubuntu (offscreen Qt).

## Building

### Windows installer (Setup.exe)

```bash
pip install pyinstaller
python build_windows.py
# → dist/RemedyPDF/                           (onedir app folder)
# → dist/RemedyPDF-<ver>-windows-setup.exe    (Inno Setup installer)
# → dist/RemedyPDF-<ver>-windows.exe          (portable onefile)
```

The app is built **onedir** (DLLs as real files next to the exe — no `%TEMP%` extraction, no bootloader race on auto-update relaunch); the portable single-file exe is still published for manual download. Inno Setup 6 is used when present, or auto-downloaded into `tools/InnoSetup` (`--download-inno`, default on). Script: `installer/remedypdf.iss`.

See [docs/INSTALL.md](docs/INSTALL.md).

### Android package

```bash
# Fast (what every tag ships):
python build_android.py --zip-only
# → dist/RemedyPDF-<ver>-android-src.zip

# Full APK (Linux/WSL + SDK/NDK; slow):
python scripts/setup_android_toolchain.py
python build_android.py --prefer-apk
# → dist/RemedyPDF-<ver>-android.apk
```

CI Release is **zip-first**. Opt-in full APK: workflow_dispatch `build_apk=true`.

Touch/APK notes:

- Hold ~450ms on a page to edit
- Tap right/left third of the screen to flip pages; drag and pinch still pan/zoom
- Toolbar and navigator buttons use ≥44px touch targets
- Mobile stylesheet extras apply automatically when Android/touch is detected

## Versioning & release

1. Bump `__version__` in `src/__init__.py` (single source of truth)
2. Update `CHANGELOG.md`
3. Push to `main` → CI must be green
4. Tag and push: `git tag v1.4.5 && git push origin v1.4.5`
5. GitHub Actions **Release** workflow builds:
   - Windows Setup installer + portable exe
   - Android mobile source zip (APK only if `build_apk=true`)
   - `latest.json` (multi-platform autoupdate channel)

## License

MIT — © Ahmi Darrow
