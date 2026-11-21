"""Devanagari normalisation: nukta/chandrabindu/nasal spelling variants and common loan-word spellings.

Variants are mapped TO the spellings used by the rule patterns and training data. Nothing is dropped (न / नहीं / मत
survive), so negation is preserved.
"""
from __future__ import annotations

import re
import unicodedata

_ZW = re.compile(r"[\u200b\u200c\u200d\u2060\ufeff]")
_NUKTA = "\u093c"
_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
# nasal consonant + halant before a stop -> anusvara  (बन्द -> बंद, सन्दर्भ -> संदर्भ)
_NASAL = re.compile("न्(?=[कखगघचछजझटठडढतथदधपफबभ])")

WORDS = {
    "ब्लाक": "ब्लॉक", "ब्लोक": "ब्लॉक", "ब्लॉक्ड": "ब्लॉक",
    "अकाउन्ट": "अकाउंट", "एकाउंट": "अकाउंट", "एकाउन्ट": "अकाउंट", "अकाऊंट": "अकाउंट", "अकाउण्ट": "अकाउंट",
    "जायेगा": "जाएगा", "जायेगी": "जाएगी", "जाऐगा": "जाएगा", "जायगा": "जाएगा", "जाएंगे": "जाएंगे",
    "लाटरी": "लॉटरी", "लौटरी": "लॉटरी",
    "केवायसी": "केवाईसी", "केवाइसी": "केवाईसी", "के वाई सी": "केवाईसी", "केवाईसि": "केवाईसी",
    "ओटिपी": "ओटीपी", "ओ टी पी": "ओटीपी", "ओटीपि": "ओटीपी",
    "यू पी आई": "यूपीआई", "यूपिआई": "यूपीआई", "यूपीआइ": "यूपीआई",
    "एटिएम": "एटीएम", "ए टी एम": "एटीएम",
    "क्लीक": "क्लिक", "कनैक्शन": "कनेक्शन", "रिफन्ड": "रिफंड", "बेंक": "बैंक", "बैन्क": "बैंक", "बैंक्": "बैंक",
    "कैंसल": "कैंसिल", "पासवर्ड": "पासवर्ड", "शेअर": "शेयर",
}
_WORD_RX = re.compile("|".join(map(re.escape, sorted(WORDS, key=len, reverse=True))))


def normalize_hindi(text: str) -> str:
    if not text:
        return ""
    t = unicodedata.normalize("NFC", text)
    t = _ZW.sub("", t).replace(_NUKTA, "")            # क़ -> क, ज़ -> ज, फ़ -> फ
    t = t.replace("\u0901", "\u0902")                  # chandrabindu -> anusvara
    t = t.translate(_DIGITS)
    t = _NASAL.sub("ं", t)
    return _WORD_RX.sub(lambda m: WORDS[m.group(0)], t)


def normalize_script(text: str) -> str:
    """Apply the right normaliser(s) for the scripts present (code-mixed text gets both)."""
    from src.nlp.hinglish_normalization import normalize_hinglish
    if not text:
        return ""
    if re.search(r"[\u0900-\u097F]", text):
        text = normalize_hindi(text)
    if re.search(r"[A-Za-z]", text):
        text = normalize_hinglish(text)
    return text
