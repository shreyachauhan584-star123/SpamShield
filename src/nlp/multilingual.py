"""Per-language evaluation bookkeeping.

We never claim support for a language the model has not been evaluated on. Three states:
  evaluated  - enough held-out samples (>= MIN_EVAL_SAMPLES_EVALUATED) from non-demo data, both classes present
  limited    - some samples (>= MIN_EVAL_SAMPLES_LIMITED) or demo-only data: model is used cautiously
  none       - too little or no evaluation: the ML model is ignored for this language (rules only)
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np
from sklearn.metrics import f1_score, precision_score, recall_score

from config import MIN_EVAL_SAMPLES_EVALUATED, MIN_EVAL_SAMPLES_LIMITED
from src.nlp.language_detection import detect_language

SUPPORTED_LANGUAGES = ("en", "hi", "hinglish", "mixed")


def per_language_metrics(texts, y_true, y_pred, demo_only: bool) -> dict:
    groups = defaultdict(lambda: ([], []))
    for t, yt, yp in zip(texts, y_true, y_pred):
        code = detect_language(t).code
        groups[code][0].append(int(yt))
        groups[code][1].append(int(yp))
    out = {}
    for code in SUPPORTED_LANGUAGES:
        yt, yp = groups.get(code, ([], []))
        n = len(yt)
        both = len(set(yt)) == 2
        entry = {"n": n, "positives": int(sum(yt)), "status": "none"}
        if n and both:
            entry.update(
                precision=float(precision_score(yt, yp, zero_division=0)),
                recall=float(recall_score(yt, yp, zero_division=0)),
                f1=float(f1_score(yt, yp, zero_division=0)),
            )
        if n >= MIN_EVAL_SAMPLES_EVALUATED and both and not demo_only:
            entry["status"] = "evaluated"
        elif n >= MIN_EVAL_SAMPLES_LIMITED and both:
            entry["status"] = "limited"
        out[code] = entry
    return out


def language_reliability(code: str, metrics: dict | None) -> str:
    """'evaluated' | 'limited' | 'none' for the given detected language code."""
    if not metrics:
        return "none"
    return metrics.get("per_language", {}).get(code, {}).get("status", "none")
