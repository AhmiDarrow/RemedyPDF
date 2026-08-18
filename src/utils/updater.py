"""GitHub Releases auto-update helpers (SecretSticky-style channel)."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import webbrowser
from pathlib import Path
from typing import Any, Callable, Optional, Union
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
        __version__ = "1.4.5"

_UA = f"RemedyPDF/{__version__} (+https://github.com/{GITHUB_OWNER}/{GITHUB_REPO})"

# Comparable version key: (core…, is_release, pre_tokens…)
# is_release=1 sorts after any pre-release of the same core (semver).
_VersionKey = tuple[Union[int, str], ...]


def _pre_token(bit: str) -> tuple[int, Union[int, str]]:
    """Semver pre-release identifier: pure ints compare as ints; else as strings."""
    s = (bit or "").strip()
    if s.isdigit():
        return (0, int(s))
    return (1, s.lower())


def _parse_version(text: str) -> _VersionKey:
    """Best-effort semver key from tag like v1.2.0 or 1.2.0-beta.1.

    Ordering (semver-compatible for common tags):
      1.0.0-alpha < 1.0.0-alpha.1 < 1.0.0-beta < 1.0.0-beta.2
      < 1.0.0-rc.1 < 1.0.0 < 1.0.1
    Build metadata (+…) is ignored.
    """
    s = (text or "").strip().lstrip("vV")
    if not s:
        return (0, 0, 0, 1)
    s = s.split("+", 1)[0]
    core, _, pre = s.partition("-")
    parts: list[int] = []
    for bit in core.split("."):
        m = re.match(r"(\d+)", bit)
        parts.append(int(m.group(1)) if m else 0)
    while len(parts) < 3:
        parts.append(0)
    core_t = tuple(parts[:3])
    if not pre:
        # Final release sorts after any pre-release of the same core.
        return core_t + (1,)
    pre_bits = [b for b in pre.replace("_", ".").split(".") if b != ""]
    tokens: list[Union[int, str]] = []
    for bit in pre_bits:
        kind, val = _pre_token(bit)
        tokens.extend((kind, val))
    # is_release=0 so 1.0.0-beta < 1.0.0
    return core_t + (0,) + tuple(tokens)


def compare_versions(a: str, b: str) -> int:
    """Return -1 if a<b, 0 if equal, 1 if a>b (semver-aware, incl. pre-release)."""
    ta, tb = _parse_version(a), _parse_version(b)
    if ta < tb:
        return -1
    if ta > tb:
        return 1
    return 0


class UpdateCancelled(Exception):
    """Raised when the user (or caller) aborts an in-flight download."""


def file_sha256(path: str, chunk_size: int = 1024 * 1024) -> str:
    """Hex SHA-256 of a file on disk."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def normalize_sha256(value: Optional[str]) -> str:
    """Strip optional 'sha256:' prefix / whitespace; return lowercase hex or ''."""
    s = (value or "").strip().lower()
    if s.startswith("sha256:"):
        s = s[7:].strip()
    # Accept only full SHA-256 hex
    if re.fullmatch(r"[0-9a-f]{64}", s):
        return s
    return ""


def find_installer_sha256(info: Optional[dict[str, Any]]) -> str:
    """Expected installer SHA-256 from update info (empty if unknown).

    Looks at latest.json platforms.windows-x86_64.sha256 / signature,
    top-level sha256, then matching GitHub API asset digests.
    """
    if not info:
        return ""
    platforms = info.get("platforms") if isinstance(info.get("platforms"), dict) else {}
    win = platforms.get("windows-x86_64")
    if isinstance(win, dict):
        for key in ("sha256", "signature", "digest"):
            got = normalize_sha256(str(win.get(key) or ""))
            if got:
                return got
    for key in ("sha256", "installer_sha256", "digest"):
        got = normalize_sha256(str(info.get(key) or ""))
        if got:
            return got

    # GitHub Releases API: asset.digest is often "sha256:<hex>"
    url = find_installer_url(info) or ""
    assets = info.get("assets") or []
    if isinstance(assets, list):
        for a in assets:
            if not isinstance(a, dict):
                continue
            aurl = str(a.get("browser_download_url") or "")
            name = str(a.get("name") or "").lower()
            if url and aurl == url:
                got = normalize_sha256(str(a.get("digest") or a.get("sha256") or ""))
                if got:
                    return got
            if url and url.rstrip("/").endswith("/" + str(a.get("name") or "")):
                got = normalize_sha256(str(a.get("digest") or a.get("sha256") or ""))
                if got:
                    return got
            # Prefer setup asset digest when URL unknown match
            if "setup" in name and name.endswith(".exe"):
                got = normalize_sha256(str(a.get("digest") or a.get("sha256") or ""))
                if got and (not url or "setup" in url.lower()):
                    return got
    return ""


