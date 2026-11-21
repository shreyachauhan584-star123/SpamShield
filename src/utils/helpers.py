"""Small shared helpers."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(path: str | Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while block := fh.read(chunk):
            h.update(block)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def pick(bilingual: dict | str | None, lang: str = "en") -> str:
    """Choose a language from {"en": ..., "hi": ...}; falls back to English, then ''."""
    if bilingual is None:
        return ""
    if isinstance(bilingual, str):
        return bilingual
    return bilingual.get(lang) or bilingual.get("en") or ""


_LONG_DIGITS = re.compile(r"\d{9,18}")
_SHORT_DIGITS = re.compile(r"\d{4,8}")


def redact_sensitive(text: str) -> str:
    """Mask OTP-like and account/phone-like digit runs. Use before logging anything derived from an SMS."""
    text = _LONG_DIGITS.sub("[long-number]", text)
    return _SHORT_DIGITS.sub("[number]", text)
