#!/usr/bin/env python3
"""Android APK build for RemedyPDF (mobile-optimized).

Primary path: Buildozer / python-for-android when the Android SDK+NDK toolchain
is present. Always emits a release-ready staging tree and (when possible) a
versioned APK under dist/.

CLI:
  python build_android.py              # zip + APK attempt if toolchain present
  python build_android.py --zip-only   # stage + android-src.zip only
  python build_android.py --prefer-apk # force Buildozer APK attempt

Mobile UI is already wired (hold-to-edit, 44px targets, both-sides book mode)
via src/utils/mobile.py — this script packages it.
"""

from __future__ import annotations

import argparse
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
    env_paths = [
        os.environ.get("ANDROID_HOME", "").strip(),
        os.environ.get("ANDROID_SDK_ROOT", "").strip(),
    ]
    for p in env_paths:
        if p and Path(p).is_dir():
            return True
    return (Path.home() / "Android" / "Sdk").is_dir()


def write_buildozer_spec(version: str | None = None) -> Path:
    """Emit buildozer.spec tuned for RemedyPDF mobile (CI-friendly relative paths)."""
    ver = version or _version()
    spec = ROOT / "buildozer.spec"
    icon_rel = "resources/icon.png"
    logo_rel = "resources/logo.png"
    icon_line = f"icon.filename = {icon_rel}" if (RES / "icon.png").is_file() else ""
    presplash_line = (
        f"presplash.filename = {logo_rel}" if (RES / "logo.png").is_file() else ""
    )
    # source.include_exts keeps packaging lean; main_android.py is entry via
    # p4a recipe default (main.py). We also ship main_android.py and a thin main.py.
    body = f"""[app]
title = RemedyPDF
package.name = remedypdf
package.domain = com.ahmidarrow
source.dir = .
source.include_exts = py,png,jpg,jpeg,ico,json,txt,md,ttf,kv
source.include_patterns = src/*,resources/*,main_android.py,main.py
source.exclude_dirs = tests,build,dist,.git,.venv,venv,tools,.remedy-build,.buildozer,bin
version = {ver}
requirements = python3,kivy,pyjnius,android,pillow,pymupdf
orientation = all
fullscreen = 0
android.permissions = INTERNET
android.api = 34
android.minapi = 26
android.ndk = 25b
android.accept_sdk_license = True
android.archs = armeabi-v7a
android.release_artifact = apk
android.entrypoint = org.kivy.android.PythonActivity
p4a.branch = master
{icon_line}
{presplash_line}

[buildozer]
log_level = 2
warn_on_root = 0
"""
    spec.write_text(body, encoding="utf-8")
    return spec


def _write_android_main() -> Path:
    """Write the Kivy-based Android entry point (mirrors on-disk main_android.py)."""
    launch = ROOT / "main_android.py"
    launch.write_text(
        '''#!/usr/bin/env python3
"""Android entry — Kivy-based PDF viewer for RemedyPDF.

Sets REMEDYPDF_MOBILE=1, then launches the Kivy UI (src/ui/kivy_app.py).
PyQt5 is NOT imported on Android — the Kivy app uses the same PDFEngine
backend directly.
"""
import os
import sys
from pathlib import Path

os.environ["REMEDYPDF_MOBILE"] = "1"

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    """Launch the Kivy-based Android PDF viewer. Returns exit code."""
    from src.ui.kivy_app import RemedyPDFApp

    RemedyPDFApp().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
''',
        encoding="utf-8",
    )
    # p4a looks for main.py by default — mirror launcher
    main_py = ROOT / "main.py"
    if not main_py.is_file() or "REMEDYPDF_MOBILE" not in main_py.read_text(
        encoding="utf-8", errors="ignore"
    ):
        main_py.write_text(
            "#!/usr/bin/env python3\n"
            '"""p4a entry — delegates to main_android."""\n'
            "from main_android import main\n"
            "if __name__ == '__main__':\n"
            "    raise SystemExit(main())\n",
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
    for name in ("LICENSE", "README.md", "CHANGELOG.md", "buildozer.spec"):
        src = ROOT / name
        if src.is_file():
            shutil.copy2(src, stage / name)
    _write_android_main()
    shutil.copy2(ROOT / "main_android.py", stage / "main_android.py")
    if (ROOT / "main.py").is_file():
        shutil.copy2(ROOT / "main.py", stage / "main.py")
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


def _run_buildozer(timeout: int = 9000) -> int:
    """Run buildozer android debug; return exit code."""
    cmd = ["buildozer", "-v", "android", "debug"]
    print("+", " ".join(cmd))
    try:
        result = subprocess.run(
            cmd,
            cwd=str(ROOT),
            text=True,
            timeout=timeout,
        )
        return int(result.returncode)
    except subprocess.TimeoutExpired:
        print("ERROR: buildozer timed out", file=sys.stderr)
        return 124
    except FileNotFoundError:
        print("ERROR: buildozer not found on PATH", file=sys.stderr)
        return 127


def build_android_apk(*, zip_only: bool = False, prefer_apk: bool = False) -> int:
    """Build Android APK via Buildozer when present; always stage + zip."""
    ver = _version()
    print(f"RemedyPDF — Android package v{ver}")
    print(f"  source: {SRC}")
    print("  mobile: hold-to-edit, 44px targets, book both-sides, zoom reset")
    print(f"  flags: zip_only={zip_only} prefer_apk={prefer_apk}")

    if not SRC.is_dir():
        print("ERROR: src/ missing", file=sys.stderr)
        return 1

    os.environ.setdefault("REMEDYPDF_MOBILE", "1")
    DIST.mkdir(parents=True, exist_ok=True)
    write_buildozer_spec(ver)
    _write_android_main()
    package_android_zip(ver)

    if zip_only:
        print("zip-only: skipping Buildozer APK attempt")
        return 0

    has_bz = _has_buildozer()
    has_sdk = _has_android_sdk()
    print(f"  buildozer={has_bz} android_sdk={has_sdk}")

    if prefer_apk or (has_bz and has_sdk):
        if not has_bz:
            print("prefer-apk requested but buildozer missing — zip only")
            return 0
        if not has_sdk:
            print("prefer-apk requested but ANDROID_HOME/SDK missing — zip only")
            return 0
        print("  toolchain: buildozer + Android SDK detected — building APK")
        code = _run_buildozer()
        if code != 0:
            print(f"ERROR: Buildozer failed with exit code {code}", file=sys.stderr)
            print("src zip still published for sideload builds.")
            return code  # let CI see the failure; src zip was already published
        apk = _collect_apk(ver)
        if apk is None:
            print("WARN: Buildozer exited 0 but no APK found")
        return 0

    if has_bz and not has_sdk:
        print("Buildozer found but ANDROID_HOME / SDK missing.")
        print("  Set ANDROID_SDK_ROOT and re-run for a real APK.")
    else:
        print("Buildozer not on PATH — emitted android-src zip + buildozer.spec.")
        print("  Install: pip install buildozer cython")
        print("  Then:    buildozer android debug")

    print("Mobile UI path is wired in src/utils/mobile.py + PDFCanvas hold-to-edit.")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="RemedyPDF Android packager")
    p.add_argument(
        "--zip-only",
        action="store_true",
        help="Only emit android-src.zip (no Buildozer)",
    )
    p.add_argument(
        "--prefer-apk",
        action="store_true",
        help="Attempt Buildozer APK when SDK is present",
    )
    args = p.parse_args(argv)
    return build_android_apk(zip_only=args.zip_only, prefer_apk=args.prefer_apk)


if __name__ == "__main__":
    raise SystemExit(main())
