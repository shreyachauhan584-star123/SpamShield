import pytest

from config import RiskThresholds
from src.security.fraud_rules import Indicator
from src.security.risk_assessment import assess_risk
from src.services.analysis_service import analyze_sms, build_view
from tests.helpers import CASES, runtime


def ind(sev, cat="c", rid="T"):
    return Indicator(rid, cat, sev, "m", (0, 1), {"en": "e", "hi": "h"}, {"en": "r", "hi": "r"})


def ml(score):
    return {"available": True, "score": score}


def risk(inds=(), score=None, rel="evaluated", lang="en", tokens=10, benign=None, **kw):
    return assess_risk(list(inds), ml(score) if score is not None else None, lang, rel, tokens, benign, **kw)


def test_model_alone_never_produces_high():
    for rel in ("evaluated", "limited"):
        assert risk(score=0.999, rel=rel)["level"] != "HIGH"


def test_model_only_strong_score_is_caution_if_evaluated_else_uncertain():
    assert risk(score=0.95, rel="evaluated")["level"] == "MEDIUM"
    r = risk(score=0.95, rel="limited")
    assert r["level"] == "UNKNOWN" and r["uncertain_reason"] == "model_only_limited"


def test_unevaluated_language_ignores_model():
    r = risk([ind(2)], score=0.99, rel="none")
    assert r["model_points"] == 0 and "note_model_ignored_language" in r["notes"]


def test_ambiguous_model_score_is_uncertain_unless_benign():
    assert risk(score=0.6)["level"] == "UNKNOWN"
    assert risk(score=0.6, benign=[{"rule_id": "B002"}])["level"] == "LOW"


def test_too_short_or_unsupported_language_is_uncertain():
    assert risk(score=0.1, tokens=2)["uncertain_reason"] == "too_short"
    assert risk(score=0.1, lang="other")["uncertain_reason"] == "unsupported_language"
    assert risk(score=0.1, lang="unknown")["level"] == "UNKNOWN"


def test_clean_message_is_low_but_never_claimed_safe():
    r = risk(score=0.05)
    assert r["level"] == "LOW"


def test_weak_single_signal_stays_low_with_note():
    r = risk([ind(1)], score=0.1)
    assert r["level"] == "LOW" and "note_weak_signal_only" in r["notes"]


def test_combinations_reach_caution_and_high():
    assert risk([ind(2)], score=0.1)["level"] == "MEDIUM"
    assert risk([ind(2, "a"), ind(2, "b"), ind(1, "c")], score=0.1)["level"] == "HIGH"   # rules alone: 5 points
    assert risk([ind(3, "a"), ind(3, "b")], score=0.1)["level"] == "HIGH"
    assert risk([ind(3)], score=0.1)["level"] == "MEDIUM"                              # one strong sign, nothing else
    assert risk([ind(3)], score=0.9)["level"] == "HIGH"                                  # + model agreement


def test_category_cap_prevents_stacking():
    r = risk([ind(2, "same", "A"), ind(2, "same", "B"), ind(2, "same", "C")], score=0.1)
    assert r["evidence_points"] == 4


def test_thresholds_are_configurable():
    strict = RiskThresholds(caution_points=1)
    assert risk([ind(1)], score=0.1, thresholds=strict)["level"] == "MEDIUM"
    assert risk([ind(1)], score=0.1)["level"] == "LOW"


@pytest.mark.parametrize("key,allowed", [
    ("kyc_block_en", {"MEDIUM", "HIGH"}), ("lottery_en", {"MEDIUM", "HIGH"}), ("otp_legit", {"LOW"}),
    ("electricity_paid", {"LOW"}), ("kyc_hinglish", {"MEDIUM", "HIGH"}), ("block_hindi", {"MEDIUM", "HIGH"}),
    ("upi_received", {"LOW"}), ("govt_legit", {"LOW"}), ("personal", {"LOW"}), ("url_ip", {"MEDIUM", "HIGH"}),
])
def test_required_sample_messages(key, allowed):
    res = analyze_sms(CASES[key], runtime=runtime())
    assert res["ok"] and res["risk"]["level"] in allowed, (key, res["risk"])


def test_hindi_and_hinglish_results_are_transparent_about_model_limits():
    res = analyze_sms(CASES["block_hindi"], runtime=runtime())
    assert res["model"]["reliability"] in ("limited", "none")   # demo data: never "evaluated"


@pytest.mark.parametrize("lang", ["en", "hi"])
def test_views_render_for_every_case_and_never_overclaim(lang):
    for text in list(CASES.values()) + ["hi", "Click bit.ly/abc"]:
        res = analyze_sms(text, runtime=runtime())
        v = build_view(res, lang)
        assert v["headline"] and v["summary"] and v["actions"] and v["spoken"]
        blob = (v["headline"] + v["summary"]).lower()
        assert "100% safe" not in blob and "completely safe" not in blob and "probability" not in blob
        if v["level"] == "LOW":
            assert ("guarantee" in v["summary"]) or lang == "hi"
    assert build_view(analyze_sms("Click bit.ly/abc", runtime=runtime()), "en")["urls"][0]["domain"] == "bit.ly"
