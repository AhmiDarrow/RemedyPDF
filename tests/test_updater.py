import hashlib
import os

import pytest

from utils.updater import (
    UpdateCancelled,
    check_for_update,
    compare_versions,
    download_update,
    fetch_latest_json,
    file_sha256,
    find_installer_sha256,
    find_installer_url,
    format_update_message,
    install_update,
    launch_installer,
    normalize_sha256,
    update_status_message,
    verify_file_sha256,
)


def test_compare_versions_basic():
    assert compare_versions("1.0.0", "1.0.0") == 0
    assert compare_versions("1.0.0", "1.0.1") == -1
    assert compare_versions("2.0.0", "1.9.9") == 1
    assert compare_versions("v1.2.0", "1.2.0") == 0


def test_compare_versions_prerelease_ordering():
    """Semver: alpha < beta < rc < release; numbered pre ids ordered."""
    assert compare_versions("1.0.0-alpha", "1.0.0-alpha.1") == -1
    assert compare_versions("1.0.0-alpha.1", "1.0.0-beta") == -1
    assert compare_versions("1.0.0-beta", "1.0.0-beta.2") == -1
    assert compare_versions("1.0.0-beta.2", "1.0.0-rc.1") == -1
    assert compare_versions("1.0.0-rc.1", "1.0.0") == -1
    assert compare_versions("1.0.0", "1.0.0-beta") == 1
    assert compare_versions("1.4.2-beta.1", "1.4.2-beta.2") == -1
    assert compare_versions("1.4.2-beta.2", "1.4.2") == -1
    # Build metadata ignored
    assert compare_versions("1.0.0+build.1", "1.0.0") == 0


def test_check_for_update_handles_network_errors(monkeypatch):
    def boom(*_a, **_k):
        raise TimeoutError("offline")

    monkeypatch.setattr("utils.updater.urlopen", boom)
    assert check_for_update(timeout=0.1) is None


def test_check_for_update_same_version(monkeypatch):
    class FakeResp:
        def read(self):
            return b'{"tag_name":"v1.2.0","name":"1.2.0","html_url":"https://example.com","body":""}'

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("utils.updater.urlopen", lambda *a, **k: FakeResp())
    assert check_for_update(current_version="1.2.0") is None


def test_check_for_update_newer(monkeypatch):
    class FakeResp:
        def read(self):
            return (
                b'{"tag_name":"v2.0.0","name":"2.0.0",'
                b'"html_url":"https://example.com/r","body":"notes"}'
            )

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("utils.updater.urlopen", lambda *a, **k: FakeResp())
    info = check_for_update(current_version="1.2.0")
    assert info is not None
    assert info["tag"] == "2.0.0"
    assert "example.com" in info["url"]


def test_fetch_latest_json(monkeypatch):
    class FakeResp:
        def read(self):
            return b'{"version":"9.9.9","notes":"hi","platforms":{}}'

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("utils.updater.urlopen", lambda *a, **k: FakeResp())
    data = fetch_latest_json("AhmiDarrow", "RemedyPDF")
    assert data is not None
    assert data["version"] == "9.9.9"


def test_format_update_message():
    assert "up to date" in format_update_message(None, "1.2.0").lower() or "1.2.0" in format_update_message(
        None, "1.2.0"
    )
    msg = format_update_message({"tag": "2.0.0", "url": "https://x"}, "1.0.0")
    assert "2.0.0" in msg
    assert update_status_message({"tag": "2.0.0"}, "1.0.0")
    assert update_status_message(None, "1.0.0")


def test_find_installer_url_prefers_latest_json_platform():
    info = {
        "platforms": {
            "windows-x86_64": {
                "url": "https://github.com/AhmiDarrow/RemedyPDF/releases/download/v2.0.0/RemedyPDF-2.0.0-windows-setup.exe"
            }
        }
    }
    assert find_installer_url(info) == (
        "https://github.com/AhmiDarrow/RemedyPDF/releases/download/v2.0.0/"
        "RemedyPDF-2.0.0-windows-setup.exe"
    )


def test_check_for_update_keeps_release_page_url(monkeypatch):
    """Open release must not point at the raw installer .exe asset."""
    payload = {
        "version": "9.0.0",
        "html_url": "https://github.com/AhmiDarrow/RemedyPDF/releases/tag/v9.0.0",
        "url": "https://github.com/AhmiDarrow/RemedyPDF/releases/tag/v9.0.0",
        "notes": "hi",
        "platforms": {
            "windows-x86_64": {
                "url": (
                    "https://github.com/AhmiDarrow/RemedyPDF/releases/download/"
                    "v9.0.0/RemedyPDF-9.0.0-windows-setup.exe"
                )
            }
        },
    }

    class FakeResp:
        def read(self, _n=None):
            import json

            return json.dumps(payload).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("utils.updater.urlopen", lambda *a, **k: FakeResp())
    info = check_for_update(current_version="1.0.0")
    assert info is not None
    assert info["url"].endswith("/releases/tag/v9.0.0")
    assert not str(info["url"]).lower().endswith(".exe")
    assert find_installer_url(info).endswith("windows-setup.exe")


