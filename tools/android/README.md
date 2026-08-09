# Android toolchain notes

## What ships a real APK

GitHub Actions **Release** workflow (`build-android` on `ubuntu-latest`) installs
Buildozer + Android command-line tools, accepts licenses, and runs:

```bash
python build_android.py --prefer-apk
```

Artifact: `RemedyPDF-<ver>-android.apk` (plus src zip fallback).

## Local (Linux / WSL recommended)

```bash
source tools/android/env.sh
pip install buildozer cython virtualenv
# Install Android SDK cmdline-tools, platform-tools, platforms;android-33, ndk
python build_android.py
```

## Windows desktop

PyQt5 APK via Buildozer is not supported on native Windows. Use WSL2 Ubuntu
or rely on the CI release job. `python build_android.py` still emits the
mobile source zip for inspection.
