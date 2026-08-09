#!/usr/bin/env python3
"""Install what we can for a real APK on the next release.

Windows note: full Buildozer APK builds need Linux (CI ubuntu-latest or WSL).
This script:
  1. pip-installs buildozer + cython into the active env (best-effort)
  2. Writes tools/android/env.ps1 + env.sh with SDK path hints
  3. Emits buildozer.spec + main_android.py via build_android.py
  4. Documents the CI path that produces RemedyPDF-*-android.apk

Does not download multi-GB Android SDK/NDK into the repo (that belongs on CI
or a dedicated SDK root outside the project).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools" / "android"
DIST = ROOT / "dist"


def _run(cmd: list[str]) -> int:
    print("+", " ".join(cmd))
    try:
        return subprocess.call(cmd, cwd=str(ROOT))
    except FileNotFoundError as exc:
        print(f"skip: {exc}")
        return 127


def install_python_deps() -> None:
    py = sys.executable
    pkgs = ["buildozer", "cython", "virtualenv"]
    print("Installing Python APK toolchain helpers:", ", ".join(pkgs))
    code = _run([py, "-m", "pip", "install", "--upgrade", *pkgs])
    if code != 0:
        print("WARN: pip install buildozer failed (often fine on pure Windows).")
    else:
        print("OK: buildozer/cython available in this env (use on Linux/WSL for APK).")


def write_env_helpers() -> None:
    TOOLS.mkdir(parents=True, exist_ok=True)
    # Prefer standard user SDK locations without writing outside the project
    candidates = [
        os.environ.get("ANDROID_SDK_ROOT", "").strip(),
        os.environ.get("ANDROID_HOME", "").strip(),
        str(Path.home() / "Android" / "Sdk"),
        str(Path(os.environ.get("LOCALAPPDATA", "")) / "Android" / "Sdk"),
        str(ROOT / "tools" / "android-sdk"),  # optional local mount
    ]
    sdk = ""
    for c in candidates:
        if c and Path(c).is_dir():
            sdk = c
            break
    if not sdk:
        sdk = str(Path.home() / "Android" / "Sdk")

    ps1 = TOOLS / "env.ps1"
    ps1.write_text(
        f"""# RemedyPDF Android env (dot-source before local experiments)
# Full APK builds: use GitHub Actions ubuntu job or WSL — not bare Windows.
$env:ANDROID_SDK_ROOT = if ($env:ANDROID_SDK_ROOT) {{ $env:ANDROID_SDK_ROOT }} else {{ "{sdk}" }}
$env:ANDROID_HOME = $env:ANDROID_SDK_ROOT
$env:REMEDYPDF_MOBILE = "1"
Write-Host "ANDROID_SDK_ROOT=$($env:ANDROID_SDK_ROOT)"
Write-Host "Tip: real APK is built on CI (release.yml build-android job)."
""",
        encoding="utf-8",
    )

    sh = TOOLS / "env.sh"
    sh.write_text(
        f"""#!/usr/bin/env bash
# RemedyPDF Android env — source from bash/WSL/Linux CI
export ANDROID_SDK_ROOT="${{ANDROID_SDK_ROOT:-{sdk}}}"
export ANDROID_HOME="${{ANDROID_HOME:-$ANDROID_SDK_ROOT}}"
export REMEDYPDF_MOBILE=1
echo "ANDROID_SDK_ROOT=$ANDROID_SDK_ROOT"
""",
        encoding="utf-8",
    )

    readme = TOOLS / "README.md"
    readme.write_text(
        """# Android toolchain notes

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
""",
        encoding="utf-8",
    )
    print(f"OK wrote {ps1}")
    print(f"OK wrote {sh}")
    print(f"OK wrote {readme}")


def refresh_android_package() -> None:
    sys.path.insert(0, str(ROOT))
    from build_android import build_android_apk, write_buildozer_spec

    write_buildozer_spec()
    code = build_android_apk()
    print(f"build_android_apk exit={code}")


def main() -> int:
    print("RemedyPDF — setup Android toolchain helpers")
    install_python_deps()
    write_env_helpers()
    try:
        refresh_android_package()
    except Exception as exc:  # noqa: BLE001
        print(f"WARN package refresh: {exc}")
    print("Done. Next release tag will use the upgraded CI APK job.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