def test_find_installer_url_api_assets():
    info = {
        "assets": [
            {"name": "RemedyPDF-2.0.0-windows.exe", "browser_download_url": "https://x/portable.exe"},
            {
                "name": "RemedyPDF-2.0.0-windows-setup.exe",
                "browser_download_url": "https://x/setup.exe",
            },
            {"name": "RemedyPDF-2.0.0-android-src.zip", "browser_download_url": "https://x/src.zip"},
        ]
    }
    assert find_installer_url(info) == "https://x/setup.exe"


def test_find_installer_url_none():
    assert find_installer_url(None) is None
    assert find_installer_url({}) is None
    assert find_installer_url({"tag": "1.0.0", "url": "https://github.com/x"}) is None


def test_download_update_streams(monkeypatch, tmp_path):
    class FakeResp:
        headers = {"Content-Length": "6"}

        def read(self, _n):
            if not hasattr(self, "_sent"):
                self._sent = True
                return b"abcdef"
            return b""

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("utils.updater.urlopen", lambda *a, **k: FakeResp())
    dest = str(tmp_path / "update.exe")
    out = download_update("https://x/setup.exe", dest)
    assert out == dest
    with open(dest, "rb") as fh:
        assert fh.read() == b"abcdef"


def test_download_update_empty_raises(monkeypatch, tmp_path):
    class FakeResp:
        headers = {"Content-Length": "0"}

        def read(self, _n):
            return b""

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("utils.updater.urlopen", lambda *a, **k: FakeResp())
    try:
        download_update("https://x/setup.exe", str(tmp_path / "u.exe"))
        raise AssertionError("expected OSError")
    except OSError:
        pass


def test_launch_installer_missing_path():
    assert launch_installer("C:/definitely/missing/setup.exe") is False


def test_launch_installer_silent_flags(monkeypatch, tmp_path):
    """Silent install must force per-user (/CURRENTUSER) so it never stalls on UAC."""
    import utils.updater as upd

    exe = tmp_path / "setup.exe"
    exe.write_bytes(b"MZ")

    captured = {}

    class FakePopen:
        def __init__(self, cmd, **kwargs):
            captured["cmd"] = cmd
            captured["kwargs"] = kwargs

    monkeypatch.setattr(upd.subprocess, "Popen", FakePopen)
    assert launch_installer(str(exe)) is True
    assert captured["cmd"][0] == str(exe)
    joined = " ".join(captured["cmd"])
    assert "/VERYSILENT" in joined
    assert "/SUPPRESSMSGBOXES" in joined
    assert "/CURRENTUSER" in joined
    assert captured["kwargs"].get("shell") is False


def test_install_update_spawns(monkeypatch, tmp_path):
    import utils.updater as upd

    class FakeResp:
        headers = {"Content-Length": "4"}

        def read(self, _n):
            if not hasattr(self, "_sent"):
                self._sent = True
                return b"MZ\x90\x00"
            return b""

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(upd, "urlopen", lambda *a, **k: FakeResp())
    monkeypatch.setattr(upd, "launch_installer", lambda p: True)
    info = {
        "tag": "2.0.0",
        "platforms": {
            "windows-x86_64": {"url": "https://x/RemedyPDF-2.0.0-windows-setup.exe"}
        },
    }
    dest = str(tmp_path / "installs")
    out = install_update(info, dest_dir=dest)
    assert out is not None
    assert os.path.exists(out)
    assert "2.0.0" in out
    with open(out, "rb") as fh:
        assert fh.read() == b"MZ\x90\x00"


def test_install_update_no_installer_url(tmp_path):
    assert install_update({"tag": "2.0.0", "url": "https://github.com/x"}, dest_dir=str(tmp_path)) is None


def test_normalize_and_find_sha256():
    assert normalize_sha256("SHA256:" + "a" * 64) == "a" * 64
    assert normalize_sha256("not-a-hash") == ""
    info = {
        "platforms": {
            "windows-x86_64": {
                "url": "https://x/setup.exe",
                "sha256": "b" * 64,
            }
        }
    }
    assert find_installer_sha256(info) == "b" * 64
    api = {
        "assets": [
            {
                "name": "RemedyPDF-setup.exe",
                "browser_download_url": "https://x/setup.exe",
                "digest": "sha256:" + "c" * 64,
            }
        ],
        "url": "https://x/setup.exe",
    }
    # find_installer_url picks setup; digest should resolve
    assert find_installer_url(api) == "https://x/setup.exe"
    assert find_installer_sha256(api) == "c" * 64


