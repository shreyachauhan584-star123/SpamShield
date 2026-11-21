"""Language registry. A language is "supported" only if rules, explanations AND evaluation exist for it.

Entering text in a language is not support. Planned languages are listed so the architecture is ready, but the app
treats their text as UNKNOWN rather than guessing. To add a language: create a LanguageConfig, a normaliser, rule
patterns, reviewed explanations (src/locales), a labelled test set (data/validated) and report its evaluation.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LanguageConfig:
    code: str
    name: str
    native_name: str
    script: str
    status: str                 # supported | experimental | planned
    ocr_tesseract: str | None   # Tesseract language pack name (None = no OCR available)
    stt_locale: str | None      # browser speech-recognition locale
    tts_locale: str | None      # browser speech-synthesis locale
    ui_and_explanations: bool   # reviewed UI strings + explanations exist
    notes: str = ""


LANGUAGES: dict[str, LanguageConfig] = {c.code: c for c in [
    LanguageConfig("en", "English", "English", "Latin", "supported", "eng", "en-IN", "en-IN", True),
    LanguageConfig("hi", "Hindi", "हिन्दी", "Devanagari", "supported", "hin", "hi-IN", "hi-IN", True,
                   "Devanagari text is treated as Hindi; Marathi/Garhwali written in Devanagari cannot be told apart."),
    LanguageConfig("hinglish", "Hinglish", "Hinglish", "Latin", "supported", "eng", "hi-IN", "hi-IN", True,
                   "Roman-script Hindi; informal spellings handled by src/nlp/hinglish_normalization.py."),
    LanguageConfig("mixed", "Hindi-English mix", "हिन्दी + English", "Devanagari+Latin", "experimental", "hin+eng", "hi-IN", "hi-IN", True,
                   "Code-mixed text; evaluation data is limited."),
    LanguageConfig("bn", "Bengali", "বাংলা", "Bengali", "planned", "ben", "bn-IN", "bn-IN", False),
    LanguageConfig("mr", "Marathi", "मराठी", "Devanagari", "planned", "mar", "mr-IN", "mr-IN", False),
    LanguageConfig("ta", "Tamil", "தமிழ்", "Tamil", "planned", "tam", "ta-IN", "ta-IN", False),
    LanguageConfig("te", "Telugu", "తెలుగు", "Telugu", "planned", "tel", "te-IN", "te-IN", False),
    LanguageConfig("gu", "Gujarati", "ગુજરાતી", "Gujarati", "planned", "guj", "gu-IN", "gu-IN", False),
    LanguageConfig("gbm", "Garhwali", "गढ़वाली", "Devanagari", "planned", None, None, None, False,
                   "Low-resource. No validated data, OCR, speech or evaluation exist. Do NOT claim fraud detection for Garhwali until "
                   "human-labelled examples and a human evaluation are available."),
]}

SCRIPT_RANGES = {   # unicode block -> script name (used to recognise text we cannot analyse)
    "Bengali": (0x0980, 0x09FF), "Gurmukhi": (0x0A00, 0x0A7F), "Gujarati": (0x0A80, 0x0AFF), "Odia": (0x0B00, 0x0B7F),
    "Tamil": (0x0B80, 0x0BFF), "Telugu": (0x0C00, 0x0C7F), "Kannada": (0x0C80, 0x0CFF), "Malayalam": (0x0D00, 0x0D7F), "Arabic": (0x0600, 0x06FF),
}
SCRIPT_TO_PLANNED_LANGUAGE = {"Bengali": "bn", "Gujarati": "gu", "Tamil": "ta", "Telugu": "te"}


def get(code: str) -> LanguageConfig | None:
    return LANGUAGES.get(code)


def supported_codes() -> list[str]:
    return [c for c, l in LANGUAGES.items() if l.status in ("supported", "experimental")]


def is_supported(code: str) -> bool:
    l = LANGUAGES.get(code)
    return bool(l and l.status in ("supported", "experimental"))


def support_report(metrics: dict | None) -> list[dict]:
    """Registry status joined with measured evaluation status (never claims more than the evidence)."""
    per = (metrics or {}).get("per_language", {})
    rows = []
    for c, l in LANGUAGES.items():
        ev = per.get(c, {})
        rows.append({"code": c, "language": l.name, "script": l.script, "registry_status": l.status,
                     "evaluation_status": ev.get("status", "none"), "evaluation_n": ev.get("n", 0),
                     "ocr": l.ocr_tesseract or "-", "notes": l.notes})
    return rows
