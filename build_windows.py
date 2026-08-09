"""Build Windows onefile binary + Inno Setup installer for RemedyPDF."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
TOOLS = ROOT / "tools"
INNO_DIR = TOOLS / "InnoSetup"


def _version() -> str:
    init = (ROOT / "src" / "__init__.py").read_text(encoding="utf-8")
    for line in init.splitlines():
        if line.startswith("__version__"):
            return line.split("=", 1)[1].strip().strip("\"'")
    return "0.0.0"


def _find_iscc() -> Path | None:
    cands = [
        INNO_DIR / "ISCC.exe",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
        / "Inno Setup 6"
        / "ISCC.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        / "Inno Setup 6"
        / "ISCC.exe",
        Path(os.environ.get("LOCALAPPDATA", ""))
        / "Programs"
        / "Inno Setup 6"
        / "ISCC.exe",
    ]
    for c in cands:
        if c and c.is_file():
            return c
    which = shutil.which("ISCC") or shutil.which("iscc")
    return Path(which) if which else None


def _ensure_inno() -> Path | None:
    """Return ISCC path; download portable Inno Setup into tools/ if missing."""
    found = _find_iscc()
    if found:
        return found

    print("ISCC not found — downloading Inno Setup 6 into tools/InnoSetup …")
    TOOLS.mkdir(parents=True, exist_ok=True)
    setup = TOOLS / "innosetup-setup.exe"
    url = "https://github.com/jrsoftware/issrc/releases/download/is-6_7_3/innosetup-6.7.3.exe"
    try:
        urllib.request.urlretrieve(url, setup)  # noqa: S310 — fixed release URL
        if setup.stat().st_size < 1_000_000:
            print("ERROR: Inno download too small (HTML stub?)", file=sys.stderr)
            return None
        dest = str(INNO_DIR)
        cmd = [
            str(setup),
            "/VERYSILENT",
            "/SUPPRESSMSGBOXES",
            "/NORESTART",
            f"/DIR={dest}",
        ]
        subprocess.run(cmd, check=False)
        return _find_iscc()
    except Exception as exc:  # noqa: BLE001
        print(f"Inno download/install failed: {exc}", file=sys.stderr)
        return None


def build_onefile() -> Path:
    icon_ico = ROOT / "resources" / "icon.ico"
    icon_png = ROOT / "resources" / "icon.png"
    if not icon_ico.is_file() and not icon_png.is_file():
        print("ERROR: missing resources/icon.ico (and icon.png)", file=sys.stderr)
        sys.exit(2)

    icon_arg = str(icon_ico if icon_ico.is_file() else icon_png)
    sep = ";" if sys.platform == "win32" else ":"
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
        str(DIST),
        "--workpath",
        str(ROOT / "build" / "pyinstaller"),
        "--specpath",
        str(ROOT / "build"),
        str(ROOT / "src" / "main.py"),
    ]
    result = subprocess.run(cmd, cwd=str(ROOT))
    if result.returncode != 0:
        sys.exit(result.returncode)
    out = DIST / "RemedyPDF.exe"
    if not out.is_file():
        print(f"ERROR: missing {out}", file=sys.stderr)
        sys.exit(1)
    print(f"OK onefile: {out} ({out.stat().st_size} bytes)")
    return out


def build_inno_installer(version: str | None = None) -> Path | None:
    """Compile installer/remedypdf.iss → dist/RemedyPDF-{ver}-windows-setup.exe."""
    ver = version or _version()
    exe = DIST / "RemedyPDF.exe"
    if not exe.is_file():
        print("ERROR: build onefile first (dist/RemedyPDF.exe missing)", file=sys.stderr)
        return None

    iscc = _ensure_inno()
    if not iscc:
        print("WARN: ISCC unavailable — skipping Setup.exe (onefile still OK)")
        return None

    iss = ROOT / "installer" / "remedypdf.iss"
    if not iss.is_file():
        print(f"ERROR: missing {iss}", file=sys.stderr)
        return None

    DIST.mkdir(parents=True, exist_ok=True)
    print(f"Building Inno Setup installer with {iscc} …")
    cmd = [
        str(iscc),
        f"/DMyAppVersion={ver}",
        f"/DDistDir={DIST}",
        str(iss),
    ]
    result = subprocess.run(cmd, cwd=str(ROOT))
    if result.returncode != 0:
        print(f"ERROR: ISCC failed ({result.returncode})", file=sys.stderr)
        return None

    setup = DIST / f"RemedyPDF-{ver}-windows-setup.exe"
    # Inno may write with different casing; glob fallback
    if not setup.is_file():
        matches = list(DIST.glob("RemedyPDF-*-windows-setup.exe"))
        if matches:
            setup = matches[0]
    if setup.is_file():
        print(f"OK installer: {setup} ({setup.stat().st_size} bytes)")
        return setup
    print("ERROR: Setup.exe not found after ISCC", file=sys.stderr)
    return None


def build_windows_installer() -> None:
    ver = _version()
    print(f"=== RemedyPDF Windows build v{ver} ===")
    build_onefile()
    setup = build_inno_installer(ver)
    # Versioned onefile copy for release channel
    versioned = DIST / f"RemedyPDF-{ver}-windows.exe"
    src = DIST / "RemedyPDF.exe"
    if src.is_file():
        shutil.copy2(src, versioned)
        print(f"OK versioned exe: {versioned}")
    print("Artifacts:")
    for p in sorted(DIST.glob("RemedyPDF*")):
        if p.is_file():
            print(f"  {p.name}  ({p.stat().st_size} bytes)")
    if setup is None:
        print("NOTE: installer missing — install Inno Setup 6 or re-run on CI.")


if __name__ == "__main__":
    build_windows_installer()
