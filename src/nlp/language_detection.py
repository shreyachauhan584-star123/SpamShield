"""Lightweight, dependency-free language/script detection for SMS.

Returns one of: en, hi (Devanagari), hinglish (Roman Hindi), mixed (Devanagari + Latin),
other (another script), unknown. This is a heuristic - callers must allow manual override.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from src.nlp.hinglish_normalization import normalize_hinglish
from src.nlp.languages import SCRIPT_RANGES

_DEV = re.compile(r"[\u0900-\u097F]")
_LATIN = re.compile(r"[A-Za-z]")
_WORD = re.compile(r"[A-Za-z]+")

# Distinctive Roman-Hindi words that are not common English words.
HINGLISH_WORDS = frozenset(
    """aap aapka aapki aapke aapko apna apni hai hain hoga hogi hoge jayega jayegi jaayega jaega
    karein karen kijiye kijiyega kripya nahi nahin khata khaata bijli turant abhi jaldi paise paisa
    rupaye rupay batayein bataiye bataye batao bhejein bhejo bhej wala wali liye mein aur kya kab
    kaise dhanyavad shukriya kal aaj ghar inaam inam jeeta jeet milega milegi dena lena wapas
    beta bhai didi namaste namaskar mat kisi koi sabhi band ho gaya gayi gaye karna karo kare
    zaroori jaruri samay tak se ko ka ki ke par pe karo warna khata paise bhejein bhejo aapko""".split()
)
_AMBIGUOUS = frozenset({"ho", "par", "pe", "se", "ko", "ka", "ki", "ke", "band", "mat", "kare", "to", "me"})
_EN_FUNCTION = frozenset(
    "the is are your you to of and for in on will be has have this that with not please".split()
)

LANGUAGE_LABELS = {
    "en": "English",
    "hi": "Hindi (Devanagari)",
    "hinglish": "Hinglish (Roman Hindi)",
    "mixed": "Hindi-English mix",
    "other": "Other language/script",
    "unknown": "Unknown",
}
CODES = tuple(LANGUAGE_LABELS)


@dataclass(frozen=True)
class LanguageResult:
    code: str
    confidence: float
    devanagari_ratio: float
    hinglish_hits: int
    source: str = "auto"  # "auto" or "user"
    script: str = ""      # dominant non-Latin/non-Devanagari script name when code == "other"

    @property
    def label(self) -> str:
        return LANGUAGE_LABELS.get(self.code, self.code)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["label"] = self.label
        return d


_ORTHO_SUFFIXES = ("ein", "iye", "ega", "egi", "ogi", "oge", "wala", "wali", "unga", "ungi")


def _script_of(ch: str) -> str:
    o = ord(ch)
    for name, (lo, hi) in SCRIPT_RANGES.items():
        if lo <= o <= hi:
            return name
    return "Other"


def detect_language(text: str) -> LanguageResult:
    """Script ratios + normalised Hinglish lexicon + orthographic cues. Still a heuristic: callers must allow override.

    (A trained identifier such as fastText/langid would be better; none is installable offline here. The detector is
    behind this single function so it can be replaced without touching the rest of the system.)
    """
    text = text or ""
    dev = len(_DEV.findall(text))
    lat = len(_LATIN.findall(text))
    other_chars = [ch for ch in text if ch.isalpha() and ord(ch) > 127 and not _DEV.match(ch)]
    letters = dev + lat + len(other_chars)
    if letters == 0:
        return LanguageResult("unknown", 0.0, 0.0, 0)
    ratio = dev / letters
    if len(other_chars) / letters >= 0.5:
        scripts = [_script_of(c) for c in other_chars]
        top = max(set(scripts), key=scripts.count)
        return LanguageResult("other", 0.7, ratio, 0, script=top)
    words = [w.lower() for w in _WORD.findall(normalize_hinglish(text))]   # spelling variants (apka, acct, kro) now count
    strong = [w for w in words if w in HINGLISH_WORDS and w not in _AMBIGUOUS]
    weak = [w for w in words if w in _AMBIGUOUS]
    cues = [w for w in words if len(w) >= 5 and w.endswith(_ORTHO_SUFFIXES) and w not in HINGLISH_WORDS]
    hits = len(strong)
    score = hits + 0.5 * len(cues)
    if ratio >= 0.8:
        return LanguageResult("hi", min(0.99, 0.7 + ratio * 0.29), ratio, hits)
    if ratio >= 0.1:
        return LanguageResult("mixed", 0.6, ratio, hits)
    if len(words) >= 2 and (score >= 2 or (score >= 1 and score / len(words) >= 0.2)):
        return LanguageResult("hinglish", min(0.95, 0.5 + 0.1 * score), ratio, hits)
    if len(words) >= 3:
        fn = sum(1 for w in words if w in _EN_FUNCTION)
        conf = 0.9 if fn >= 2 else 0.6 if fn == 1 else 0.45
        if hits == 1 and len(weak) >= 1:
            conf = min(conf, 0.5)
        return LanguageResult("en", conf, ratio, hits)
    return LanguageResult("unknown", 0.2, ratio, hits)


def with_override(auto: LanguageResult, user_choice: str | None) -> LanguageResult:
    """Apply a manual language choice from the UI ('auto' or None keeps detection)."""
    if not user_choice or user_choice == "auto" or user_choice not in CODES:
        return auto
    return LanguageResult(user_choice, 1.0, auto.devanagari_ratio, auto.hinglish_hits, source="user", script=auto.script)
