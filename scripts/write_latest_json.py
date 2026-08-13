#!/usr/bin/env python3
"""Write latest.json for RemedyPDF GitHub Releases auto-update channel."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--version", required=True, help="Semver without v prefix, e.g. 1.3.0")
    p.add_argument("--tag", default="", help="Git tag, e.g. v1.3.0")
    p.add_argument("--repo", required=True, help="owner/repo")
    p.add_argument(
        "--exe-name",
        default="",
        help="Windows portable exe on the release",
    )
    p.add_argument(
        "--setup-name",
        default="",
        help="Windows Inno Setup installer filename",
    )
    p.add_argument(
        "--apk-name",
        default="",
        help="Android APK filename (optional)",
    )
    p.add_argument(
        "--android-zip-name",
        default="",
        help="Android source zip fallback (optional)",
    )
    p.add_argument("--out", required=True, help="Output path for latest.json")
    p.add_argument("--notes", default="", help="Optional release notes")
    p.add_argument(
        "--setup-sha256",
        default="",
        help="Hex SHA-256 of the Windows setup installer (optional but recommended)",
    )
    p.add_argument(
        "--exe-sha256",
        default="",
        help="Hex SHA-256 of the Windows portable exe (optional)",
    )
    p.add_argument(
        "--apk-sha256",
        default="",
        help="Hex SHA-256 of the Android APK (optional)",
    )
    args = p.parse_args()

    version = args.version.lstrip("vV")
    tag = (args.tag or f"v{version}").strip()
    if not tag.startswith("v"):
        tag = f"v{tag}"

    exe_name = args.exe_name or f"RemedyPDF-{version}-windows.exe"
    setup_name = args.setup_name or f"RemedyPDF-{version}-windows-setup.exe"
    apk_name = args.apk_name or f"RemedyPDF-{version}-android.apk"
    azip_name = args.android_zip_name or f"RemedyPDF-{version}-android-src.zip"

    def _norm_sha(value: str) -> str:
        s = (value or "").strip().lower()
        if s.startswith("sha256:"):
            s = s[7:].strip()
        if len(s) == 64 and all(c in "0123456789abcdef" for c in s):
            return s
        return ""

    setup_sha = _norm_sha(args.setup_sha256)
    exe_sha = _norm_sha(args.exe_sha256)
    apk_sha = _norm_sha(args.apk_sha256)

    base = f"https://github.com/{args.repo}/releases/download/{tag}"
    html_url = f"https://github.com/{args.repo}/releases/tag/{tag}"
    pub_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    notes = args.notes or (
        f"RemedyPDF {tag} — Windows installer + Android package. "
        "Hi I'm Ahmi, hope this helps!"
    )

    # Prefer real APK as primary android URL when a non-empty name is provided;
    # callers may pass only the zip (CI zip-first path) and rewrite later.
    android_primary = apk_name if apk_name else azip_name
    android_kind = "apk" if apk_name else "android-src-zip"
    win_plat = {
        "url": f"{base}/{setup_name}",
        "portable_url": f"{base}/{exe_name}",
        "signature": setup_sha,  # Tauri-style field; clients also read sha256
        "kind": "installer",
    }
    if setup_sha:
        win_plat["sha256"] = setup_sha
    if exe_sha:
        win_plat["portable_sha256"] = exe_sha
    android_plat = {
        "url": f"{base}/{android_primary}",
        "src_zip_url": f"{base}/{azip_name}",
        "signature": apk_sha,
        "kind": android_kind,
    }
    if apk_sha:
        android_plat["sha256"] = apk_sha
    platforms = {
        "windows-x86_64": win_plat,
        "android-arm64": android_plat,
    }

    payload = {
        "version": version,
        "tag_name": tag,
        "name": f"RemedyPDF {tag}",
        "notes": notes,
        "body": notes,
        "url": html_url,
        "html_url": html_url,
        "pub_date": pub_date,
        "platforms": platforms,
        "assets": {
            "windows_setup": setup_name,
            "windows_portable": exe_name,
            "android_apk": apk_name,
            "android_src_zip": azip_name,
        },
    }
    # Top-level digest for simple clients / find_installer_sha256
    if setup_sha:
        payload["sha256"] = setup_sha
        payload["installer_sha256"] = setup_sha

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
