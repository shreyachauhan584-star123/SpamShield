"""Centralised UI strings. Dictionaries live in src/locales/*.json (reviewed Hindi, no auto-translation)."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

LOCALES_DIR = Path(__file__).resolve().parents[1] / "locales"
SUPPORTED = ("en", "hi")


@lru_cache(maxsize=None)
def _load(lang: str) -> dict:
    return json.loads((LOCALES_DIR / f"{lang}.json").read_text(encoding="utf-8"))


def tr(key: str, lang: str = "en", **fmt) -> str:
    lang = lang if lang in SUPPORTED else "en"
    s = _load(lang).get(key) or _load("en").get(key) or key
    try:
        return s.format(**fmt) if fmt else s
    except (KeyError, IndexError):
        return s


def missing_keys() -> dict[str, set[str]]:
    en, hi = set(_load("en")), set(_load("hi"))
    return {"missing_in_hi": en - hi, "missing_in_en": hi - en}