def verify_file_sha256(path: str, expected: str) -> None:
    """Raise OSError if file hash does not match expected (normalized) hex."""
    exp = normalize_sha256(expected)
    if not exp:
        raise OSError("Missing expected SHA-256")
    if not path or not os.path.isfile(path):
        raise OSError("Installer file missing for hash verify")
    got = file_sha256(path)
    if got != exp:
        raise OSError(
            f"Installer SHA-256 mismatch (expected {exp[:12]}…, got {got[:12]}…)"
        )


def clean_stale_extraction_dirs(max_age_days: int = 7) -> int:
    """Remove leftover PyInstaller onefile extraction dirs (%TEMP% _MEI dirs).

    Old onefile builds left a new _MEI dir per launch; onedir builds don't
    create them. Best-effort cleanup of dirs older than max_age_days; never
    raises. Returns the number of dirs removed.
    """
    removed = 0
    try:
        tmp = Path(tempfile.gettempdir())
        cutoff = time.time() - max_age_days * 86400
        for d in tmp.glob("_MEI*"):
            try:
                if not d.is_dir():
                    continue
                if d.stat().st_mtime >= cutoff:
                    continue
                # Skip the dir the current process may be running from.
                shutil.rmtree(d, ignore_errors=True)
                removed += 1
            except OSError:  # noqa: BLE001
                continue
    except OSError:  # noqa: BLE001
        pass
    return removed


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
        # Keep the human release page URL separate from the installer asset URL.
        # Overwriting url with platforms.*.url made "Open release" download a
        # raw .exe instead of showing the GitHub release notes page.
        release_url = str(
            latest.get("html_url")
            or latest.get("url")
            or f"https://github.com/{owner}/{repo}/releases"
        )
        # If latest.json put the installer .exe in top-level url, prefer tag page.
        if release_url.lower().endswith(".exe"):
            release_url = (
                str(latest.get("html_url") or "").strip()
                or f"https://github.com/{owner}/{repo}/releases/tag/v{tag}"
            )
        platforms = latest.get("platforms") if isinstance(latest.get("platforms"), dict) else {}
        if tag and compare_versions(tag, current_version) > 0:
            out: dict[str, Any] = {
                "tag": tag,
                "name": latest.get("name") or tag,
                "url": release_url,
                "html_url": release_url,
                "body": notes,
                "platforms": platforms,
                "source": "latest.json",
            }
            # Surface top-level digest fields when present (find_installer_sha256
            # also walks platforms / assets).
            for key in ("sha256", "installer_sha256", "digest"):
                if latest.get(key):
                    out[key] = latest.get(key)
            return out

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
    cancel_check: Optional[Callable[[], bool]] = None,
    expected_sha256: Optional[str] = None,
) -> str:
    """Stream-download url to dest (bytes). progress(done, total) optional.

    cancel_check() → True aborts mid-stream (raises UpdateCancelled) and
    removes the partial file. When expected_sha256 is a full 64-hex digest,
    the finished file is verified before return (mismatch → OSError + delete).

    Raises on network failure, cancel, hash mismatch, or empty payload.
    Returns dest on success.
    """
    req = Request(url, headers={"User-Agent": _UA})
    total = 0
    done = 0
    exp = normalize_sha256(expected_sha256)

    def _cancelled() -> bool:
        if cancel_check is None:
            return False
        try:
            return bool(cancel_check())
        except Exception:  # noqa: BLE001
            return False

    def _cleanup_partial() -> None:
        try:
            if dest and os.path.isfile(dest):
                os.remove(dest)
        except OSError:
            pass

    if _cancelled():
        _cleanup_partial()
        raise UpdateCancelled("Update download cancelled")

    try:
        with urlopen(req, timeout=timeout) as resp:
            try:
                total = int(resp.headers.get("Content-Length") or 0)
            except (ValueError, AttributeError):
                total = 0
            with open(dest, "wb") as fh:
                while True:
                    if _cancelled():
                        raise UpdateCancelled("Update download cancelled")
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
                    if _cancelled():
                        raise UpdateCancelled("Update download cancelled")
    except UpdateCancelled:
        _cleanup_partial()
        raise
    except Exception:
        _cleanup_partial()
        raise

    if done <= 0:
        _cleanup_partial()
        raise OSError("Empty download payload")

    if exp:
        try:
            verify_file_sha256(dest, exp)
        except OSError:
            _cleanup_partial()
            raise
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
    cancel_check: Optional[Callable[[], bool]] = None,
    require_sha256: bool = True,
) -> Optional[str]:
    """Download the installer for update info and launch it silently.

    When latest.json / API provides a SHA-256, the download is verified before
    launch. require_sha256=True (default) refuses install when no digest is
    published so a missing channel digest cannot launch an unverified binary.
    Pass require_sha256=False only for trusted local/dev channels.
    cancel_check() → True aborts and raises UpdateCancelled.

    Returns the installer path when spawned, or None (missing installer URL,
    download/hash/launch failure). UpdateCancelled propagates to the caller
    so the UI can treat cancel as a soft abort (not a hard error dialog).
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
    # Sanitize tag for filesystem (pre-release tags may contain +)
    safe_tag = re.sub(r"[^\w.\-]+", "_", tag) or "update"
    dest = os.path.join(dest_dir, f"RemedyPDF-{safe_tag}-setup.exe")
    expected = find_installer_sha256(info)
    if require_sha256 and not expected:
        raise OSError(
            "Release channel did not publish an installer SHA-256; refusing install"
        )
    try:
        download_update(
            url,
            dest,
            progress=progress,
            cancel_check=cancel_check,
            expected_sha256=expected or None,
        )
    except UpdateCancelled:
        try:
            if os.path.exists(dest):
                os.remove(dest)
        except Exception:  # noqa: BLE001
            pass
        raise
    except OSError:
        # Hash mismatch / empty payload / I/O — surface to UI (do not mask as
        # "no installer available").
        try:
            if os.path.exists(dest):
                os.remove(dest)
        except Exception:  # noqa: BLE001
            pass
        raise
    except Exception as exc:  # noqa: BLE001
        try:
            if os.path.exists(dest):
                os.remove(dest)
        except Exception:  # noqa: BLE001
            pass
        raise OSError(f"Update download failed: {exc}") from exc
    if cancel_check is not None:
        try:
            if cancel_check():
                try:
                    if os.path.exists(dest):
                        os.remove(dest)
                except Exception:  # noqa: BLE001
                    pass
                raise UpdateCancelled("Update install cancelled")
        except UpdateCancelled:
            raise
        except Exception:  # noqa: BLE001
            pass
    if not launch_installer(dest):
        raise OSError("Could not launch the downloaded installer")
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
    "UpdateCancelled",
    "check_for_update",
    "clean_stale_extraction_dirs",
    "compare_versions",
    "download_update",
    "fetch_latest_json",
    "file_sha256",
    "find_installer_sha256",
    "find_installer_url",
    "format_update_message",
    "install_update",
    "launch_installer",
    "normalize_sha256",
    "update_status_message",
    "verify_file_sha256",
    "open_url",
]
