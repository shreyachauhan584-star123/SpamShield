import json
import urllib.error
import urllib.request

import pytest

from src.security import threat_intel
from src.security.url_analysis import analyze_urls, lookalike_brand, extract_urls
from src.services.analysis_service import analyze_sms, build_view, finalize_schema
from src.services.result_schema import RISK_LEVELS, validate_result
from tests.helpers import CASES, runtime


def ids(text):
    return {i.rule_id for u in analyze_urls(text) for i in u["indicators"]}


@pytest.mark.parametrize("url,rule", [
    ("http://hdfcbnk-kyc.top/verify", "U009"), ("https://paytrn.com/login", "U009"), ("https://sbi-l.co.in/x", "U009"),
    ("http://xn--sbi-kyc-9ya.top/a", "U005"), ("http://sbï-bank.com/a", "U005"),
    ("http://evil.example.com/a%20b%2Fc%3Dd", "U011"), ("http://ok.example.com/account/verify?otp=1", "U010"),
    ("http://192.168.1.5/x", "U002"), ("https://user@evil.com/x", "U004"), ("bit.ly/abc", "U001"),
    ("http://sbi-kyc-update.xyz/", "U007"),
])
def test_url_structure_findings(url, rule):
    assert rule in ids(url)


def test_official_and_ordinary_domains_do_not_trigger_lookalike_or_brand_alarms():
    for u in ("https://www.onlinesbi.sbi/home", "https://hdfcbank.com/", "https://www.irctc.co.in/nget"):
        assert not ids(u) & {"U007", "U009"}, u
    assert lookalike_brand("hdfcbank.com") is None and lookalike_brand("mynewshop.com") is None


def test_multiple_links_and_malformed_urls_are_handled():
    assert "U012" in ids("see http://a.xyz/1 and http://b.top/2 and https://c.click/3")
    res = analyze_urls("click http://[bad-host/x now http://host:99999999/a")
    assert all(u["opened"] is False and u["resolved"] is False for u in res)       # malformed input never crashes


def test_shortened_links_are_unresolved_not_labelled_malicious():
    u = analyze_urls("bit.ly/abc")[0]
    assert u["is_shortened"] and u["resolved"] is False and u["structure_verdict"] == "unusual_structure" and "malicious" not in str(u)


# --------------------------- threat intelligence ---------------------------
class _Resp:
    def __init__(self, body):
        self._b = body
    def read(self, n=-1):
        return self._b
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False


def _with_urlopen(fake, fn):
    orig = urllib.request.urlopen
    urllib.request.urlopen = fake
    try:
        return fn()
    finally:
        urllib.request.urlopen = orig


def test_provider_is_off_without_env_and_never_logs_key():
    assert threat_intel.get_provider({}) is None
    assert threat_intel.get_provider({"THREAT_INTEL_PROVIDER": "safebrowsing"}) is None            # key missing
    p = threat_intel.get_provider({"THREAT_INTEL_PROVIDER": "safebrowsing", "THREAT_INTEL_API_KEY": "SECRET-KEY-123"})
    assert p.name == "google_safe_browsing" and "SECRET-KEY-123" not in repr(p) and "SECRET-KEY-123" not in repr(threat_intel.ThreatVerdict("u", "unknown"))


def test_provider_uses_fixed_endpoint_and_sends_urls_only_as_data():
    seen = {}

    def fake(req, timeout=None):
        seen["url"], seen["timeout"], seen["body"] = req.full_url, timeout, json.loads(req.data)
        return _Resp(json.dumps({"matches": [{"threat": {"url": "http://evil.top/a"}, "threatType": "SOCIAL_ENGINEERING"}]}).encode())

    p = threat_intel.SafeBrowsingProvider("KEY")
    out = _with_urlopen(fake, lambda: p.check(["http://evil.top/a", "https://fine.example.org/"]))
    assert seen["url"].startswith(threat_intel.SAFE_BROWSING_ENDPOINT) and "evil.top" not in seen["url"]
    assert seen["timeout"] == threat_intel.TIMEOUT_SECONDS
    assert out["http://evil.top/a"].status == "flagged" and out["https://fine.example.org/"].status == "not_flagged"
    assert [e["url"] for e in seen["body"]["threatInfo"]["threatEntries"]] == ["http://evil.top/a", "https://fine.example.org/"]


