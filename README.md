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
- **Themes** — Dark / light Remedy QSS (`Ctrl+Shift+T`)
- **Mobile / APK** — Larger touch targets, flick scroll, hold-to-edit, mobile default zoom
- **Brand assets** — Window icon (`resources/icon.ico` / `icon.png`) + About logo (`logo_ui.png`)
- **About + Auto-Update** — SecretSticky-style About (hello, links, Check for updates) against GitHub Releases + optional `latest.json`
- **Cross-Platform** — Windows primary; Android build script scaffold

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
| Theme toggle | Ctrl+Shift+T |
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

- `RemedyPDF.exe` (PyInstaller onefile, branded icon)
- `latest.json` — `{ "version", "notes", "url", "pub_date" }` for the in-app checker

## Tests

```bash
pytest -q
```

CI runs the same suite on Windows + Ubuntu (offscreen Qt).

## Building

### Windows Installer

```bash
python build_windows.py
# or:
python -m PyInstaller --name RemedyPDF --onefile --windowed --add-data "resources;resources" --icon resources/icon.ico src/main.py
```

### Android APK (scaffold)

```bash
python build_android.py
```

Touch/APK notes:

- Hold ~450ms on a page to edit
- Toolbar and navigator buttons use ≥44px touch targets
- Mobile stylesheet extras apply automatically when Android/touch is detected

## Versioning & release

1. Bump `__version__` in `src/__init__.py` (single source of truth)
2. Update `CHANGELOG.md`
3. Push to `main` → CI must be green
4. Tag and push: `git tag v1.2.0 && git push origin v1.2.0`
5. GitHub Actions **Release** workflow builds the exe, writes `latest.json`, and opens a draft release

## License

MIT — © Ahmi Darrow
