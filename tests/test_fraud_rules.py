import socket
import time

import pytest

from src.security.fraud_rules import RuleEngine
from src.security.url_analysis import analyze_urls, extract_urls
from tests.helpers import CASES

E = RuleEngine()


def ids(text):
    return {i.rule_id for i in E.scan(text).indicators}


@pytest.mark.parametrize("text,expected", [
    (CASES["kyc_block_en"], {"R003", "R004"}),
    (CASES["kyc_hinglish"], {"R003", "R004"}),
    (CASES["block_hindi"], {"R004"}),
    (CASES["lottery_en"], {"R007"}),
    ("Please share your OTP with me", {"R001"}),
    ("Aapka OTP kisi ko bhejein? nahi: otp batao", {"R001"}),
    ("अपना ओटीपी बताएं", {"R001"}),
    ("Your power will be cut tonight. Call 9811122233 now", {"R006", "R013"}),
    ("आपकी बिजली आज रात कट जाएगी", {"R006"}),
    ("To receive refund enter your UPI PIN", {"R012"}),
    ("Install AnyDesk so we can help", {"R016"}),
    ("Download http://x.top/bank.apk now", {"R017"}),
    ("Pay Rs 3000 processing fee to claim your prize", {"R009"}),
    ("Your parcel is held at customs, click link to pay fee", {"R014"}),
])
def test_rules_detect(text, expected):
    assert expected <= ids(text)


@pytest.mark.parametrize("text", [
    CASES["otp_legit"], CASES["electricity_paid"], CASES["upi_received"], CASES["govt_legit"], CASES["personal"],
    "Do not share your OTP with anyone.", "Never share your OTP, PIN or CVV.", "Your KYC has been successfully updated.",
    "Never enter UPI PIN to receive money", "Rs 1,200 debited from A/c XX4821 via UPI. Ref 6123498712.",
    "आपका ओटीपी 664120 है। इसे किसी के साथ साझा न करें।",
])
def test_rules_stay_quiet_on_legitimate_text(text):
    assert ids(text) == set(), text


def test_legit_otp_is_recognised_as_benign_context():
    assert any(b["rule_id"] == "B001" for b in E.scan(CASES["otp_legit"]).benign)


def test_government_message_with_official_domain_is_not_flagged_as_fake_scheme():
    assert "R011" not in ids("PM-KISAN update: visit https://pmkisan.gov.in/ for details")
    assert "R011" in ids("PM-KISAN stopped. Click https://pmkisan.gov.in.verify-now.xyz/ to update bank details")


def test_every_indicator_has_required_fields():
    for ind in E.scan("Your KYC pending. Share your OTP now. Call 9876543210 immediately").indicators:
        assert ind.rule_id and ind.category and ind.severity in (1, 2, 3) and ind.matched_text and ind.pattern
        assert ind.explanation["en"] and ind.explanation["hi"] and ind.recommendation["en"] and ind.recommendation["hi"]


def test_rules_are_configurable_without_code_changes():
    eng = RuleEngine(rules={"rules": [{"id": "X1", "category": "test", "severity": 2, "patterns": ["magic\\s+word"],
                                      "explanation": {"en": "e", "hi": "h"}, "recommendation": {"en": "r", "hi": "r"}}]})
    assert [i.rule_id for i in eng.scan("say the MAGIC  word").indicators] == ["X1"]


def test_adversarial_long_input_is_fast():
    nasty = ("kyc " * 500) + ("account " * 300) + ("a" * 1000)
    t0 = time.time()
    E.scan(nasty)
    assert time.time() - t0 < 1.0


# ------------------------------- URLs -------------------------------
def test_url_extraction_skips_emails_and_trims_punctuation():
    urls = [u for u, _, _ in extract_urls("Mail me@sbi.co.in or visit http://a.example.com/x?y=1, then bit.ly/abc.")]
    assert "http://a.example.com/x?y=1" in urls and "bit.ly/abc" in urls
    assert not any("sbi.co.in" in u for u in urls)


def test_url_indicators():
    r = {u["url"]: {i.rule_id for i in u["indicators"]} for u in analyze_urls(
        "http://192.168.4.7/claim bit.ly/abc http://sbi-kyc-update.xyz/login https://www.onlinesbi.sbi/home http://user@evil.com/x")}
    assert "U002" in r["http://192.168.4.7/claim"]
    assert "U001" in r["bit.ly/abc"]
    assert {"U007", "U008", "U003"} <= r["http://sbi-kyc-update.xyz/login"]
    assert r["https://www.onlinesbi.sbi/home"] == set()
    assert "U004" in r["http://user@evil.com/x"]


def test_urls_are_never_called_malicious_and_never_opened():
    def boom(*a, **k):
        raise AssertionError("network access attempted")
    original = socket.socket.connect
    socket.socket.connect = boom
    try:
        res = analyze_urls("http://192.168.4.7/claim and bit.ly/zz")
    finally:
        socket.socket.connect = original
    for u in res:
        assert u["opened"] is False
        assert u["structure_verdict"] in ("unusual_structure", "no_unusual_structure_found")
        assert "malicious" not in str(u["structure_verdict"])
