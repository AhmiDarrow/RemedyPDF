"""Regression: installer must ship the onedir build (no onefile bootloader race).

v1.4.0 shipped a PyInstaller --onefile exe in the installer. On launch the
bootloader extracts ~2600 files to %TEMP%\\_MEIxxxxx and LoadLibrary's
python312.dll from there — racing AV scans and the old process being killed
during auto-update relaunch, producing:
  "Failed to load Python DLL 'python312.dll'. LoadLibrary: The specified
   module could not be found."
Fix: install --onedir (real DLLs beside the exe, no temp extraction).
These tests pin that shape so it cannot regress.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _build_script() -> str:
    return (ROOT / "build_windows.py").read_text(encoding="utf-8")


def _iss() -> str:
    return (ROOT / "installer" / "remedypdf.iss").read_text(encoding="utf-8")


def test_installer_build_uses_onedir():
    """The Inno installer must be fed a --onedir build, not --onefile."""
    src = _build_script()
    assert "--onedir" in src
    # The onefile build is only the portable asset
    assert "build_onefile()  # portable single-file asset" in src


def test_iss_installs_whole_app_folder():
    """Installer copies the whole onedir folder (exe + _internal DLLs)."""
    iss = _iss()
    assert 'Source: "{#DistDir}\\RemedyPDF\\*"' in iss
    assert "recursesubdirs" in iss
    assert "createallsubdirs" in iss


def test_no_single_exe_source_in_iss():
    """The old broken shape (one exe only, no DLLs) must be gone."""
    iss = _iss()
    assert 'Source: "{#DistDir}\\{#MyAppExeName}"' not in iss


def test_installer_version_fallback_synced():
    """The .iss fallback version must match src/__init__.py."""
    init = (ROOT / "src" / "__init__.py").read_text(encoding="utf-8")
    for line in init.splitlines():
        if line.startswith("__version__"):
            ver = line.split("=", 1)[1].strip().strip("\"'")
            break
    else:
        ver = ""
    assert f'#define MyAppVersion "{ver}"' in _iss()


def test_build_script_still_compiles():
    """The build script must stay importable/parseable."""
    import ast

    ast.parse(_build_script())
