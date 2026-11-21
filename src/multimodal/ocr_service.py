"""OCR for SMS screenshots (Tesseract via pytesseract).

Engine choice (documented in docs/ML_PIPELINE.md): Tesseract is installable on Windows/Linux without a GPU, supports
English and (with the `hin` language pack) Hindi, and is free. PaddleOCR gives better Hindi accuracy but needs a heavy
deep-learning install; it can be added behind the same `extract_text` function if you need it.

OCR output is NEVER trusted automatically: the UI must show it for editing and confirmation before analysis.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from config import MAX_SMS_CHARS, OCR_LOW_CONFIDENCE, OCR_TIMEOUT_SECONDS
from src.multimodal.image_processing import preprocess_variants, validate_image

_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SCHEME = re.compile(r"(?i)\b(https?)\s*:\s*/\s*/\s*")
_WWW = re.compile(r"(?i)\bwww\s*\.\s*")


class OCRUnavailable(RuntimeError):
    pass


@dataclass
class OCRResult:
    text: str
    confidence: float | None          # mean word confidence 0-100 (Tesseract), None if no words
    variant: str
    language: str
    words: int
    warnings: list[str] = field(default_factory=list)
    needs_review: bool = True         # always: OCR is not trusted automatically

    @property
    def low_confidence(self) -> bool:
        return self.confidence is None or self.confidence < OCR_LOW_CONFIDENCE


def ocr_status() -> dict:
    """Availability report for the admin page / UI feature flags. Never raises."""
    try:
        import pytesseract
        version = str(pytesseract.get_tesseract_version())
        langs = sorted(pytesseract.get_languages(config=""))
    except Exception as exc:  # noqa: BLE001 - missing binary, missing package...
        return {"available": False, "engine": "tesseract", "reason": f"{type(exc).__name__}: Tesseract/pytesseract not usable. See README 'OCR setup'.",
                "languages": [], "hindi_available": False}
    return {"available": True, "engine": "tesseract", "version": version, "languages": langs, "hindi_available": "hin" in langs, "reason": ""}


def repair_urls(text: str) -> str:
    """Fix only unambiguous OCR spacing damage in URL prefixes. Never guesses at characters (0/O, l/1)."""
    return _WWW.sub("www.", _SCHEME.sub(lambda m: m.group(1).lower() + "://", text))


def _choose_language(pref: str, installed: list[str]) -> tuple[str, list[str]]:
    warns = []
    wants_hindi = pref in ("hi", "mixed", "auto")
    if wants_hindi and "hin" in installed:
        return "hin+eng", warns
    if pref in ("hi", "mixed") and "hin" not in installed:
        warns.append("hindi_pack_missing")
    return "eng", warns


def extract_text(data: bytes, language: str = "auto") -> OCRResult:
    """Validate the image, OCR it and return text + confidence. Raises ImageValidationError / OCRUnavailable."""
    img = validate_image(data)
    st = ocr_status()
    if not st["available"]:
        raise OCRUnavailable(st["reason"])
    import pytesseract
    lang, warns = _choose_language(language, st["languages"])
    best = None
    for name, im in preprocess_variants(img):
        try:
            d = pytesseract.image_to_data(im, lang=lang, config="--psm 6", output_type=pytesseract.Output.DICT, timeout=OCR_TIMEOUT_SECONDS)
        except RuntimeError as exc:                          # pytesseract raises RuntimeError on timeout
            if "timeout" not in str(exc).lower():
                raise OCRUnavailable(f"OCR failed: {type(exc).__name__}") from exc
            warns.append("ocr_timeout")
            continue
        words = [(i, w, float(c)) for i, (w, c) in enumerate(zip(d["text"], d["conf"])) if w.strip() and float(c) >= 0]
        if not words:
            continue
        conf = sum(c for _, _, c in words) / len(words)
        score = conf * min(1.0, len(words) / 3)
        if best is None or score > best[0]:
            lines: dict[tuple, list[str]] = {}
            for i, w, _ in words:
                lines.setdefault((d["block_num"][i], d["par_num"][i], d["line_num"][i]), []).append(w)
            best = (score, name, conf, "\n".join(" ".join(ws) for ws in lines.values()), len(words))
    if best is None:
        return OCRResult("", None, "none", lang, 0, warns + ["no_text_found"])
    _, name, conf, text, n = best
    text = repair_urls(_CTRL.sub("", text)).strip()
    if len(text) > MAX_SMS_CHARS:
        text, warns = text[:MAX_SMS_CHARS], warns + ["truncated"]
    res = OCRResult(text, round(conf, 1), name, lang, n, list(dict.fromkeys(warns)))
    if res.low_confidence:
        res.warnings.append("low_confidence")
    return res
