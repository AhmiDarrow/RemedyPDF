"""Packaging / installer / release-channel contracts."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_inno_script_present():
    iss = ROOT / "installer" / "remedypdf.iss"
    assert iss.is_file()
    text = iss.read_text(encoding="utf-8")
    assert "RemedyPDF" in text
    assert "windows-setup" in text or "Setup" in text
    assert "icon.ico" in text or "SetupIconFile" in text


def test_build_windows_module_exports():
    sys.path.insert(0, str(ROOT))
    import build_windows as bw

    assert callable(bw.build_windows_installer) or callable(getattr(bw, "build_onefile", None))
    assert callable(bw._find_iscc) or callable(getattr(bw, "find_iscc", None))
    assert callable(bw._version)


def test_build_android_module_exports():
    sys.path.insert(0, str(ROOT))
    import build_android as ba

    assert callable(ba.build_android_apk)
    assert callable(ba.write_buildozer_spec)
    assert callable(ba.package_android_zip)
    assert callable(ba._version)


def test_write_latest_json_multi_platform(tmp_path: Path):
    out = tmp_path / "latest.json"
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "write_latest_json.py"),
        "--version",
        "1.3.0",
        "--tag",
        "v1.3.0",
        "--repo",
        "AhmiDarrow/RemedyPDF",
        "--out",
        str(out),
        "--setup-name",
        "RemedyPDF-1.3.0-windows-setup.exe",
        "--exe-name",
        "RemedyPDF-1.3.0-windows.exe",
        "--apk-name",
        "RemedyPDF-1.3.0-android.apk",
        "--android-zip-name",
        "RemedyPDF-1.3.0-android-src.zip",
    ]
    r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    assert r.returncode == 0, r.stderr + r.stdout
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["version"] == "1.3.0"
    assert data["tag_name"] == "v1.3.0"
    platforms = data["platforms"]
    assert "windows-x86_64" in platforms
    assert "android-arm64" in platforms
    assert platforms["windows-x86_64"]["url"].endswith(
        "RemedyPDF-1.3.0-windows-setup.exe"
    )
    assert platforms["android-arm64"]["url"].endswith(
        "RemedyPDF-1.3.0-android.apk"
    )


def test_version_is_semver():
    init = (ROOT / "src" / "__init__.py").read_text(encoding="utf-8")
    import re

    m = re.search(r'__version__\s*=\s*"(\d+\.\d+\.\d+)"', init)
    assert m, "version missing"
    assert m.group(1).startswith("1.")


def test_release_workflow_has_token_and_platforms():
    yml = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "secrets.GITHUB_TOKEN" in yml
    assert "GITHUB_[redacted]" not in yml
    assert "build-windows" in yml
    assert "build-android" in yml
    assert "windows-setup" in yml
    assert "android" in yml.lower()


def test_docs_install_mentions_both_platforms():
    install = (ROOT / "docs" / "INSTALL.md").read_text(encoding="utf-8")
    assert "Windows" in install
    assert "Android" in install or "APK" in install
