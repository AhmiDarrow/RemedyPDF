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

1. Download **`RemedyPDF-*-android.apk`** when a full APK is attached to the release,
   **or** the **`RemedyPDF-*-android-src.zip`** mobile source bundle + README.
2. Enable **Install unknown apps** for your file manager / browser.
3. Open the APK to install.

Full APK builds need Buildozer + Android SDK/NDK (Linux/macOS CI or WSL):

```bash
# Install Python helpers + env scripts (Windows OK; real APK on Linux/WSL/CI)
python scripts/setup_android_toolchain.py

# Linux / WSL / CI:
source tools/android/env.sh   # or tools/android/env.ps1 on PowerShell
python build_android.py
```

Release workflow (`ubuntu-latest`) installs cmdline-tools + NDK and runs the same
script so the next tag can ship `RemedyPDF-*-android.apk` when Buildozer succeeds.

Without a full SDK, `build_android.py` still stages the mobile source zip and
`ANDROID_BUILD.md` so the release always has an Android artifact.

## Auto-update

Help → **About** → **Check for updates** (or Help → Check for Updates…).

The app reads GitHub Releases + `latest.json` (Windows Setup + Android APK URLs).

## Uninstall (Windows)

Settings → Apps → RemedyPDF → Uninstall, or use the Start Menu uninstall entry.
