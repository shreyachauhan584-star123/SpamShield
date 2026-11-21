"""Orchestrates one SMS analysis. UI-independent and free of persistence (nothing is stored)."""
from __future__ import annotations

from dataclasses import dataclass

from config import RISK_THRESHOLDS, RiskThresholds
from src.explainability.explain_prediction import highlight_html, term_spans
from src.explainability.feature_explanations import top_features
from src.models.model_loader import ModelUnavailable, get_advanced, load_baseline, load_metrics
from src.models.muril_predict import MuRILUnavailable, load_muril_metrics, load_muril_predictor
from src.models.predict import unavailable
from src.nlp.language_detection import detect_language, with_override
from src.nlp.multilingual import language_reliability
from src.nlp.text_processing import token_count
from src.security.fraud_rules import RuleEngine
from src.security.categories import category_name, message_category
from src.security.fraud_rules import Indicator
from src.security.risk_assessment import assess_risk
from src.security.threat_intel import ThreatIntelProvider
from src.services.result_schema import AnalysisResult, validate_result
from src.security.safety_recommendations import build_recommendations
from src.security.url_analysis import analyze_urls
from src.services.translation_service import tr
from src.utils.helpers import pick
from src.utils.validators import InputValidationError, validate_message


@dataclass
class Runtime:
    rule_engine: RuleEngine
    baseline: object | None
    baseline_error: str | None
    metrics: dict | None
    muril: object | None = None
    muril_error: str | None = None
    muril_metrics: dict | None = None

def build_runtime() -> Runtime:
    """Load baseline and initialize the optional MuRIL predictor."""
    try:
        base, err = load_baseline(), None
    except ModelUnavailable as exc:
        base, err = None, str(exc)

    muril, muril_error = None, None
    try:
        muril = load_muril_predictor()
    except MuRILUnavailable as exc:
        muril_error = str(exc)

    return Runtime(
    RuleEngine(),
    base,
    err,
    load_metrics(),
    muril,
    muril_error,
    load_muril_metrics()
)

def _select_predictor(rt: Runtime, choice: str):
    if choice == "muril":
        if rt.muril is not None:
            return rt.muril, False
        return rt.baseline, True

    if choice == "advanced":
        adv = get_advanced()
        if adv is not None:
            return adv, False
        return rt.baseline, True

    return rt.baseline, False

def analyze_sms(text, language_override: str | None = None, model_choice: str = "baseline",
                runtime: Runtime | None = None, thresholds: RiskThresholds = RISK_THRESHOLDS,
                threat_provider: ThreatIntelProvider | None = None) -> dict:
    """`threat_provider` is None unless the caller explicitly opted in (it sends URL addresses to a third party)."""
    rt = runtime or build_runtime()
    try:
        clean = validate_message(text)
    except InputValidationError as exc:
        return {"ok": False, "error_code": exc.code}

    lang = with_override(detect_language(clean), language_override)
    urls = analyze_urls(clean)
    scan = rt.rule_engine.scan(clean, has_links=bool(urls))
    threat = {"used": False}
    if threat_provider is not None and urls:
        verdicts = threat_provider.check([u["url"] for u in urls])
        threat = {"used": True, "provider": threat_provider.name,
                  "results": {u: {"status": v.status, "detail": v.detail} for u, v in verdicts.items()},
                  "note": "'not_flagged' only means the provider has no record; it does not mean the link is safe."}
        for u in urls:
            v = verdicts.get(u["url"])
            if v and v.status == "flagged":
                u["indicators"].append(Indicator("U020", "suspicious_url", 3, u["url"], tuple(u["span"]),
                    {"en": "A threat-intelligence service has flagged this link as dangerous.", "hi": "एक सुरक्षा सेवा ने इस लिंक को ख़तरनाक बताया है।"},
                    {"en": "Do not open this link.", "hi": "इस लिंक को न खोलें।"}, source="url"))
                u["structure_verdict"] = "unusual_structure"
    url_inds = [i for u in urls for i in u["indicators"]]
    indicators = sorted(scan.indicators + url_inds, key=lambda i: -i.severity)

    predictor, fell_back = _select_predictor(rt, model_choice)
    ml, features, model_failure = (unavailable(rt.baseline_error or "no model")), None, None
    if predictor is not None:
        try:
            ml = predictor.predict(clean)
            if hasattr(predictor, "pipeline"):
                features = top_features(predictor.pipeline, clean)
        except Exception as exc:  # noqa: BLE001 - never crash the UI because a model failed
            model_failure = type(exc).__name__
            ml = unavailable(model_failure)
    model_metrics = (
        rt.muril_metrics
        if getattr(predictor, "kind", None) == "transformer"
        else rt.metrics
    )
    reliability = language_reliability(lang.code, model_metrics)
    if getattr(predictor, "kind", "") == "advanced":
        reliability = "limited"  # advanced model has no evaluation in this repo
    if lang.source == "auto" and lang.confidence < 0.5 and reliability == "evaluated":
        reliability = "limited"

    risk = assess_risk(indicators, ml, lang.code, reliability, token_count(clean), scan.benign, thresholds)
    if lang.source == "auto" and lang.confidence < 0.5 and lang.code in ("en", "hinglish", "mixed", "hi"):
        risk["notes"].append("note_low_language_confidence")

    spans = [tuple(i.span) for i in indicators]
    if features and risk["model_used_in_decision"]:
        spans += term_spans(clean, [f["feature"] for f in features["toward_flagged"]])

    recs = build_recommendations(risk["level"], indicators)
    res = {
        "ok": True,
        "text": clean,
        "language": lang.as_dict(),
        "indicators": [i.as_dict() for i in indicators],
        "benign": scan.benign,
        "urls": [{k: v for k, v in u.items() if k != "indicators"} | {"indicator_ids": [i.rule_id for i in u["indicators"]],
                  "indicators": [i.as_dict() for i in u["indicators"]]} for u in urls],
        "ml": ml,
        "model": {"name": ml.get("model_name"), "kind": ml.get("kind"), "requested": model_choice,
                  "fell_back_to_baseline": fell_back, "failure": model_failure, "reliability": reliability},
        "risk": risk,
        "features": features,
        "recommendations": recs,
        "highlight_spans": [list(s) for s in spans if s[1] > s[0]],
        "rules_version": scan.rules_version, "suppressed": scan.suppressed, "threat_intel": threat,
        "evaluation_status": (rt.metrics or {}).get("evaluation_status"),
    }
    return finalize_schema(res)


