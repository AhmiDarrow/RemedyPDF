"""Lightweight catalogs for RemedyPDF.

English strings are the message keys and the runtime fallback. A missing key
returns the English catalog value, then the key itself. Lookup never raises
and never returns a blank string when the key is non-blank.

No third-party i18n library. PyQt is imported only inside helpers that need it,
so the Kivy Android UI can call ``t()`` without Qt.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Mapping, Optional

# Stable codes shipped with the app. Native names are not translated.
LANGUAGES: tuple[tuple[str, str], ...] = (
    ("en", "English"),
    ("es", "Español"),
    ("fr", "Français"),
    ("de", "Deutsch"),
    ("pt-BR", "Português (Brasil)"),
    ("it", "Italiano"),
    ("ru", "Русский"),
    ("pl", "Polski"),
    ("ja", "日本語"),
    ("ko", "한국어"),
    ("zh-CN", "简体中文"),
)

LANGUAGE_CODES: frozenset[str] = frozenset(code for code, _name in LANGUAGES)

# QLocale names. File dialogs and spin boxes follow this after setDefault.
_QLOCALE_NAMES = {
    "en": "en_US",
    "es": "es_ES",
    "fr": "fr_FR",
    "de": "de_DE",
    "pt-BR": "pt_BR",
    "it": "it_IT",
    "ru": "ru_RU",
    "pl": "pl_PL",
    "ja": "ja_JP",
    "ko": "ko_KR",
    "zh-CN": "zh_CN",
}

# Traditional Chinese is a different script. Do not map it onto zh-CN.
_UNSUPPORTED = frozenset({"zh-tw", "zh-hk", "zh-hant", "zh-mo"})

_ALIAS = {
    "en": "en",
    "en-us": "en",
    "en-gb": "en",
    "en-au": "en",
    "es": "es",
    "es-es": "es",
    "es-mx": "es",
    "es-419": "es",
    "es-ar": "es",
    "es-co": "es",
    "fr": "fr",
    "fr-fr": "fr",
    "fr-ca": "fr",
    "fr-be": "fr",
    "de": "de",
    "de-de": "de",
    "de-at": "de",
    "de-ch": "de",
    "pt": "pt-BR",
    "pt-br": "pt-BR",
    "pt-pt": "pt-BR",
    "it": "it",
    "it-it": "it",
    "ru": "ru",
    "ru-ru": "ru",
    "pl": "pl",
    "pl-pl": "pl",
    "ja": "ja",
    "ja-jp": "ja",
    "ko": "ko",
    "ko-kr": "ko",
    "zh": "zh-CN",
    "zh-cn": "zh-CN",
    "zh-hans": "zh-CN",
    "zh-sg": "zh-CN",
}

_NBSP = "\u00a0"
_PERCENT_SPACE = frozenset({"de", "fr", "es", "ru"})
_GROUP_DOT = frozenset({"de", "es", "it", "pt-BR"})
_GROUP_NBSP = frozenset({"fr", "ru", "pl"})
_DECIMAL_COMMA = frozenset({"de", "es", "fr", "it", "pt-BR", "pl", "ru"})

_JA = ["Yu Gothic UI", "Yu Gothic", "Meiryo", "MS Gothic", "Noto Sans CJK JP", "Noto Sans JP"]
_KO = ["Malgun Gothic", "Noto Sans CJK KR", "Noto Sans KR"]
_ZH = ["Microsoft YaHei UI", "Microsoft YaHei", "Noto Sans CJK SC", "Noto Sans SC", "SimHei", "SimSun"]
_LATIN = ["Segoe UI", "SF Pro Text", "Helvetica Neue", "Noto Sans"]


class _State:
    lang: str = "en"
    catalogs: dict[str, dict[str, str]]
    home: Optional[Path] = None
    persist: bool = False

    def __init__(self) -> None:
        self.catalogs = {}


_state = _State()


def normalize_language(code: Optional[str]) -> Optional[str]:
    """Map an OS or user tag onto a shipped code, or None if unsupported."""
    if code is None:
        return None
    raw = str(code).strip().replace("_", "-")
    if not raw:
        return None
    key = raw.lower()
    if key in _UNSUPPORTED:
        return None
    if key in _ALIAS:
        return _ALIAS[key]
    primary = key.split("-", 1)[0]
    if primary in _ALIAS:
        return _ALIAS[primary]
    return None


def language_native_name(code: str) -> str:
    norm = normalize_language(code) or "en"
    for c, name in LANGUAGES:
        if c == norm:
            return name
    return "English"


def locales_dir() -> Path:
    """Directory of ``*.json`` catalogs (dev tree, PyInstaller, or onedir)."""
    here = Path(__file__).resolve().parent / "locales"
    candidates: list[Path] = []
    if here.is_dir():
        candidates.append(here)
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "i18n" / "locales")
        candidates.append(Path(meipass) / "src" / "i18n" / "locales")
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates.append(exe_dir / "i18n" / "locales")
        candidates.append(exe_dir / "_internal" / "i18n" / "locales")
    for path in candidates:
        if path.is_dir():
            return path
    return here


def _read_catalog(code: str) -> dict[str, str]:
    path = locales_dir() / f"{code}.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, str] = {}
    for key, value in data.items():
        if isinstance(key, str) and isinstance(value, str):
            out[key] = value
    return out


def _catalog(code: str) -> Mapping[str, str]:
    cached = _state.catalogs.get(code)
    if cached is None:
        cached = _read_catalog(code)
        _state.catalogs[code] = cached
    return cached


def reload_catalogs() -> None:
    """Drop cached JSON (tests that rewrite locale files)."""
    _state.catalogs.clear()


def current_language() -> str:
    return _state.lang


def t(key: str, **kwargs: object) -> str:
    """Translate ``key``. Missing keys fall back to English, then the key.

    Format placeholders use ``str.format``. A format error falls back to the
    English template, then the unformatted template. Never raises.
    """
    if not isinstance(key, str):
        key = str(key)
    template = _lookup(key)
    if kwargs:
        try:
            return template.format(**kwargs)
        except (IndexError, KeyError, ValueError):
            english = _state.catalogs.get("en", {}).get(key) or key
            if english and english != template:
                try:
                    return english.format(**kwargs)
                except (IndexError, KeyError, ValueError):
                    pass
            return template if template else key
    return template if template else key


def _lookup(key: str) -> str:
    current = _catalog(_state.lang)
    value = current.get(key)
    if isinstance(value, str) and value.strip() != "":
        return value
    if _state.lang != "en":
        english = _catalog("en").get(key)
        if isinstance(english, str) and english.strip() != "":
            return english
    return key


def plural_category(lang: str, n: int) -> str:
    """CLDR-ish category for an integer count."""
    try:
        number = abs(int(n))
    except (TypeError, ValueError):
        number = 0
    base = (normalize_language(lang) or "en").split("-", 1)[0]
    if base in ("ja", "ko", "zh"):
        return "other"
    if base == "fr":
        return "one" if number < 2 else "other"
    if base in ("ru", "pl"):
        mod10 = number % 10
        mod100 = number % 100
        if mod10 == 1 and mod100 != 11:
            return "one"
        if 2 <= mod10 <= 4 and not (12 <= mod100 <= 14):
            return "few"
        return "many"
    return "one" if number == 1 else "other"


def tn(one_key: str, other_key: str, n: int, **kwargs: object) -> str:
    """Plural lookup. ``other_key.few`` and ``other_key.many`` are extra keys."""
    cat = plural_category(_state.lang, n)
    if cat == "one":
        key = one_key
    elif cat == "few":
        key = other_key + ".few"
    elif cat == "many":
        key = other_key + ".many"
    else:
        key = other_key
    payload = dict(kwargs)
    payload.setdefault("n", format_int(n))
    return t(key, **payload)


def choose_language(
    explicit: Optional[str],
    settings_lang: Optional[str],
    detected: Optional[str],
    *,
    ignore_environment: bool,
) -> str:
    """Pick a shipped language code.

    Explicit ``--lang`` / ``REMEDYPDF_LANG`` wins. Under pytest, with no
    explicit language and no ``--home``, stay on English and do not read the
    real profile (``ignore_environment=True``).
    """
    if explicit:
        return normalize_language(explicit) or "en"
    if ignore_environment:
        return "en"
    if settings_lang:
        return normalize_language(str(settings_lang)) or "en"
    if detected:
        return normalize_language(detected) or "en"
    return "en"


def detect_os_language() -> str:
    """Best-effort UI language of the operating system."""
    try:
        from PyQt5.QtCore import QLocale

        norm = normalize_language(QLocale.system().name())
        if norm:
            return norm
    except Exception:  # noqa: BLE001
        pass
    if os.name == "nt":
        try:
            import ctypes

            buf = ctypes.create_unicode_buffer(85)
            ctypes.windll.kernel32.GetUserDefaultLocaleName(buf, 85)
            norm = normalize_language(buf.value)
            if norm:
                return norm
        except Exception:  # noqa: BLE001
            pass
    try:
        import locale

        loc = ""
        getter = getattr(locale, "getdefaultlocale", None)
        if getter is not None:
            pair = getter()
            loc = (pair[0] if pair else "") or ""
        norm = normalize_language(loc)
        if norm:
            return norm
    except Exception:  # noqa: BLE001
        pass
    return "en"


def default_config_dir() -> Path:
    if os.name == "nt":
        base = os.environ.get("APPDATA")
        if base:
            return Path(base) / "RemedyPDF"
        return Path.home() / "AppData" / "Roaming" / "RemedyPDF"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "remedypdf"
    return Path.home() / ".config" / "RemedyPDF"


def config_dir() -> Optional[Path]:
    return _state.home


def settings_path() -> Optional[Path]:
    if _state.home is None:
        return None
    return _state.home / "settings.json"


def _read_settings(path: Path) -> dict:
    """Load a settings object. A corrupt file is moved aside and treated as empty."""
    if not path.is_file():
        return {}
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except Exception:  # noqa: BLE001
        stamp = time.strftime("%Y%m%d%H%M%S")
        dest = path.with_name(path.name + f".corrupt-{stamp}")
        try:
            path.replace(dest)
        except OSError:
            try:
                dest.write_bytes(path.read_bytes())
            except OSError:
                pass
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def _write_settings(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, path)


def update_settings(updates: Mapping[str, object]) -> None:
    """Merge ``updates`` into settings.json. Unknown existing keys stay."""
    path = settings_path()
    if path is None or not _state.persist:
        return
    data = _read_settings(path)
    data.update(dict(updates))
    _write_settings(path, data)


def load_settings() -> dict:
    path = settings_path()
    if path is None:
        return {}
    return _read_settings(path)


def parse_launch_args(argv: Optional[list[str]]) -> dict[str, Optional[str]]:
    """Pull ``--home`` and ``--lang`` (and ``--home=`` / ``--lang=``) out of argv."""
    home: Optional[str] = None
    lang: Optional[str] = None
    args = list(argv or [])
    i = 1
    while i < len(args):
        item = args[i]
        if item in ("--home", "--lang"):
            if i + 1 < len(args):
                value = args[i + 1]
                if item == "--home":
                    home = value
                else:
                    lang = value
                i += 2
                continue
            i += 1
            continue
        if item.startswith("--home="):
            home = item.split("=", 1)[1]
        elif item.startswith("--lang="):
            lang = item.split("=", 1)[1]
        i += 1
    return {"home": home, "lang": lang}


def iter_document_args(argv: Optional[list[str]]):
    """Yield positional args, skipping ``--home`` / ``--lang`` and their values."""
    args = list(argv or [])
    skip = False
    for item in args[1:]:
        if skip:
            skip = False
            continue
        if item in ("--home", "--lang"):
            skip = True
            continue
        if item.startswith("--home=") or item.startswith("--lang="):
            continue
        if item.startswith("-"):
            continue
        yield item


def _under_test() -> bool:
    return bool(os.environ.get("PYTEST_CURRENT_TEST"))


def init_i18n(argv: Optional[list[str]] = None) -> str:
    """Select the language for this process and remember where settings live.

    Pytest without ``--home`` and without an explicit language forces English
    and does not read or write the user's profile.
    """
    args = list(sys.argv if argv is None else argv)
    parsed = parse_launch_args(args)
    explicit = parsed.get("lang") or os.environ.get("REMEDYPDF_LANG") or None
    home_arg = parsed.get("home")
    under = _under_test()
    home_explicit = bool(home_arg)
    use_profile = home_explicit or not under
    ignore_environment = under and not explicit and not home_explicit

    settings_lang = None
    if use_profile:
        _state.home = Path(home_arg) if home_arg else default_config_dir()
        _state.persist = True
        settings_lang = _read_settings(_state.home / "settings.json").get("language")
    else:
        _state.home = None
        _state.persist = False

    detected = None
    if not explicit and not settings_lang and not ignore_environment:
        detected = detect_os_language()

    lang = choose_language(
        explicit,
        str(settings_lang) if settings_lang else None,
        detected,
        ignore_environment=ignore_environment,
    )
    _state.lang = lang
    # First run, or an explicit --lang, sticks. Same value does not rewrite.
    if _state.persist and settings_lang != lang:
        update_settings({"language": lang})
    # Touch English so a later fallback does not hit the disk twice.
    _catalog("en")
    _catalog(lang)
    return lang


def set_language(code: str, persist: Optional[bool] = None) -> str:
    """Switch the process language. Persist when the profile is writable.

    ``persist=False`` never writes. ``persist=True`` writes even if init turned
    persistence off, except it still refuses the real user profile during pytest
    unless a home directory was set.
    """
    norm = normalize_language(code) or "en"
    _state.lang = norm
    _catalog(norm)
    if persist is False:
        return norm
    write = _state.persist if persist is None else True
    if not write:
        return norm
    if _state.home is None:
        if _under_test():
            return norm
        _state.home = default_config_dir()
        _state.persist = True
    else:
        _state.persist = True
    current = _read_settings(_state.home / "settings.json").get("language")
    if current != norm:
        update_settings({"language": norm})
    return norm


def format_int(value: object) -> str:
    """Grouped integer for the active locale. Falls back without Qt."""
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return str(value)
    try:
        from PyQt5.QtCore import QLocale

        return QLocale().toString(number)
    except Exception:  # noqa: BLE001
        return _format_int_plain(number)


def _format_int_plain(number: int) -> str:
    sign = "-" if number < 0 else ""
    digits = str(abs(number))
    lang = _state.lang
    if lang in _GROUP_DOT:
        sep = "."
    elif lang in _GROUP_NBSP:
        sep = _NBSP
    else:
        sep = ","
    parts: list[str] = []
    while digits:
        parts.append(digits[-3:])
        digits = digits[:-3]
    parts.reverse()
    return sign + sep.join(parts)


def format_number(value: object, decimals: int = 0) -> str:
    """Fixed-point number. Decimal mark follows the language."""
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return str(value)
    places = max(0, int(decimals))
    if places == 0:
        return format_int(int(round(number)))
    try:
        from PyQt5.QtCore import QLocale

        return QLocale().toString(number, "f", places)
    except Exception:  # noqa: BLE001
        sign = "-" if number < 0 else ""
        text = f"{abs(number):.{places}f}"
        whole, frac = text.split(".", 1)
        grouped = _format_int_plain(int(whole))
        sep = "," if _state.lang in _DECIMAL_COMMA else "."
        return f"{sign}{grouped}{sep}{frac}"


def format_percent(value: object) -> str:
    """Integer percent. German, French, Spanish, and Russian use a nbsp before %."""
    try:
        number = int(round(float(value)))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return str(value)
    text = format_int(number)
    if _state.lang in _PERCENT_SPACE:
        return f"{text}{_NBSP}%"
    return f"{text}%"


def qlocale_name(code: Optional[str] = None) -> str:
    norm = normalize_language(code or _state.lang) or "en"
    return _QLOCALE_NAMES.get(norm, "en_US")


def apply_qt_locale(code: Optional[str] = None) -> None:
    """Point Qt's default locale at the active language (dates, spin boxes)."""
    try:
        from PyQt5.QtCore import QLocale

        QLocale.setDefault(QLocale(qlocale_name(code)))
    except Exception:  # noqa: BLE001
        return


