"""Unicode-safe text normalisation for English, Hindi (Devanagari), Hinglish and code-mixed SMS.

Design notes
- No stop-word removal: words like "not", "never", "नहीं", "mat" carry meaning in fraud text.
- Roman Hindi (Hinglish) is kept as-is; we never transliterate.
- Numbers/URLs/phones are replaced by placeholder tokens so the model learns "a number appears"
  rather than memorising specific OTPs or links.
"""
from __future__ import annotations

import re
import unicodedata

from src.nlp.hindi_normalization import normalize_script

# Devanagari matras are combining marks and are NOT matched by \w, so include the whole block.
# 2+ character words (danda U+0964/0965 excluded), PLUS the one-letter Hindi negator "न" - dropping it would erase negation.
TOKEN_PATTERN = r"(?u)[\w\u0900-\u0963\u0966-\u097F]{2,}|(?<![\w\u0900-\u097F])न(?![\w\u0900-\u097F])"
_TOKEN_RE = re.compile(TOKEN_PATTERN)

_ZERO_WIDTH = re.compile(r"[\u200b\u200c\u200d\u2060\ufeff]")
_URL = re.compile(r"(?:https?://|www\.)\S+|\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|in|co|org|net|xyz|top|club|link|click|online|site|ly|gl)\b/?\S*", re.I)
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_PHONE = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)")
_DIGITS = re.compile(r"\d{4,}")
_RUPEE = re.compile(r"₹|\brs\.?(?=\s*\d)|\binr\b", re.I)
_SPACES = re.compile(r"\s+")


def normalize_for_model(text: str) -> str:
    """Normalise text for TF-IDF. Pure function, safe for any Unicode input."""
    if not isinstance(text, str):
        return ""
    t = unicodedata.normalize("NFKC", text)
    t = _ZERO_WIDTH.sub("", t)
    t = normalize_script(t)       # Hindi/Hinglish spelling variants -> canonical (never drops negation)
    t = t.lower()
    t = _EMAIL.sub(" emailtoken ", t)
    t = _URL.sub(" urltoken ", t)
    t = _PHONE.sub(" phonetoken ", t)
    t = _RUPEE.sub(" rupeetoken ", t)
    t = _DIGITS.sub(" numtoken ", t)
    return _SPACES.sub(" ", t).strip()


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(normalize_for_model(text))


def token_count(text: str) -> int:
    return len(_TOKEN_RE.findall(unicodedata.normalize("NFKC", text or "")))


FRIENDLY_TOKENS = {
    "urltoken": "a web link",
    "numtoken": "a long number",
    "phonetoken": "a phone number",
    "rupeetoken": "a rupee amount",
    "emailtoken": "an email address",
}
