#!/usr/bin/env python3
"""Set the RemedyPDF version everywhere the repo keeps a copy of it.

src/__init__.py is the source of truth; these files carry copies that must
match it (past releases shipped with a stale installer / buildozer version):

  - src/__init__.py                (__version__)
  - src/main.py, src/core/app.py,
    src/ui/about.py, src/utils/updater.py   (ImportError fallbacks)
  - installer/remedypdf.iss        (#define MyAppVersion fallback)
  - buildozer.spec                 (version = …)
  - README.md, docs/AUTOUPDATE.md  (tag / latest.json examples)

Usage:
  python scripts/bump_version.py 1.4.6     # rewrite every location
  python scripts/bump_version.py --check   # exit 1 if any copy has drifted
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEMVER = r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.]+)?"

# (file, regex with one group around the version)
LOCATIONS: list[tuple[str, str]] = [
    ("src/__init__.py", rf'^__version__ = "({SEMVER})"'),
    ("src/main.py", rf'^\s+VERSION = "({SEMVER})"'),
    ("src/core/app.py", rf'^\s+VERSION = "({SEMVER})"'),
    ("src/ui/about.py", rf'^\s+__version__ = "({SEMVER})"'),
    ("src/utils/updater.py", rf'^\s+__version__ = "({SEMVER})"'),
    ("installer/remedypdf.iss", rf'^\s*#define MyAppVersion "({SEMVER})"'),
    ("buildozer.spec", rf"^version = ({SEMVER})$"),
    ("README.md", rf"git tag v({SEMVER}) && git push origin v{SEMVER}"),
    ("docs/AUTOUPDATE.md", rf'"version": "({SEMVER})"'),
]

# Extra docs references that move with the version (examples only).
DOC_URL_FILES = ["docs/AUTOUPDATE.md"]


def current_version() -> str:
    text = (ROOT / "src" / "__init__.py").read_text(encoding="utf-8")
    m = re.search(rf'^__version__ = "({SEMVER})"', text, re.M)
    if not m:
        raise SystemExit("src/__init__.py: __version__ not found")
    return m.group(1)


def found_versions() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for rel, pattern in LOCATIONS:
        text = (ROOT / rel).read_text(encoding="utf-8")
        out[rel] = re.findall(pattern, text, re.M)
    return out


def check() -> list[str]:
    """Return human-readable drift problems (empty list = all in sync)."""
    want = current_version()
    problems = []
    for rel, versions in found_versions().items():
        if not versions:
            problems.append(f"{rel}: version string not found")
        for v in versions:
            if v != want:
                problems.append(f"{rel}: {v} != {want}")
    return problems


def bump(new: str) -> None:
    if not re.fullmatch(SEMVER, new):
        raise SystemExit(f"not a semver version: {new!r}")
    old = current_version()
    for rel, pattern in LOCATIONS:
        path = ROOT / rel
        text = path.read_text(encoding="utf-8")

        def _swap(m: re.Match) -> str:
            whole = m.group(0)
            return whole.replace(m.group(1), new)

        new_text, n = re.subn(pattern, _swap, text, flags=re.M)
        if rel == "README.md":
            new_text = new_text.replace(f"origin v{old}", f"origin v{new}")
        if rel in DOC_URL_FILES:
            new_text = new_text.replace(f"/v{old}/", f"/v{new}/")
            new_text = new_text.replace(f"/tag/v{old}", f"/tag/v{new}")
            new_text = new_text.replace(f"RemedyPDF-{old}-", f"RemedyPDF-{new}-")
        if n == 0:
            raise SystemExit(f"{rel}: version string not found")
        path.write_text(new_text, encoding="utf-8")
        print(f"{rel}: {n} occurrence(s) -> {new}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("version", nargs="?", help="new version, e.g. 1.4.6")
    p.add_argument("--check", action="store_true", help="only verify every copy matches")
    args = p.parse_args(argv)
    if args.check or not args.version:
        problems = check()
        for line in problems:
            print(line, file=sys.stderr)
        if not problems:
            print(f"all version strings in sync ({current_version()})")
        return 1 if problems else 0
    bump(args.version)
    problems = check()
    for line in problems:
        print(line, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