def test_provider_failure_is_unknown_never_safe():
    def boom(req, timeout=None):
        raise urllib.error.URLError("offline")
    out = _with_urlopen(boom, lambda: threat_intel.SafeBrowsingProvider("K").check(["http://x.top/a"]))
    assert out["http://x.top/a"].status == "unknown"


def test_threat_intel_is_not_called_unless_the_caller_opts_in():
    class Spy(threat_intel.ThreatIntelProvider):
        name, calls = "spy", 0
        def check(self, urls):
            Spy.calls += 1
            return {u: threat_intel.ThreatVerdict(u, "flagged", "x") for u in urls}
    analyze_sms("see http://a.example.com/x", runtime=runtime())
    assert Spy.calls == 0
    res = analyze_sms("see http://a.example.com/x", runtime=runtime(), threat_provider=Spy())
    assert Spy.calls == 1 and res["schema"]["threat_intel"]["used"] and "U020" in {i["rule_id"] for u in res["schema"]["url_findings"] for i in u["indicators"]}
    assert res["risk"]["level"] in ("MEDIUM", "HIGH")


# --------------------------- schema / hybrid ---------------------------
def test_every_case_yields_a_valid_traceable_schema():
    for text in list(CASES.values()) + ["Send your OTP to receive your reward", "Beware of fraud. Never share your OTP.", "bit.ly/a http://a.xyz/b https://c.top/d", "ok"]:
        s = analyze_sms(text, runtime=runtime())["schema"]
        assert validate_result(s) == [] and s["risk_level"] in RISK_LEVELS and s["confidence"] is None   # calibration is only preliminary here
        assert s["model_prediction"]["score_note"].startswith("raw_score is an uncalibrated")


def test_required_example_from_the_specification():
    s = analyze_sms("Your bank account will be blocked today. Update your KYC immediately using this link http://sbi-kyc-help.top/x", runtime=runtime())["schema"]
    assert s["risk_level"] == "HIGH" and s["message_category"] in ("KYC_SCAM", "BANK_ACCOUNT_THREAT")
    assert {"R003", "R004", "R005"} <= {e["rule_id"] for e in s["rule_evidence"]} and s["url_findings"]
    assert all(a["text"]["en"] and a["text"]["hi"] for a in s["recommended_actions"])


def test_otp_context_cases_from_the_specification():
    assert analyze_sms("Your OTP is 123456. Do not share it with anyone.", runtime=runtime())["risk"]["level"] == "LOW"
    s = analyze_sms("Send your OTP to receive your reward.", runtime=runtime())["schema"]
    assert s["risk_level"] == "HIGH" and s["message_category"] == "OTP_SCAM"
    assert analyze_sms("OTP share mat karo", runtime=runtime())["risk"]["level"] != "HIGH"


def test_high_is_never_produced_by_the_model_alone():
    for text in ("Free entry in our weekly competition winners announced", "Hello dear friend good morning", "winner winner chicken dinner prize"):
        r = analyze_sms(text, runtime=runtime())
        if r["risk"]["level"] == "HIGH":
            assert r["schema"]["rule_evidence"] or r["schema"]["url_findings"]


def test_inconsistent_results_are_downgraded_to_unknown_not_shown():
    res = analyze_sms("Your account will be blocked. Update KYC immediately.", runtime=runtime())
    broken = dict(res)
    broken["indicators"] = []                      # claims HIGH but no evidence left -> must not be displayed as HIGH
    broken["urls"] = []
    out = finalize_schema(broken)
    assert out["schema"]["risk_level"] == "UNKNOWN" and out["schema_errors"] and out["schema"]["message_category"] == "UNDETERMINED"
    assert build_view(out, "en")["level"] == "UNKNOWN"


def test_validator_flags_untraceable_explanations_and_overclaims():
    s = analyze_sms("Your account will be blocked. Update KYC immediately.", runtime=runtime())["schema"]
    bad = json.loads(json.dumps(s))
    bad["explanations"].append({"ref": "R999", "kind": "rule", "text": {"en": "invented", "hi": "x"}})
    bad["confidence"] = {"value": 0.9}
    bad["url_findings"] = [{"opened": True, "indicators": []}]
    errs = validate_result(bad)
    assert any("R999" in e for e in errs) and any("confidence" in e for e in errs) and any("opened" in e for e in errs)


def test_suppressed_matches_are_recorded_for_traceability():
    r = analyze_sms("Beware of fraud! Scammers say your account will be blocked. Never share your OTP.", runtime=runtime())
    assert r["suppressed"] and r["risk"]["level"] == "LOW"
