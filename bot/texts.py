# -*- coding: utf-8 -*-
"""
Loads localized strings from /locales/*.json and exposes t() / detect_language().
"""
import json
import os

LOCALES_DIR = os.path.join(os.path.dirname(__file__), "..", "locales")
DEFAULT_LANGUAGE = "en"

# code -> label shown in the language picker (flag + native name)
SUPPORTED_LANGUAGES = {
    "ru": "🇷🇺 Русский",
    "en": "🇬🇧 English",
    "es": "🇪🇸 Español",
    "pt": "🇧🇷 Português",
    "fr": "🇫🇷 Français",
    "fa": "🇮🇷 فارسی",
    "ar": "🇸🇦 العربية",
    "hi": "🇮🇳 हिन्दी",
    "zh": "🇨🇳 中文",
    "tg": "🇹🇯 Тоҷикӣ",
    "id": "🇮🇩 Bahasa Indonesia",
    "ja": "🇯🇵 日本語",
    "tr": "🇹🇷 Türkçe",
    "de": "🇩🇪 Deutsch",
    "fil": "🇵🇭 Filipino",
    "ko": "🇰🇷 한국어",
    "nl": "🇳🇱 Nederlands",
    "it": "🇮🇹 Italiano",
    "es_ar": "🇦🇷 Español (Argentina)",
    "th": "🇹🇭 ไทย",
    "ur": "🇵🇰 اردو",
    "bn": "🇧🇩 বাংলা",
}

# Maps Telegram's client language_code (ISO 639-1, e.g. "pt-BR" -> "pt")
# to one of our supported locales.
_LANGUAGE_ALIASES = {
    "ru": "ru", "be": "ru", "uk": "ru",
    "en": "en",
    "es": "es",
    "pt": "pt",
    "fr": "fr",
    "fa": "fa",
    "ar": "ar",
    "hi": "hi",
    "zh": "zh",
    "tg": "tg",
    "id": "id",
    "ja": "ja",
    "tr": "tr",
    "de": "de",
    "fil": "fil",
    "ko": "ko",
    "nl": "nl",
    "it": "it",
    "es-ar": "es_ar",
    "es_ar": "es_ar",
    "th": "th",
    "ur": "ur",
    "bn": "bn",
}

_cache: dict[str, dict] = {}


def _load(lang: str) -> dict:
    if lang not in _cache:
        path = os.path.join(LOCALES_DIR, f"{lang}.json")
        if not os.path.exists(path):
            lang = DEFAULT_LANGUAGE
            path = os.path.join(LOCALES_DIR, f"{lang}.json")
        with open(path, "r", encoding="utf-8") as f:
            _cache[lang] = json.load(f)
    return _cache[lang]


def t(lang: str, key: str, **kwargs) -> str:
    """Get a localized string by key, falling back to English, then the key itself."""
    data = _load(lang)
    text = data.get(key)
    if text is None:
        text = _load(DEFAULT_LANGUAGE).get(key, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass
    return text


def detect_language(telegram_code: str | None) -> str:
    """Map a Telegram client language_code to a supported locale, defaulting to English."""
    if not telegram_code:
        return DEFAULT_LANGUAGE

    raw_code = telegram_code.lower().replace("_", "-")

    # Regional locale first, e.g. es-AR -> es_ar.
    if raw_code in _LANGUAGE_ALIASES:
        return _LANGUAGE_ALIASES[raw_code]

    code = raw_code.split("-")[0]
    return _LANGUAGE_ALIASES.get(code, DEFAULT_LANGUAGE)
