"""GitHub Releases auto-update helpers (SecretSticky-style channel)."""

from __future__ import annotations

import json
import re
import webbrowser
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    from src import GITHUB_OWNER, GITHUB_RELEASES_URL, GITHUB_REPO, __version__
except ImportError:
    try:
        from __init__ import (  # type: ignore
            GITHUB_OWNER,
            GITHUB_RELEASES_URL,
            GITHUB_REPO,
            __version__,
        )
    except ImportError:
        GITHUB_OWNER = "AhmiDarrow"
        GITHUB_REPO = "RemedyPDF"
        GITHUB_RELEASES_URL = "https://github.com/AhmiDarrow/RemedyPDF/releases"
        __version__ = "1.2.0"

_UA = f"RemedyPDF/{__version__} (+https://github.com/{GITHUB_OWNER}/{GITHUB_REPO})"


def _parse_version(text: str) -> tuple[int, ...]:
    """Best-effort semver tuple from tag like v1.2.0 or 1.2.0-beta.1."""
    s = (text or "").strip().lstrip("vV")
    if not s:
        return (0,)
    # drop pre-release / build metadata for numeric compare
    s = s.split("+", 1)[0]
    core, _, pre = s.partition("-")
    parts: list[int] = []
    for bit in core.split("."):
        m = re.match(r"(\d+)", bit)
        parts.append(int(m.group(1)) if m else 0)
    while len(parts) < 3:
        parts.append(0)
    # pre-release is older than final of same core
    if pre:
        return tuple(parts[:3] + [0])
    return tuple(parts[:3] + [1])


def compare_versions(a: str, b: str) -> int:
    """Return -1 if a<b, 0 if equal, 1 if a>b."""
    ta, tb = _parse_version(a), _parse_version(b)
    if ta < tb:
        return -1
    if ta > tb:
        return 1
    return 0


def open_url(url: str) -> bool:
    """Open http(s) URL in the default browser."""
    u = (url or "").strip()
    if not (u.startswith("https://") or u.startswith("http://")):
        return False
    try:
        from PyQt5.QtCore import QUrl
        from PyQt5.QtGui import QDesktopServices

        if QDesktopServices.openUrl(QUrl(u)):
            return True
    except Exception:  # noqa: BLE001
        pass
    try:
        return bool(webbrowser.open(u))
    except Exception:  # noqa: BLE001
        return False


def _get_json(url: str, timeout: float = 5.0) -> Optional[dict[str, Any]]:
    req = Request(url, headers={"User-Agent": _UA, "Accept": "application/vnd.github+json"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except (URLError, HTTPError, TimeoutError, json.JSONDecodeError, ValueError, OSError):
        return None


def fetch_latest_json(
    owner: str = GITHUB_OWNER,
    repo: str = GITHUB_REPO,
    timeout: float = 5.0,
) -> Optional[dict[str, Any]]:
    """Fetch Tauri-style latest.json from GitHub Releases if present."""
    # Common patterns used by Tauri updater / our release workflow
    candidates = [
        f"https://github.com/{owner}/{repo}/releases/latest/download/latest.json",
        f"https://github.com/{owner}/{repo}/releases/download/latest/latest.json",
    ]
    for url in candidates:
        data = _get_json(url, timeout=timeout)
        if data:
            return data
    return None


def check_for_update(
    owner: str = GITHUB_OWNER,
    repo: str = GITHUB_REPO,
    current_version: str = __version__,
    timeout: float = 5.0,
) -> Optional[dict[str, Any]]:
    """Return latest release info if newer than current_version, else None.

    Prefers latest.json (autoupdate channel), falls back to GitHub API.
    Network failures return None (never raises to UI callers).
    """
    # 1) latest.json channel (mirrors SecretSticky / Tauri updater)
    latest = fetch_latest_json(owner=owner, repo=repo, timeout=timeout)
    if latest:
        tag = str(latest.get("version") or latest.get("tag_name") or "").lstrip("v")
        notes = str(latest.get("notes") or latest.get("body") or "")
        url = str(
            latest.get("url")
            or latest.get("html_url")
            or f"https://github.com/{owner}/{repo}/releases"
        )
        platforms = latest.get("platforms") if isinstance(latest.get("platforms"), dict) else {}
        if tag and compare_versions(tag, current_version) > 0:
            return {
                "tag": tag,
                "name": latest.get("name") or tag,
                "url": url,
                "body": notes,
                "platforms": platforms,
                "source": "latest.json",
            }

    # 2) GitHub Releases API
    api = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    data = _get_json(api, timeout=timeout)
    if not data:
        return None

    tag = str(data.get("tag_name") or "").lstrip("v")
    if not tag:
        return None
    if compare_versions(tag, current_version) <= 0:
        return None
    return {
        "tag": tag,
        "name": data.get("name") or tag,
        "url": data.get("html_url") or f"https://github.com/{owner}/{repo}/releases/tag/v{tag}",
        "body": data.get("body") or "",
        "assets": data.get("assets") or [],
        "source": "github-api",
    }


def format_update_message(info: Optional[dict[str, Any]], current_version: str) -> str:
    """Human-readable status line for About / message boxes."""
    if info is None:
        return f"You're on the latest version ({current_version})."
    tag = str(info.get("tag") or "?")
    url = str(info.get("url") or GITHUB_RELEASES_URL)
    name = str(info.get("name") or tag)
    return (
        f"Update available: v{tag} (you have {current_version}).\n"
        f"{name}\n"
        f"{url}"
    )


def update_status_message(info: Optional[dict[str, Any]], current_version: str) -> str:
    """Alias used by About dialog (SecretSticky wording)."""
    if info is None:
        return f"You're on the latest version ({current_version})."
    tag = str(info.get("tag") or "?")
    return f"Update {tag} is available — open Releases to install."


__all__ = [
    "check_for_update",
    "compare_versions",
    "fetch_latest_json",
    "format_update_message",
    "update_status_message",
    "open_url",
]
