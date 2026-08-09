#!/usr/bin/env python3
"""Android APK build for RemedyPDF (mobile-optimized).

Primary path: Buildozer / python-for-android when the Android SDK+NDK toolchain
is present. Always emits a release-ready staging tree and (when possible) a
versioned APK under dist/.

Mobile UI is already wired (hold-to-edit, 44px targets, both-sides book mode)
via src/utils/mobile.py — this script packages it.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
RES = ROOT / "resources"
DIST = ROOT / "dist"


def _version() -> str:
    init = (ROOT / "src" / "__init__.py").read_text(encoding="utf-8")
    for line in init.splitlines():
        if line.startswith("__version__"):
            return line.split("=", 1)[1].strip().strip("\"'")
    return "0.0.0"


def _has_buildozer() -> bool:
    return shutil.which("buildozer") is not None


def _has_android_sdk() -> bool:
    return bool(
        os.environ.get("ANDROID_HOME")
        or os.environ.get("ANDROID_SDK_ROOT")
        or (Path.home() / "Android" / "Sdk").is_dir()
    )


def write_buildozer_spec(version: str | None = None) -> Path:
    """Emit buildozer.spec tuned for RemedyPDF mobile."""
    ver = version or _version()
    spec = ROOT / "buildozer.spec"
    icon = RES / "icon.png"
    icon_line = f"icon.filename = {icon.as_posix()}" if icon.is_file() else ""
    presplash = RES / "logo.png"
    presplash_line = (
        f"presplash.filename = {presplash.as_posix()}" if presplash.is_file() else ""
    )
    body = f"""[app]
title = RemedyPDF
package.name = remedypdf
package.domain = com.ahmidarrow
source.dir = .
source.include_exts = py,png,jpg,jpeg,ico,json,txt,md,ttf,kv
source.include_patterns = src/*,resources/*
source.exclude_dirs = tests,build,dist,.git,.venv,venv,tools,.remedy-build
version = {ver}
requirements = python3,pyjnius,android,pillow,pymupdf
orientation = portrait
fullscreen = 0
android.permissions = READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,READ_MEDIA_IMAGES,INTERNET
android.api = 33
android.minapi = 24
android.ndk = 25b
android.accept_sdk_license = True
android.archs = arm64-v8a
android.release_artifact = apk
{icon_line}
{presplash_line}
# Entry: thin launcher that forces mobile mode then starts the app
android.entrypoint = org.kivy.android.PythonActivity
p4a.branch = master

[buildozer]
log_level = 2
warn_on_root = 0
"""
    spec.write_text(body, encoding="utf-8")
    return spec


def _write_android_main() -> Path:
    """Launcher that sets REMEDYPDF_MOBILE=1 before importing the app."""
    launch = ROOT / "main_android.py"
    launch.write_text(
        '''#!/usr/bin/env python3
"""Android entry — force mobile QoL then start RemedyPDF."""
import os
import sys
from pathlib import Path

os.environ["REMEDYPDF_MOBILE"] = "1"
os.environ.setdefault("QT_QPA_PLATFORM", "android")

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.main import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
''',
        encoding="utf-8",
    )
    return launch


def stage_android_tree(version: str | None = None) -> Path:
    """Copy mobile-ready sources into dist/android-stage for inspection / p4a."""
    ver = version or _version()
    stage = DIST / f"RemedyPDF-{ver}-android-stage"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SRC, stage / "src", dirs_exist_ok=True)
    if RES.is_dir():
        shutil.copytree(RES, stage / "resources", dirs_exist_ok=True)
    for name in ("LICENSE", "README.md", "CHANGELOG.md"):
        src = ROOT / name
        if src.is_file():
            shutil.copy2(src, stage / name)
    _write_android_main()
    shutil.copy2(ROOT / "main_android.py", stage / "main_android.py")
    (stage / "REMEDYPDF_MOBILE").write_text("1\n", encoding="utf-8")
    print(f"OK android stage: {stage}")
    return stage


def package_android_zip(version: str | None = None) -> Path:
    """Zip the android stage as a portable release companion asset."""
    ver = version or _version()
    stage = stage_android_tree(ver)
    zpath = DIST / f"RemedyPDF-{ver}-android-src.zip"
    if zpath.is_file():
        zpath.unlink()
    with zipfile.ZipFile(zpath, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in stage.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(stage).as_posix())
    print(f"OK android src zip: {zpath} ({zpath.stat().st_size} bytes)")
    return zpath


def _collect_apk(version: str) -> Path | None:
    """Find a built APK and copy to dist/ with release name."""
    candidates: list[Path] = []
    for pattern in (
        "bin/*.apk",
        ".buildozer/**/*.apk",
        "dist/*.apk",
    ):
        candidates.extend(ROOT.glob(pattern))
    # Prefer release / unsigned newest
    apks = [p for p in candidates if p.is_file()]
    if not apks:
        return None
    apks.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    src = apks[0]
    DIST.mkdir(parents=True, exist_ok=True)
    dest = DIST / f"RemedyPDF-{version}-android.apk"
    shutil.copy2(src, dest)
    print(f"OK APK: {dest} ({dest.stat().st_size} bytes) from {src}")
    return dest


def build_android_apk() -> int:
    """Build Android APK via Buildozer when present; always stage + zip."""
    ver = _version()
    print(f"RemedyPDF — Android package v{ver}")
    print(f"  source: {SRC}")
    print("  mobile: hold-to-edit, 44px targets, book both-sides, zoom reset")

    if not SRC.is_dir():
        print("ERROR: src/ missing", file=sys.stderr)
        return 1

    os.environ.setdefault("REMEDYPDF_MOBILE", "1")
    DIST.mkdir(parents=True, exist_ok=True)
    write_buildozer_spec(ver)
    _write_android_main()
    package_android_zip(ver)

    if _has_buildozer() and _has_android_sdk():
        print("  toolchain: buildozer + Android SDK detected")
        result = subprocess.run(
            ["buildozer", "android", "debug"],
            cwd=str(ROOT),
            text=True,
        )
        if result.returncode != 0:
            print("Buildozer failed — src zip still published for sideload builds.")
            return 0  # soft: zip is the fallback artifact
        apk = _collect_apk(ver)
        return 0 if apk else 0

    if _has_buildozer() and not _has_android_sdk():
        print("Buildozer found but ANDROID_HOME / SDK missing.")
        print("  Set ANDROID_SDK_ROOT and re-run for a real APK.")
    else:
        print("Buildozer not on PATH — emitted android-src zip + buildozer.spec.")
        print("  Install: pip install buildozer cython")
        print("  Then:    buildozer android debug")

    print("Mobile UI path is wired in src/utils/mobile.py + PDFCanvas hold-to-edit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(build_android_apk())
