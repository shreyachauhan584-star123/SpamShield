"""Context checks used by the rule engine: negation scope and fraud-awareness messages.

Negation: "do not share your OTP" / "OTP share mat karna" / "ओटीपी किसी को न बताएँ" are warnings, not requests.
A negator counts only if it sits in the same clause as the matched phrase (no sentence/clause punctuation between).
"""
from __future__ import annotations

import re
import unicodedata

NEGATORS = {
    "en": {"not", "never", "no", "dont", "don't", "don’t", "do", "without", "cannot", "can't", "won't", "neither", "nor"},
    "hinglish": {"mat", "na", "nahi", "nahin", "nhi", "bina"},
    "hi": {"न", "ना", "नहीं", "नही", "मत", "बिना"},
}
_ALL = set().union(*NEGATORS.values())
_CLAUSE_BREAK = re.compile(r"[.!?;:,\n।|]")
_TOKEN = re.compile(r"[\w\u0900-\u0963\u0966-\u097F'’]+")
_LOOKBACK = 40


def _has_negator(segment: str) -> bool:
    toks = [t.lower() for t in _TOKEN.findall(unicodedata.normalize("NFC", segment))]
    for i, t in enumerate(toks):
        if t in {"do"}:
            if i + 1 < len(toks) and toks[i + 1] in {"not", "n't"}:
                return True
            continue
        if t in _ALL and t != "do":
            return True
    return False


def is_negated(text: str, start: int, end: int) -> bool:
    """True if the phrase text[start:end] is under negation in its own clause."""
    inside = text[start:end]
    # negator inside the matched phrase, in its final clause ("ओटीपी या पिन न बताएँ")
    last_clause = _CLAUSE_BREAK.split(inside)[-1]
    if _has_negator(last_clause):
        return True
    before = text[max(0, start - _LOOKBACK):start]
    clause = _CLAUSE_BREAK.split(before)[-1]
    tokens = _TOKEN.findall(clause)[-3:]                 # negator must be within 3 words before the phrase
    return _has_negator(" ".join(tokens))


_AWARE_MARKERS = re.compile(
    r"(?:beware|be\s+aware|stay\s+alert|fraud\s+alert|safety\s+tip|scam\s+alert|avoid\s+fraud|protect\s+yourself|"
    r"bachein|bacha\s*rahein|savdhan|sachet|fraud\s+se\s+bach|सावधान|सतर्क|बचें|धोखाधड़ी\s+से\s+बच|ठगी\s+से\s+बच)", re.I | re.U)
_AWARE_ADVICE = re.compile(r"(?:never|do\s*not|don'?t|kabhi\s+(?:na|nahi)|(?:na|mat)\s+(?:bata|bhej|share|de)|न\s+(?:बता|दें|भेज|शेयर|साझा)|कभी\s+(?:न|नहीं)|मत)", re.I | re.U)


def awareness_context(text: str) -> bool:
    """True for fraud-awareness messages (a marker such as 'beware' AND advice such as 'never share')."""
    return bool(_AWARE_MARKERS.search(text) and _AWARE_ADVICE.search(text))
