import os

from utils.updater import (
    check_for_update,
    compare_versions,
    download_update,
    fetch_latest_json,
    find_installer_url,
    format_update_message,
    install_update,
    launch_installer,
    update_status_message,
)


def test_compare_versions_basic():
    assert compare_versions("1.0.0", "1.0.0") == 0
    assert compare_versions("1.0.0", "1.0.1") == -1
    assert compare_versions("2.0.0", "1.9.9") == 1
    assert compare_versions("v1.2.0", "1.2.0") == 0


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
