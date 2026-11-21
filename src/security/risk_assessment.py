"""Central risk engine. Combines rules, URL findings, model score, language reliability.

It does NOT map a raw model probability to a risk level. Principles:
  * The model alone can never produce HIGH.
  * The model is ignored for languages where it has no evaluation (reliability 'none').
  * Ambiguous / thin evidence returns UNKNOWN ("Unable to confidently assess"), never a guess.
  * LOW never means "safe" - it means "no obvious fraud patterns found".
"""
from __future__ import annotations

from collections import defaultdict

from config import MIN_TOKENS_FOR_ASSESSMENT, RISK_THRESHOLDS, RiskThresholds
from src.security.fraud_rules import Indicator

LEVELS = ("LOW", "MEDIUM", "HIGH", "UNKNOWN")


def assess_risk(
    indicators: list[Indicator],
    ml: dict | None,
    language_code: str,
    ml_reliability: str,
    token_count: int,
    benign: list | None = None,
    thresholds: RiskThresholds = RISK_THRESHOLDS,
) -> dict:
    th = thresholds
    benign = benign or []
    notes: list[str] = []

    # ---- evidence points (cap per category so one theme cannot stack unlimitedly) ----
    per_cat: dict[str, int] = defaultdict(int)
    for i in indicators:
        per_cat[i.category] += int(i.severity)
    evidence = sum(min(v, th.category_cap) for v in per_cat.values())
    n_strong = sum(1 for i in indicators if i.severity >= th.strong_severity)

    # ---- model contribution ----
    ml_available = bool(ml and ml.get("available"))
    score = float(ml.get("decision_value", ml.get("score"))) if ml_available else None
    ml_usable = ml_available and ml_reliability in ("evaluated", "limited")
    ml_pts = 0
    if ml_usable:
        ml_pts = 2 if score >= th.ml_high else 1 if score >= th.ml_caution else 0
        if ml_reliability == "limited":
            ml_pts = min(ml_pts, 1)
            notes.append("note_model_limited")
    elif ml_available:
        notes.append("note_model_ignored_language")
    else:
        notes.append("note_model_unavailable")
    total = evidence + ml_pts

    level, uncertain_reason, basis = "LOW", None, "none"
    if indicators:
        basis = "rules+model" if ml_pts else "rules"
        high = (evidence >= th.high_evidence_points or total >= th.high_points or n_strong >= 2
                or (n_strong >= 1 and (evidence >= 4 or ml_pts >= 1)))
        if high:
            level = "HIGH"
        elif total >= th.caution_points:
            level = "MEDIUM"
        else:
            level = "LOW"
            notes.append("note_weak_signal_only")
    else:
        if token_count < MIN_TOKENS_FOR_ASSESSMENT:
            level, uncertain_reason = "UNKNOWN", "too_short"
        elif language_code in ("other", "unknown"):
            level, uncertain_reason = "UNKNOWN", "unsupported_language"
        elif ml_usable and score >= th.ml_high:
            basis = "model_only"
            if ml_reliability == "evaluated":
                level = "MEDIUM"
                notes.append("note_model_only")
            else:
                level, uncertain_reason = "UNKNOWN", "model_only_limited"
        elif ml_usable and score >= th.ml_caution:
            basis = "model_only"
            if benign:
                level = "LOW"
            else:
                level, uncertain_reason = "UNKNOWN", "ml_ambiguous"
        # else LOW: no rules, model quiet or unavailable
    if benign and level == "LOW":
        notes.append("note_benign")
    # Report the model as "used" only when it actually shaped a non-LOW outcome.
    model_used = (bool(indicators) and ml_pts > 0) or (basis == "model_only" and level != "LOW")
    reported_points = ml_pts if (indicators or level != "LOW") else 0

    return {
        "level": level,
        "uncertain": level == "UNKNOWN",
        "uncertain_reason": uncertain_reason,
        "basis": basis,
        "evidence_points": evidence,
        "model_points": reported_points,
        "total_points": total,
        "strong_indicators": n_strong,
        "model_score": score,
        "model_used_in_decision": model_used,
        "ml_reliability": ml_reliability,
        "notes": list(dict.fromkeys(notes)),
        "thresholds": {
            "ml_caution": th.ml_caution, "ml_high": th.ml_high, "caution_points": th.caution_points,
            "high_points": th.high_points, "high_evidence_points": th.high_evidence_points,
            "category_cap": th.category_cap,
        },
    }