def font_families_for(code: Optional[str] = None) -> list[str]:
    """Font list for the UI.

    Remedy Sans and Ahmi Pixel are Latin-only and are not used here.
    For Japanese, Korean, and Simplified Chinese the CJK UI face is first
    (those faces also draw Latin). Other languages keep Segoe UI first and
    still list CJK faces so mixed text can fall back per glyph.
    """
    lang = normalize_language(code or _state.lang) or "en"
    if lang == "ja":
        return list(_JA + _LATIN + _KO + _ZH)
    if lang == "ko":
        return list(_KO + _LATIN + _JA + _ZH)
    if lang == "zh-CN":
        return list(_ZH + _LATIN + _JA + _KO)
    return list(_LATIN + _JA + _KO + _ZH)


def apply_ui_font(app, scale: Optional[float] = None) -> None:
    """Set the application font families and point size. Safe if Qt is missing."""
    if app is None:
        return
    try:
        from PyQt5.QtGui import QFont
    except Exception:  # noqa: BLE001
        return
    if scale is None:
        try:
            stored = app.property("remedyUiScale")
            scale = float(stored) if stored else 1.0
        except (TypeError, ValueError):
            scale = 1.0
    else:
        try:
            app.setProperty("remedyUiScale", float(scale))
        except Exception:  # noqa: BLE001
            pass
    families = font_families_for(_state.lang)
    font = QFont()
    try:
        font.setFamilies(families)
    except Exception:  # noqa: BLE001
        pass
    if families:
        font.setFamily(families[0])
    try:
        font.setPointSizeF(max(8.0, 13.0 * float(scale)))
    except (TypeError, ValueError):
        font.setPointSize(13)
    try:
        app.setFont(font)
    except Exception:  # noqa: BLE001
        return


