"""Verify locale catalogs share one key set, placeholders, and markup.

Run from the repo root: ``python scripts/check_i18n.py``
Also imported by ``tests/test_i18n.py`` so ``pytest -q`` covers it.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

from . import LANGUAGES, LANGUAGE_CODES, locales_dir

# Kept verbatim in every language.
EXACT_VALUES = frozenset({"Hi I'm Ahmi, hope this helps!"})

# If the English value contains one of these, the translation must too.
BRANDS = ("RemedyPDF", "ClaimIDX", "Patreon", "GitHub", "Remedy", "Ahmi")

# Words that may stay as in English inside an otherwise structural string.
LOANWORDS = frozenset(
    {
        "Zoom",
        "PDF",
        "EPUB",
        "XPS",
        "CBZ",
        "MOBI",
        "SVG",
        "HTML",
        "MIT",
        "APK",
        "OLED",
        "GitHub",
        "Patreon",
        "Android",
        "Windows",
        "RemedyPDF",
        "Remedy",
        "Ahmi",
        "ClaimIDX",
        "Esc",
        "Ctrl",
        "OK",
        "v",
        "B",
        "C",
        "FictionBook",
        "Word",
    }
)

# The natural translation is the same string in that language.
_SAME_OK: dict[str, frozenset[str]] = {
    "es": frozenset({"Error"}),
    "fr": frozenset({"Page", "Images", "Documents", "Version {version}"}),
    "de": frozenset({"Version {version}"}),
    "it": frozenset({"&File"}),
}

_PLACEHOLDER = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")
_TAG = re.compile(r"</?[A-Za-z][A-Za-z0-9]*\b[^>]*>")
_WORD = re.compile(r"[A-Za-z][A-Za-z0-9·]*")

# Theme and filter labels are passed to t() through a variable, so the AST
# scan does not see them. They still have to be catalog keys.
_THEME_LABELS = (
    "Normal (no theme)",
    "Dark",
    "Light",
    "High contrast",
    "Sepia (paper)",
    "Night (OLED)",
    "Midnight blue",
    "Soft paper",
    "Slate gray",
    "Normal page",
    "Invert page (dark paper)",
    "Sepia page",
    "Grayscale page",
    "Warm page",
    "Cool page",
)


def _src_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _const_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def extract_message_keys(root: Path | None = None) -> set[str]:
    """String constants passed to ``t()`` / ``tn()`` under ``src/``."""
    base = root or _src_root()
    found: set[str] = set()
    for path in sorted(base.rglob("*.py")):
        if "locales" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            raise SystemExit(f"{path}: {exc}") from exc
        env: dict[str, str] = {}
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            value = _const_string(node.value)
            if value is None:
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    env[target.id] = value
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Name) or func.id not in ("t", "tn", "_tr"):
                continue
            for arg in node.args:
                text = _const_string(arg)
                if text is None and isinstance(arg, ast.Name):
                    text = env.get(arg.id)
                if text:
                    found.add(text)
    found.update(_THEME_LABELS)
    if "{n} matches" in found:
        found.add("{n} matches.few")
        found.add("{n} matches.many")
    return found


def _may_equal_english(value: str) -> bool:
    if value in EXACT_VALUES:
        return True
    stripped = _PLACEHOLDER.sub(" ", value)
    words = _WORD.findall(stripped)
    if not words:
        return True
    return all(word in LOANWORDS for word in words)


def _load(path: Path) -> tuple[dict[str, str] | None, str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, f"{path.name}: invalid JSON ({exc})"
    except OSError as exc:
        return None, f"{path.name}: {exc}"
    if not isinstance(data, dict):
        return None, f"{path.name}: catalog must be a JSON object"
    out: dict[str, str] = {}
    for key, value in data.items():
        if not isinstance(key, str) or not isinstance(value, str):
            return None, f"{path.name}: keys and values must be strings ({key!r})"
        out[key] = value
    return out, None


def check_catalogs(root: Path | None = None) -> list[str]:
    """Return a list of human-readable problems. Empty means the catalogs pass."""
    problems: list[str] = []
    folder = locales_dir()
    en_path = folder / "en.json"
    english, err = _load(en_path)
    if err or english is None:
        return [err or "en.json missing"]

    for key, value in english.items():
        if value.strip() == "":
            problems.append(f"en.json: empty value for {key!r}")
        if key.endswith(".few") or key.endswith(".many"):
            if value != "{n} matches":
                problems.append(f"en.json: {key!r} must equal '{{n}} matches'")
        elif value != key:
            problems.append(f"en.json: value must equal the key {key!r}")

    expected_codes = [code for code, _name in LANGUAGES]
    present = {p.stem for p in folder.glob("*.json")}
    for code in expected_codes:
        if code not in present:
            problems.append(f"missing locale file {code}.json")
    for extra in sorted(present - set(expected_codes)):
        problems.append(f"unexpected locale file {extra}.json")

    source_keys = extract_message_keys(root)
    missing_in_en = sorted(source_keys - set(english))
    for key in missing_in_en:
        problems.append(f"en.json missing source string {key!r}")

    en_keys = set(english)
    for code in expected_codes:
        if code == "en":
            continue
        path = folder / f"{code}.json"
        if not path.is_file():
            continue
        data, load_err = _load(path)
        if load_err or data is None:
            problems.append(load_err or f"{code}.json unreadable")
            continue
        keys = set(data)
        if keys != en_keys:
            missing = sorted(en_keys - keys)
            extra = sorted(keys - en_keys)
            if missing:
                problems.append(f"{code}.json missing {len(missing)} keys, first: {missing[:3]!r}")
            if extra:
                problems.append(f"{code}.json extra {len(extra)} keys, first: {extra[:3]!r}")
        for key, value in data.items():
            if value.strip() == "":
                problems.append(f"{code}.json: empty value for {key!r}")
                continue
            en_value = english.get(key, key)
            if key in EXACT_VALUES or en_value in EXACT_VALUES:
                if value != en_value:
                    problems.append(f"{code}.json: {key!r} must stay {en_value!r}")
                continue
            if _PLACEHOLDER.findall(en_value) != _PLACEHOLDER.findall(value):
                problems.append(
                    f"{code}.json: placeholders differ for {key!r}: "
                    f"{_PLACEHOLDER.findall(en_value)!r} vs {_PLACEHOLDER.findall(value)!r}"
                )
            names = _PLACEHOLDER.findall(value)
            if names:
                dummy = {name: "1" for name in names}
                try:
                    value.format(**dummy)
                except (IndexError, KeyError, ValueError) as exc:
                    problems.append(f"{code}.json: format failed for {key!r}: {exc}")
            if _TAG.findall(en_value) != _TAG.findall(value):
                problems.append(f"{code}.json: HTML tags differ for {key!r}")
            if "&" in en_value and "{" not in en_value:
                if en_value.count("&") != value.count("&"):
                    problems.append(
                        f"{code}.json: accelerator '&' count differs for {key!r}"
                    )
            for brand in BRANDS:
                if brand in en_value and brand not in value:
                    problems.append(f"{code}.json: {key!r} dropped {brand}")
            if value == en_value and not _may_equal_english(en_value):
                if key not in _SAME_OK.get(code, ()):
                    problems.append(f"{code}.json: untranslated {key!r}")
            if code not in LANGUAGE_CODES:
                problems.append(f"unknown language {code}")
    return problems


def main(argv: list[str] | None = None) -> int:
    del argv
    problems = check_catalogs()
    if problems:
        print(f"i18n check failed ({len(problems)}):", file=sys.stderr)
        for item in problems:
            print(f"  - {item}", file=sys.stderr)
        return 1
    folder = locales_dir()
    en = json.loads((folder / "en.json").read_text(encoding="utf-8"))
    print(f"i18n check OK: {len(en)} keys, {len(LANGUAGES)} languages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
