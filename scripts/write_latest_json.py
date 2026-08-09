#!/usr/bin/env python3
"""Write latest.json for RemedyPDF GitHub Releases auto-update channel."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--version", required=True, help="Semver without v prefix, e.g. 1.2.0")
    p.add_argument("--tag", default="", help="Git tag, e.g. v1.2.0")
    p.add_argument("--repo", required=True, help="owner/repo")
    p.add_argument(
        "--exe-name",
        default="",
        help="Asset filename on the release (default RemedyPDF-{version}-windows.exe)",
    )
    p.add_argument("--out", required=True, help="Output path for latest.json")
    p.add_argument("--notes", default="", help="Optional release notes")
    args = p.parse_args()

    version = args.version.lstrip("vV")
    tag = (args.tag or f"v{version}").strip()
    if not tag.startswith("v"):
        tag = f"v{tag}"
    exe_name = args.exe_name or f"RemedyPDF-{version}-windows.exe"
    base = f"https://github.com/{args.repo}/releases/download/{tag}"
    exe_url = f"{base}/{exe_name}"
    html_url = f"https://github.com/{args.repo}/releases/tag/{tag}"
    pub_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    notes = args.notes or f"RemedyPDF {tag}"

    payload = {
        "version": version,
        "tag_name": tag,
        "name": f"RemedyPDF {tag}",
        "notes": notes,
        "body": notes,
        "url": html_url,
        "html_url": html_url,
        "pub_date": pub_date,
        "platforms": {
            "windows-x86_64": {
                "url": exe_url,
                "signature": "",
            }
        },
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
