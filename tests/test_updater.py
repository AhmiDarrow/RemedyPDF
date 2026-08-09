from utils.updater import (
    check_for_update,
    compare_versions,
    fetch_latest_json,
    format_update_message,
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
