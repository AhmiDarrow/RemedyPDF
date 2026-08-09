"""Build Windows onefile binary using PyInstaller (icon + resources wired)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def build_windows_installer() -> None:
    icon_ico = ROOT / "resources" / "icon.ico"
    icon_png = ROOT / "resources" / "icon.png"
    if not icon_ico.is_file() and not icon_png.is_file():
        print("ERROR: missing resources/icon.ico (and icon.png)", file=sys.stderr)
        sys.exit(2)

    icon_arg = str(icon_ico if icon_ico.is_file() else icon_png)
    sep = ";" if sys.platform == "win32" else ":"
    # Absolute source path — relative "resources" breaks when --specpath is build/
    resources_src = str((ROOT / "resources").resolve())
    print("Building Windows onefile (RemedyPDF)…")
    print(f"  icon: {icon_arg}")
    print(f"  resources: {resources_src}")
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name",
        "RemedyPDF",
        "--onefile",
        "--windowed",
        f"--add-data={resources_src}{sep}resources",
        "--paths",
        str(ROOT),
        "--hidden-import",
        "src",
        "--hidden-import",
        "src.core.app",
        "--hidden-import",
        "src.core.pdf_engine",
        "--hidden-import",
        "src.ui.about",
        "--hidden-import",
        "src.ui.theme",
        "--hidden-import",
        "src.ui.widgets",
        "--hidden-import",
        "src.utils.brand",
        "--hidden-import",
        "src.utils.updater",
        "--hidden-import",
        "src.utils.mobile",
        "--hidden-import",
        "src.utils.paths",
        "--collect-all",
        "PyQt5",
        "--collect-all",
        "fitz",
        "--icon",
        icon_arg,
        "--distpath",
        str(ROOT / "dist"),
        "--workpath",
        str(ROOT / "build" / "pyinstaller"),
        "--specpath",
        str(ROOT / "build"),
        str(ROOT / "src" / "main.py"),
    ]
    result = subprocess.run(cmd, cwd=str(ROOT))
    if result.returncode != 0:
        sys.exit(result.returncode)
    out = ROOT / "dist" / "RemedyPDF.exe"
    print(f"OK built: {out} exists={out.is_file()}")


if __name__ == "__main__":
    build_windows_installer()