def _both(key: str) -> dict:
    return {"en": tr(key, "en"), "hi": tr(key, "hi")}


def build_schema(res: dict) -> dict:
    """Structured, traceable result (see result_schema.py). Every explanation cites real evidence."""
    risk, ml = res["risk"], res["ml"]
    rule_ev = [i for i in res["indicators"] if i["source"] == "rule"]
    url_findings = [{k: v for k, v in u.items() if k not in ("indicator_ids",)} for u in res["urls"]]
    expl = [{"ref": i["rule_id"], "kind": i["source"], "text": i["explanation"]} for i in res["indicators"]]
    if risk["model_used_in_decision"]:
        expl.append({"ref": "model", "kind": "model", "text": _both("reason_model")})
    for n in risk["notes"]:
        if n == "note_benign":
            expl += [{"ref": f"benign:{b['rule_id']}", "kind": "benign", "text": b["explanation"]} for b in res["benign"][:1]]
        else:
            expl.append({"ref": f"note:{n}", "kind": "note", "text": _both(n)})
    if risk["uncertain_reason"]:
        expl.append({"ref": f"note:uncertain_{risk['uncertain_reason']}", "kind": "note", "text": _both(f"uncertain_{risk['uncertain_reason']}")})
    acts = [{"text": a, "source": src} for a, src in zip(res["recommendations"]["actions"], res["recommendations"].get("action_sources", []))]
    code = message_category([Indicator(i["rule_id"], i["category"], i["severity"], "", (0, 0), {}, {}) for i in res["indicators"]], risk["level"], risk["basis"])
    ml_ok = ml.get("available")
    return AnalysisResult(
        risk_level=risk["level"], message_category=code, category_name=CATEGORY_BOTH(code),
        detected_language=res["language"],
        model_prediction={"available": bool(ml_ok), "model_id": ml.get("model_id"), "model_name": ml.get("model_name"), "label": ml.get("label"),
                          "raw_score": ml.get("score"), "calibrated_probability": ml.get("calibrated_probability"),
                          "calibration_status": ml.get("calibration_status", "unavailable"), "reliability_for_language": risk["ml_reliability"],
                          "used_in_decision": risk["model_used_in_decision"], "score_note": "raw_score is an uncalibrated model score, not a probability of fraud"},
        rule_evidence=rule_ev, url_findings=url_findings, explanations=expl, recommended_actions=acts,
        confidence=({"kind": "calibrated_probability_flagged", "value": ml["calibrated_probability"], "scope": "model only, not the risk level"}
                    if ml_ok and ml.get("calibration_status") == "validated" and ml.get("calibrated_probability") is not None else None),
        uncertainty={"is_unknown": risk["uncertain"], "reason": risk["uncertain_reason"], "evaluation_status": res.get("evaluation_status"),
                     "basis": risk["basis"]},
        rules_version=res.get("rules_version", ""), threat_intel=res.get("threat_intel", {"used": False})).to_dict()


