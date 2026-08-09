# Contributing to RemedyPDF

Thanks for helping — Hi I'm Ahmi, hope this helps!

## Setup

```bash
git clone https://github.com/AhmiDarrow/RemedyPDF.git
cd RemedyPDF
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
pytest -q
python src/main.py
```

## Project layout

- `src/core/` — engine + main window
- `src/ui/` — theme, widgets, About
- `src/utils/` — paths, brand, updater, mobile
- `resources/` — icon/logo assets (required for builds)
- `tests/` — pytest (offscreen Qt)
- `.github/workflows/` — CI + Release

## Version bump

Edit **only** `src/__init__.py` `__version__`. `setup.py` and the app read it from there.

## Release

1. Green CI on `main`
2. `git tag vX.Y.Z && git push origin vX.Y.Z`
3. Release workflow attaches:
   - `RemedyPDF-*-windows-setup.exe` (Inno installer)
   - `RemedyPDF-*-windows.exe` / `RemedyPDF.exe` (portable)
   - `RemedyPDF-*-android.apk` or `*-android-src.zip`
   - `latest.json` (windows + android URLs)
   - `icon.png`

## Code style

- Python 3.10+, type hints where practical
- Keep headless tests free of modal dialogs (`QT_QPA_PLATFORM=offscreen`)
