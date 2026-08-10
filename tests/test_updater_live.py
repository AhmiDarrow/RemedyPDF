"""Opt-in LIVE probe of the real RemedyPDF auto-update chain against GitHub.

These tests hit the network and the real releases of AhmiDarrow/RemedyPDF.
They are skipped unless REMEDYPDF_LIVE=1 — CI stays hermetic; run locally
after each release to prove: latest.json channel -> update detection ->
installer URL resolution -> real installer download (MZ header).

Run:  set REMEDYPDF_LIVE=1  (or $env:REMEDYPDF_LIVE=1)  then  pytest tests/test_updater_live.py -v
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

pytestmark = pytest.mark.skipif(
    os.environ.get("REMEDYPDF_LIVE") != "1",
    reason="live network probe — set REMEDYPDF_LIVE=1 to run",
)

from utils.updater import (  # noqa: E402
    check_for_update,
    download_update,
    fetch_latest_json,
    find_installer_url,
)


def test_live_latest_json_channel_resolves():
    lj = fetch_latest_json(timeout=15)
    assert lj is not None
    assert lj.get("version")
    assert isinstance(lj.get("platforms"), dict)


def test_live_update_offered_for_old_version():
    info = check_for_update(current_version="0.0.1", timeout=15)
    assert isinstance(info, dict)
    assert info.get("tag")
    assert info.get("source") == "latest.json"


def test_live_up_to_date_is_detected():
    lj = fetch_latest_json(timeout=15)
    assert lj is not None
    tag = str(lj.get("version") or "").lstrip("v")
    assert tag
    # At the latest published version (and any newer) → no update offered.
    assert check_for_update(current_version=tag, timeout=15) is None
    assert check_for_update(current_version="99.99.99", timeout=15) is None


def test_live_installer_url_and_download():
    info = check_for_update(current_version="0.0.1", timeout=15)
    url = find_installer_url(info)
    assert url and url.startswith("https://") and url.lower().endswith(".exe")
    dest = os.path.join(tempfile.gettempdir(), "remedy_live_probe_setup.exe")
    try:
        download_update(url, dest, timeout=300)
        with open(dest, "rb") as fh:
            assert fh.read(2) == b"MZ"  # real PE executable, not an HTML stub
        assert os.path.getsize(dest) > 1_000_000
    finally:
        if os.path.exists(dest):
            os.remove(dest)
