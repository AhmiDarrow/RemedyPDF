"""Catalog parity, language choice, settings merge, and CJK font coverage."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]


def test_catalogs_match_english():
    from i18n.check import check_catalogs

    problems = check_catalogs()
    assert problems == []


def test_missing_key_falls_back_and_never_blank():
    from i18n import set_language, t

    set_language("ja", persist=False)
    assert t("&File") == "ファイル(&F)"
    missing = "-".join(("this", "key", "is", "not", "in", "any", "catalog"))
    assert t(missing) == missing
    assert t("Hi I'm Ahmi, hope this helps!") == "Hi I'm Ahmi, hope this helps!"
    # Both templates lack {nope}, so the current translation is returned as-is.
    assert t("{n} match", nope=1) == "{n} 件"
    set_language("en", persist=False)
    assert t("{n} match", nope=1) == "{n} match"


def test_normalize_and_choose_language():
    from i18n import choose_language, language_native_name, normalize_language

    assert normalize_language("pt-PT") == "pt-BR"
    assert normalize_language("pt") == "pt-BR"
    assert normalize_language("zh-Hans") == "zh-CN"
    assert normalize_language("zh-TW") is None
    assert normalize_language("zh-HK") is None
    assert choose_language("ja", "fr", "de", ignore_environment=False) == "ja"
    assert choose_language(None, "fr", "de", ignore_environment=False) == "fr"
    assert choose_language(None, None, "de-AT", ignore_environment=False) == "de"
    assert choose_language(None, "fr", "de", ignore_environment=True) == "en"
    assert choose_language("zh-TW", None, "ja", ignore_environment=False) == "en"
    assert language_native_name("de") == "Deutsch"
    assert language_native_name("ja") == "日本語"
    assert language_native_name("zh-CN") == "简体中文"


def test_plurals_and_grouped_numbers():
    from i18n import apply_qt_locale, format_int, format_percent, set_language, tn

    set_language("ru", persist=False)
    assert "совпадение" in tn("{n} match", "{n} matches", 1)
    assert "совпадения" in tn("{n} match", "{n} matches", 2)
    assert "совпадений" in tn("{n} match", "{n} matches", 5)
    set_language("pl", persist=False)
    assert "trafienie" in tn("{n} match", "{n} matches", 1)
    assert "trafienia" in tn("{n} match", "{n} matches", 3)
    assert "trafień" in tn("{n} match", "{n} matches", 5)
    set_language("ja", persist=False)
    assert tn("{n} match", "{n} matches", 2) == "2 件"
    set_language("de", persist=False)
    apply_qt_locale("de")
    grouped = format_int(1234567)
    assert "234" in grouped and "567" in grouped
    assert format_percent(15).endswith("%")
    set_language("en", persist=False)
    apply_qt_locale("en")


def test_launch_args_are_not_documents():
    from i18n import iter_document_args, parse_launch_args

    parsed = parse_launch_args(
        ["remedypdf", "--home", r"C:\profile", "--lang", "es", "notes.pdf"]
    )
    assert parsed == {"home": r"C:\profile", "lang": "es"}
    docs = list(
        iter_document_args(
            ["remedypdf", "--home", "H", "a.pdf", "--lang=ja", "b.epub", "--lang", "de"]
        )
    )
    assert docs == ["a.pdf", "b.epub"]


def test_settings_merge_keeps_unknown_keys_and_sidelines_corrupt(tmp_path):
    from i18n import init_i18n, load_settings, set_language

    home = tmp_path / "home"
    home.mkdir()
    (home / "settings.json").write_text(
        json.dumps({"language": "en", "theme": "night", "custom": [1, 2]}),
        encoding="utf-8",
    )
    lang = init_i18n(["remedypdf", "--home", str(home), "--lang", "es"])
    assert lang == "es"
    data = load_settings()
    assert data["language"] == "es"
    assert data["theme"] == "night"
    assert data["custom"] == [1, 2]

    set_language("de", persist=True)
    assert load_settings()["language"] == "de"
    assert load_settings()["theme"] == "night"

    (home / "settings.json").write_text("{not json", encoding="utf-8")
    assert load_settings() == {}
    assert list(home.glob("settings.json.corrupt-*"))


def test_first_run_uses_detected_language_only_when_supported(tmp_path, monkeypatch):
    from i18n import init_i18n, load_settings

    home = tmp_path / "fresh"
    monkeypatch.setattr("i18n.detect_os_language", lambda: "ko")
    lang = init_i18n(["remedypdf", "--home", str(home)])
    assert lang == "ko"
    assert load_settings()["language"] == "ko"

    other = tmp_path / "fallback"
    lang = init_i18n(["remedypdf", "--home", str(other), "--lang", "zh-TW"])
    assert lang == "en"
    assert load_settings()["language"] == "en"


def test_cjk_fonts_are_installed():
    """Preferred CJK faces exist on Windows. Offscreen QRawFont/QPainter crash here."""
    from i18n import font_families_for

    assert font_families_for("ja")[0] == "Yu Gothic UI"
    assert font_families_for("ko")[0] == "Malgun Gothic"
    assert font_families_for("zh-CN")[0] == "Microsoft YaHei UI"
    if os.name != "nt":
        return
    fonts = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    expected = {
        "ja": ("YuGothR.ttc", "YuGothM.ttc", "msgothic.ttc"),
        "ko": ("malgun.ttf",),
        "zh-CN": ("msyh.ttc", "simsun.ttc"),
    }
    for code, names in expected.items():
        assert any((fonts / name).is_file() for name in names), (code, names)


def test_installer_ships_language_files():
    iss = (ROOT / "installer" / "remedypdf.iss").read_text(encoding="utf-8")
    for name in (
        "Spanish.isl",
        "French.isl",
        "German.isl",
        "BrazilianPortuguese.isl",
        "Italian.isl",
        "Russian.isl",
        "Polish.isl",
        "Japanese.isl",
        "Korean.isl",
        "ChineseSimplified.isl",
    ):
        assert name in iss
    assert 'Source: "{#DistDir}\\RemedyPDF\\*"' in iss
    assert "RemedyPDF" in iss
