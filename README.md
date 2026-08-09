# RemedyPDF

A sleek, fast multi-format document viewer and editor with Remedy themes, both-sides book mode, mobile/APK polish, and **GitHub Releases auto-update**.

**Hi I'm Ahmi, hope this helps!**

- Profile: https://github.com/AhmiDarrow
- Repo: https://github.com/AhmiDarrow/RemedyPDF
- Releases: https://github.com/AhmiDarrow/RemedyPDF/releases
- Patreon: https://www.patreon.com/cw/AhmiDarrow

## Features

- **View documents** — Fast rendering with zoom, pan, and scroll (PyMuPDF)
- **Multi-format** — PDF, EPUB, XPS/OXPS, CBZ, FB2, HTML, TXT
- **Fine zoom** — Ctrl+Scroll / Ctrl+Shift+/- for **1%** steps; Ctrl+/- for 15%
- **Zoom reset** — Toolbar **Reset** or **Ctrl+0**
- **Book mode** — **Both sides** two-page spreads (0+1, 2+3, …) via Ctrl+B
- **Edit** — **Double-click** (PC) or **hold / long-press** (mobile) to add text at a point
- **8 visibility themes** — Dark, Light, High contrast, Sepia, Night OLED, Midnight, Soft paper, Slate (`Ctrl+Shift+T`)
- **Page appearance** — Invert / sepia / grayscale / warm / cool filters + brightness & contrast (view-only)
- **UI Scale** — Chrome font 90–150% independent of page zoom
- **Fit modes** — Width / page / height (`Ctrl+1/2/3`) + full screen (`F11`)
- **Mobile / APK** — Larger touch targets, flick scroll, hold-to-edit, mobile default zoom
- **Brand assets** — Window icon (`resources/icon.ico` / `icon.png`) + About logo (`logo_ui.png`)
- **About + Auto-Update** — SecretSticky-style About (hello, platform tags, Check for updates) against GitHub Releases + `latest.json`
- **Windows installer** — Inno Setup `*-windows-setup.exe` (Start Menu + Desktop shortcuts) + portable onefile
- **Android package** — every release ships `*-android-src.zip` (fast CI); full APK via opt-in Buildozer

## Requirements

- Python 3.10+
- PyQt5, PyMuPDF, PyPDF2, Pillow

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
| Fit width / page / height | Ctrl+1 / Ctrl+2 / Ctrl+3 |
| Full screen | F11 |
| Cycle theme (8) | Ctrl+Shift+T |
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

- `RemedyPDF-*-windows-setup.exe` — Inno Setup installer
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
# → dist/RemedyPDF.exe                          (portable onefile)
# → dist/RemedyPDF-<ver>-windows-setup.exe      (Inno Setup installer)
```

Inno Setup 6 is used when present, or auto-downloaded into `tools/InnoSetup`
(`--download-inno`, default on). Script: `installer/remedypdf.iss`.

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
- Toolbar and navigator buttons use ≥44px touch targets
- Mobile stylesheet extras apply automatically when Android/touch is detected

## Versioning & release

1. Bump `__version__` in `src/__init__.py` (single source of truth)
2. Update `CHANGELOG.md`
3. Push to `main` → CI must be green
4. Tag and push: `git tag v1.3.0 && git push origin v1.3.0`
5. GitHub Actions **Release** workflow builds:
   - Windows Setup installer + portable exe
   - Android mobile source zip (APK only if `build_apk=true`)
   - `latest.json` (multi-platform autoupdate channel)

## License

MIT — © Ahmi Darrow