def CATEGORY_BOTH(code: str) -> dict:
    return {"en": category_name(code, "en"), "hi": category_name(code, "hi")}


def finalize_schema(res: dict) -> dict:
    """Attach the validated schema. An internally inconsistent result is NEVER shown as-is: it is downgraded to UNKNOWN."""
    schema = build_schema(res)
    errors = validate_result(schema)
    if errors:
        res["risk"] = {**res["risk"], "level": "UNKNOWN", "uncertain": True, "uncertain_reason": "internal_inconsistency", "notes": res["risk"]["notes"]}
        schema = build_schema(res)
        schema["message_category"], schema["category_name"] = "UNDETERMINED", CATEGORY_BOTH("UNDETERMINED")
        res["schema_errors"] = errors
    res["schema"] = schema
    res["category"] = {"code": schema["message_category"], "name": schema["category_name"]}
    return res


# --------------------------- localisation of a result for display ---------------------------
def build_view(res: dict, lang: str) -> dict:
    """Turn a raw analysis result into display strings in `lang` ('en' or 'hi')."""
    risk = res["risk"]
    level = risk["level"]
    reasons = [pick(i["explanation"], lang) for i in res["indicators"] if i["source"] == "rule"]
    reasons += [pick(i["explanation"], lang) for i in res["indicators"] if i["source"] == "url"]
    model_reason = tr("reason_model", lang) if risk["model_used_in_decision"] else None
    notes = [tr(n, lang) for n in risk["notes"] if n != "note_benign"]
    if "note_benign" in risk["notes"]:
        notes += [pick(b["explanation"], lang) for b in res["benign"][:1]] or [tr("note_benign", lang)]
    if risk["uncertain_reason"]:
        notes.insert(0, tr(f"uncertain_{risk['uncertain_reason']}", lang))
    indicators = [{
        "rule_id": i["rule_id"], "severity": i["severity"], "severity_label": tr(f"severity_{i['severity']}", lang),
        "matched_text": i["matched_text"], "explanation": pick(i["explanation"], lang),
        "recommendation": pick(i["recommendation"], lang), "source": i["source"],
    } for i in res["indicators"]]
    urls = [{
        "url": u["url"], "domain": u["registered_domain"] or u["host"],
        "verdict": tr("url_unusual" if u["structure_verdict"] == "unusual_structure" else "url_nothing_unusual", lang),
        "findings": [pick(i["explanation"], lang) for i in u["indicators"]],
    } for u in res["urls"]]
    actions = [pick(a, lang) for a in res["recommendations"]["actions"]]
    report = pick(res["recommendations"]["report"], lang)
    view = {
        "level": level, "level_label": tr(f"risk_{level}", lang), "headline": tr(f"headline_{level}", lang),
        "summary": tr(f"summary_{level}", lang), "reasons": reasons, "model_reason": model_reason, "notes": notes, "indicators": indicators,
        "urls": urls, "actions": actions, "report": report,
        "highlight_html": highlight_html(res["text"], [tuple(s) for s in res["highlight_spans"]]),
        "model_line": tr("model_line", lang, model=res["model"]["name"] or "-"),
        "disclaimer": tr("disclaimer_general", lang),
        "language_label": res["language"]["label"],
        "category": category_name(res["category"]["code"], lang),
    }
    view["spoken"] = spoken_text(view, lang)
    return view


def spoken_text(view: dict, lang: str) -> str:
    """Plain-language audio script: the risk and what to do - never raw scores or technical terms."""
    why = " ".join(view["reasons"][:3])
    todo = " ".join(view["actions"][:3])
    head = "मुख्य कारण:" if lang == "hi" else "Main reasons:"
    act = "आपको यह करना चाहिए:" if lang == "hi" else "What you should do:"
    parts = [view["headline"] + ".", view["summary"]]
    if why:
        parts.append(f"{head} {why}")
    if todo:
        parts.append(f"{act} {todo}")
    return " ".join(parts)
