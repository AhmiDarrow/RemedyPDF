"""GitHub Releases auto-update helpers (SecretSticky-style channel)."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import webbrowser
from pathlib import Path
from typing import Any, Callable, Optional
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
        __version__ = "1.3.7"

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
            # Prefer Windows installer URL from platforms when present
            win = platforms.get("windows-x86_64") if isinstance(platforms, dict) else None
            if isinstance(win, dict) and win.get("url"):
                url = str(win.get("url") or url)
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


def find_installer_url(info: Optional[dict[str, Any]]) -> Optional[str]:
    """Best Windows installer download URL from update info (or None).

    Priority: latest.json platforms.windows-x86_64.url → GitHub API assets
    (setup, then portable exe) → generic https .exe url.
    """
    if not info:
        return None
    platforms = info.get("platforms") if isinstance(info.get("platforms"), dict) else {}
    win = platforms.get("windows-x86_64")
    if isinstance(win, dict):
        u = str(win.get("url") or "").strip()
        if u.startswith("https://") and u.lower().endswith(".exe"):
            return u
    assets = info.get("assets") or []

    def _url_for(needle: str) -> str:
        for a in assets:
            if not isinstance(a, dict):
                continue
            name = str(a.get("name") or "").lower()
            url = str(a.get("browser_download_url") or "")
            if needle in name and url.startswith("https://"):
                return url
        return ""

    for needle in ("-setup", "setup", "-windows", ".exe"):
        u = _url_for(needle)
        if u:
            return u
    u = str(info.get("url") or "").strip()
    if u.startswith("https://") and u.lower().endswith(".exe"):
        return u
    return None


def download_update(
    url: str,
    dest: str,
    timeout: float = 180.0,
    progress: Optional[Callable[[int, int], None]] = None,
) -> str:
    """Stream-download url to dest (bytes). progress(done, total) optional.

    Raises on network failure or empty payload. Returns dest on success.
    """
    req = Request(url, headers={"User-Agent": _UA})
    total = 0
    done = 0
    with urlopen(req, timeout=timeout) as resp:
        try:
            total = int(resp.headers.get("Content-Length") or 0)
        except (ValueError, AttributeError):
            total = 0
        with open(dest, "wb") as fh:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                fh.write(chunk)
                done += len(chunk)
                if progress:
                    try:
                        progress(done, total)
                    except Exception:  # noqa: BLE001
                        pass
    if done <= 0:
        raise OSError("Empty download payload")
    return dest


def launch_installer(path: str) -> bool:
    """Silently run the Inno Setup installer, detached. Returns True if spawned."""
    p = Path(path)
    if not p.exists():
        return False
    # /CURRENTUSER keeps the silent update per-user (PrivilegesRequired=lowest)
    # so it never tries to elevate and stall waiting on a UAC prompt mid-silent-run.
    flags = ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-", "/CURRENTUSER"]
    try:
        if os.name == "nt":
            creationflags = 0
            for flag in ("CREATE_NEW_PROCESS_GROUP", "DETACHED_PROCESS"):
                creationflags |= getattr(subprocess, flag, 0)
            subprocess.Popen(
                [str(p), *flags],
                cwd=str(p.parent),
                creationflags=creationflags,
                close_fds=True,
                shell=False,
            )
        else:
            subprocess.Popen([str(p), *flags], cwd=str(p.parent), start_new_session=True)
        return True
    except Exception:  # noqa: BLE001
        return False


def install_update(
    info: Optional[dict[str, Any]],
    dest_dir: Optional[str] = None,
    progress: Optional[Callable[[int, int], None]] = None,
) -> Optional[str]:
    """Download the installer for update info and launch it silently.

    Returns the installer path when spawned, or None (missing installer URL,
    download failure, or launch failure). Never raises.
    """
    url = find_installer_url(info)
    if not url:
        return None
    dest_dir = dest_dir or tempfile.gettempdir()
    try:
        os.makedirs(dest_dir, exist_ok=True)
    except OSError:  # noqa: BLE001
        return None
    tag = str(info.get("tag") or "update")
    dest = os.path.join(dest_dir, f"RemedyPDF-{tag}-setup.exe")
    try:
        download_update(url, dest, progress=progress)
    except Exception:  # noqa: BLE001
        try:
            if os.path.exists(dest):
                os.remove(dest)
        except Exception:  # noqa: BLE001
            pass
        return None
    if not launch_installer(dest):
        return None
    return dest


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
    return f"Update {tag} is available — use Help → Check for Updates to download and install."


__all__ = [
    "check_for_update",
    "compare_versions",
    "download_update",
    "fetch_latest_json",
    "find_installer_url",
    "format_update_message",
    "install_update",
    "launch_installer",
    "update_status_message",
    "open_url",
]