def test_file_sha256_and_verify(tmp_path):
    p = tmp_path / "blob.bin"
    data = b"hello-remedy-update"
    p.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    assert file_sha256(str(p)) == digest
    verify_file_sha256(str(p), digest)
    try:
        verify_file_sha256(str(p), "d" * 64)
        raise AssertionError("expected mismatch OSError")
    except OSError as exc:
        assert "mismatch" in str(exc).lower()


def test_download_update_verifies_sha256(monkeypatch, tmp_path):
    payload = b"abcdef"
    digest = hashlib.sha256(payload).hexdigest()

    class FakeResp:
        headers = {"Content-Length": str(len(payload))}

        def read(self, _n):
            if not hasattr(self, "_sent"):
                self._sent = True
                return payload
            return b""

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("utils.updater.urlopen", lambda *a, **k: FakeResp())
    dest = str(tmp_path / "ok.exe")
    out = download_update("https://x/setup.exe", dest, expected_sha256=digest)
    assert out == dest
    assert os.path.isfile(dest)

    dest_bad = str(tmp_path / "bad.exe")
    try:
        download_update("https://x/setup.exe", dest_bad, expected_sha256="e" * 64)
        raise AssertionError("expected OSError on hash mismatch")
    except OSError:
        pass
    assert not os.path.exists(dest_bad)


def test_download_update_cancel(monkeypatch, tmp_path):
    class FakeResp:
        headers = {"Content-Length": "100"}

        def read(self, _n):
            return b"x" * 10

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("utils.updater.urlopen", lambda *a, **k: FakeResp())
    dest = str(tmp_path / "partial.exe")
    calls = {"n": 0}

    def cancel_after_progress():
        calls["n"] += 1
        return calls["n"] > 2

    with pytest.raises(UpdateCancelled):
        download_update(
            "https://x/setup.exe",
            dest,
            cancel_check=cancel_after_progress,
        )
    assert not os.path.exists(dest)


def test_install_update_cancel(monkeypatch, tmp_path):
    import utils.updater as upd

    class FakeResp:
        headers = {"Content-Length": "50"}

        def read(self, _n):
            return b"MZ" + b"\x00" * 8

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(upd, "urlopen", lambda *a, **k: FakeResp())
    launched = {"n": 0}
    monkeypatch.setattr(upd, "launch_installer", lambda p: launched.__setitem__("n", 1) or True)

    info = {
        "tag": "3.0.0",
        "platforms": {
            "windows-x86_64": {"url": "https://x/RemedyPDF-3.0.0-windows-setup.exe"}
        },
    }
    n = {"i": 0}

    def cancel_soon():
        n["i"] += 1
        return n["i"] > 1

    with pytest.raises(UpdateCancelled):
        install_update(info, dest_dir=str(tmp_path), cancel_check=cancel_soon)
    assert launched["n"] == 0


def test_install_update_hash_mismatch(monkeypatch, tmp_path):
    import utils.updater as upd

    payload = b"MZ\x90\x00"

    class FakeResp:
        headers = {"Content-Length": str(len(payload))}

        def read(self, _n):
            if not hasattr(self, "_sent"):
                self._sent = True
                return payload
            return b""

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(upd, "urlopen", lambda *a, **k: FakeResp())
    monkeypatch.setattr(upd, "launch_installer", lambda p: True)
    info = {
        "tag": "3.1.0",
        "platforms": {
            "windows-x86_64": {
                "url": "https://x/RemedyPDF-3.1.0-windows-setup.exe",
                "sha256": "f" * 64,
            }
        },
    }
    # install_update surfaces hash mismatch as OSError (UI shows real reason)
    with pytest.raises(OSError, match="[Mm]ismatch|[Ss]HA"):
        install_update(info, dest_dir=str(tmp_path))
    leftovers = list(tmp_path.glob("*.exe"))
    assert leftovers == []


def test_install_update_require_sha256_missing(tmp_path):
    info = {
        "tag": "3.2.0",
        "platforms": {
            "windows-x86_64": {"url": "https://x/RemedyPDF-3.2.0-windows-setup.exe"}
        },
    }
    with pytest.raises(OSError, match="SHA-256"):
        install_update(info, dest_dir=str(tmp_path), require_sha256=True)


def test_install_update_with_matching_sha(monkeypatch, tmp_path):
    import utils.updater as upd

    payload = b"MZ\x90\x00good"
    digest = hashlib.sha256(payload).hexdigest()

    class FakeResp:
        headers = {"Content-Length": str(len(payload))}

        def read(self, _n):
            if not hasattr(self, "_sent"):
                self._sent = True
                return payload
            return b""

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(upd, "urlopen", lambda *a, **k: FakeResp())
    monkeypatch.setattr(upd, "launch_installer", lambda p: True)
    info = {
        "tag": "3.3.0",
        "platforms": {
            "windows-x86_64": {
                "url": "https://x/RemedyPDF-3.3.0-windows-setup.exe",
                "sha256": digest,
            }
        },
    }
    out = install_update(info, dest_dir=str(tmp_path))
    assert out is not None
    assert file_sha256(out) == digest