def _join_filter(pairs: list[tuple[str, str]]) -> str:
    return ";;".join(f"{label} ({pattern})" for label, pattern in pairs)


def localized_open_filter() -> str:
    """Open-dialog filter. Extensions stay ASCII; labels are translated."""
    return _join_filter(
        [
            (
                t("Documents"),
                "*.pdf *.epub *.xps *.oxps *.cbz *.cbr *.fb2 *.mobi *.svg *.docx "
                "*.html *.htm *.xhtml *.txt *.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.webp",
            ),
            (t("PDF"), "*.pdf"),
            (t("EPUB"), "*.epub"),
            (t("XPS"), "*.xps *.oxps"),
            (t("Comic Book"), "*.cbz *.cbr"),
            (t("FictionBook"), "*.fb2"),
            (t("MOBI"), "*.mobi"),
            (t("SVG"), "*.svg"),
            (t("Word"), "*.docx"),
            (t("HTML"), "*.html *.htm *.xhtml"),
            (t("Text"), "*.txt"),
            (t("Images"), "*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.webp"),
            (t("All Files"), "*"),
        ]
    )


def localized_save_filter() -> str:
    return _join_filter(
        [
            (t("PDF Files"), "*.pdf"),
            (t("All Files"), "*"),
        ]
    )


def localized_image_filter() -> str:
    return f"{t('Images')} (*.png *.jpg *.jpeg *.bmp *.webp)"


# Load English at import so About dialogs created before init_i18n stay English
# and a missing catalog never crashes the first t() call.
_state.lang = "en"
_catalog("en")
