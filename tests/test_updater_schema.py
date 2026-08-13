"""Hermetic contract test: the release workflow's write_latest_json.py output
must be parseable by utils.updater.check_for_update, and the installer URL
it emits must be what find_installer_url selects. No network needed."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import write_latest_json  # noqa: E402  (workflow helper under scripts/)

from utils.updater import (  # noqa: E402
    check_for_update,
    fetch_latest_json,
    find_installer_sha256,
    find_installer_url,
)


@pytest.fixture
def latest_payload(tmp_path, monkeypatch):
    """Generate latest.json exactly like .github/workflows/release.yml does,
    then serve it through the updater's _get_json (first candidate URL)."""
    out = tmp_path / "latest.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "write_latest_json.py",
            "--version", "9.9.9",
            "--tag", "v9.9.9",
            "--repo", "AhmiDarrow/RemedyPDF",
            "--setup-name", "RemedyPDF-9.9.9-windows-setup.exe",
            "--exe-name", "RemedyPDF-9.9.9-windows.exe",
            "--android-zip-name", "RemedyPDF-9.9.9-android-src.zip",
            "--out", str(out),
        ],
    )
    assert write_latest_json.main() == 0
    payload = json.loads(out.read_text(encoding="utf-8"))

    class FakeResp:
        headers = {"Content-Length": str(len(json.dumps(payload)))}

        def read(self, _n=None):
            return json.dumps(payload).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("utils.updater.urlopen", lambda *a, **k: FakeResp())
    return payload


def test_latest_json_is_detected(latest_payload):
    lj = fetch_latest_json("AhmiDarrow", "RemedyPDF")
    assert lj is not None
    assert lj["version"] == "9.9.9"
    assert lj["tag_name"] == "v9.9.9"


def test_check_for_update_uses_latest_json_channel(latest_payload):
    info = check_for_update(current_version="1.0.0")
    assert info is not None
    assert info["tag"] == "9.9.9"
    assert info["source"] == "latest.json"
    assert "RemedyPDF" in info["name"]


def test_check_for_update_not_newer_returns_none(latest_payload):
    assert check_for_update(current_version="9.9.9") is None
    assert check_for_update(current_version="10.0.0") is None


def test_find_installer_url_prefers_latest_json_windows(latest_payload):
    info = check_for_update(current_version="1.0.0")
    url = find_installer_url(info)
    assert url == (
        "https://github.com/AhmiDarrow/RemedyPDF/releases/download/"
        "v9.9.9/RemedyPDF-9.9.9-windows-setup.exe"
    )


def test_write_latest_json_emits_sha256(tmp_path, monkeypatch):
    """Release helper must publish installer digest for client-side verify."""
    out = tmp_path / "latest.json"
    digest = "a" * 64
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "write_latest_json.py",
            "--version", "8.8.8",
            "--tag", "v8.8.8",
            "--repo", "AhmiDarrow/RemedyPDF",
            "--setup-name", "RemedyPDF-8.8.8-windows-setup.exe",
            "--exe-name", "RemedyPDF-8.8.8-windows.exe",
            "--setup-sha256", digest,
            "--out", str(out),
        ],
    )
    assert write_latest_json.main() == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["sha256"] == digest
    assert payload["installer_sha256"] == digest
    win = payload["platforms"]["windows-x86_64"]
    assert win["sha256"] == digest
    assert win["signature"] == digest

    class FakeResp:
        def read(self, _n=None):
            return json.dumps(payload).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("utils.updater.urlopen", lambda *a, **k: FakeResp())
    info = check_for_update(current_version="1.0.0")
    assert info is not None
    assert find_installer_sha256(info) == digest


def test_platform_android_src_zip_fallback_present(latest_payload):
    """Mirror release.yml's post-rewrite: when no APK exists, the workflow
    repoints android-arm64 at the src zip so autoupdate is never a 404."""
    data = latest_payload
    assert data["platforms"]["android-arm64"]["kind"] == "apk"  # script default
    assert data["platforms"]["android-arm64"]["url"].endswith(".apk")

    # Same rewrite the workflow's inline python applies (release.yml)
    plat = data.setdefault("platforms", {}).setdefault("android-arm64", {})
    z = "RemedyPDF-9.9.9-android-src.zip"
    tag = data.get("tag_name") or ""
    base = f"https://github.com/AhmiDarrow/RemedyPDF/releases/download/{tag}"
    plat["url"] = f"{base}/{z}"
    plat["src_zip_url"] = f"{base}/{z}"
    plat["kind"] = "android-src-zip"
    data.setdefault("assets", {})["android_apk"] = ""
    data["assets"]["android_src_zip"] = z

    assert plat["kind"] == "android-src-zip"
    assert plat["url"].endswith("RemedyPDF-9.9.9-android-src.zip")
    # Updater must still parse the rewritten payload and resolve the Windows installer
    info = check_for_update(current_version="1.0.0")
    assert info is not None
    assert info["source"] == "latest.json"
    assert find_installer_url(info).endswith("RemedyPDF-9.9.9-windows-setup.exe")
