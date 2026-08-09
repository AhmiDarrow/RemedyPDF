# Install RemedyPDF

Hi I'm Ahmi, hope this helps!

## Windows (recommended)

1. Download **`RemedyPDF-*-windows-setup.exe`** from
   [Releases](https://github.com/AhmiDarrow/RemedyPDF/releases).
2. Run the Setup wizard (per-user install, no admin required).
3. Optional: create a Desktop shortcut when prompted.
4. Launch **RemedyPDF** from the Start Menu.

Portable option: download **`RemedyPDF-*-windows.exe`** (onefile) and run it
directly — no install step.

### Build the Windows installer locally

```bash
pip install -r requirements.txt pyinstaller
python build_windows.py
# artifacts:
#   dist/RemedyPDF.exe
#   dist/RemedyPDF-<ver>-windows-setup.exe   (when Inno Setup 6 is available)
```

Inno Setup is auto-downloaded into `tools/InnoSetup` when missing (CI does this too).

## Android

Every release ships **`RemedyPDF-*-android-src.zip`** (mobile-ready sources +
`buildozer.spec` + `main_android.py`). That is the default, reliable Android asset.

When a full **`RemedyPDF-*-android.apk`** is attached (opt-in CI or local Buildozer):

1. Enable **Install unknown apps** for your file manager / browser.
2. Open the APK to install.

### Why zip-first?

Buildozer + NDK on free GitHub runners is slow (often 30–90+ minutes) and fragile
(PyQt5 is not a stock p4a recipe). Tag releases therefore **always** publish the
mobile source zip in minutes. Full APK is optional:

```bash
# Local / WSL / Linux with SDK+NDK:
python scripts/setup_android_toolchain.py
source tools/android/env.sh   # or tools/android/env.ps1
python build_android.py --prefer-apk

# CI opt-in: Actions → Release → Run workflow → build_apk = true
```

```bash
# Fast package only (what CI does on every tag):
python build_android.py --zip-only
```

## Auto-update

Help → **About** → **Check for updates** (or Help → Check for Updates…).

The app reads GitHub Releases + `latest.json` (Windows Setup + Android APK URLs).

## Uninstall (Windows)

Settings → Apps → RemedyPDF → Uninstall, or use the Start Menu uninstall entry.
