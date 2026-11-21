import pytest

from src.nlp import languages
from src.nlp.contextual_analysis import awareness_context, is_negated
from src.nlp.hindi_normalization import normalize_hindi
from src.nlp.hinglish_normalization import normalize_hinglish, split_concatenated
from src.nlp.language_detection import detect_language
from src.nlp.text_processing import normalize_for_model, tokenize
from src.models.transformer_training import class_weights
from src.security.categories import CATEGORY_NAMES, RULE_TO_MESSAGE, message_category
from src.security.fraud_rules import Indicator, RuleEngine

E = RuleEngine()


def ids(text, has_links=False):
    return {i.rule_id for i in E.scan(text, has_links).indicators}


@pytest.mark.parametrize("raw,expected", [
    ("Apka acct block hoga", "aapka account block hoga"),
    ("KYC update kro warna UPI band", "KYC update karo warna UPI band"),
    ("k.y.c update", "kyc update"), ("OTP bhejo nhi to", "OTP bhejo nahi to"),
    ("accountband ho jayega", "account band ho jayega"), ("Aapka a/c band", "Aapka account band"),
])
def test_hinglish_normalisation_variants(raw, expected):
    assert normalize_hinglish(raw).lower() == expected.lower()


def test_hinglish_normalisation_leaves_urls_emails_and_other_scripts_alone():
    s = "kro http://Acct-kro.top/Pls?x=nhi me@acct.com आपका"
    out = normalize_hinglish(s)
    assert "http://Acct-kro.top/Pls?x=nhi" in out and "me@acct.com" in out and "आपका" in out


def test_split_concatenated_only_when_fully_covered():
    assert split_concatenated("kycupdate") == ["kyc", "update"]
    assert split_concatenated("blockchain") is None and split_concatenated("account") is None


@pytest.mark.parametrize("raw,expected", [
    ("आपका बैंक अकाउन्ट ब्लाक हो जायेगा", "आपका बैंक अकाउंट ब्लॉक हो जाएगा"),
    ("बन्द कर दिया", "बंद कर दिया"), ("केवायसी करें", "केवाईसी करें"), ("राशि ५००", "राशि 500"), ("ओ टी पी बताएँ", "ओटीपी बताएं"),
])
def test_hindi_normalisation(raw, expected):
    assert normalize_hindi(raw) == expected


def test_negation_is_never_normalised_away():
    for pos, neg in [("OTP share karo", "OTP share mat karo"), ("OTP share karo", "OTP share na karo"),
                     ("Share your OTP", "Do not share your OTP"), ("ओटीपी बताएँ", "ओटीपी न बताएँ")]:
        assert normalize_for_model(pos) != normalize_for_model(neg)
        assert set(tokenize(neg)) - set(tokenize(pos))          # the negator survives as its own token


@pytest.mark.parametrize("text,start_rx,expected", [
    ("Do not share your OTP with anyone", "share your OTP", True), ("Do not delay, share your OTP now", "share your OTP", False),
    ("ओटीपी या पिन न बताएँ", "ओटीपी.*बताएँ", True), ("Kabhi OTP share karo", "OTP share karo", False),
    ("OTP share mat karna", "OTP share mat karna", True), ("Never ever share your OTP", "share your OTP", True)])
def test_negation_scope(text, start_rx, expected):
    import re
    m = re.search(start_rx, text)
    assert is_negated(text, m.start(), m.end()) is expected


@pytest.mark.parametrize("text,fires", [
    ("OTP share karo", True), ("OTP share mat karo", False), ("OTP share mat karna", False),
    ("Send your OTP to receive your reward.", True), ("Your OTP is 123456. Do not share it with anyone.", False),
    ("ओटीपी शेयर करें और इनाम पाएं।", True), ("किसी को भी ओटीपी या पिन न बताएँ।", False),
    ("Apna otp bata do warna card block ho jayega.", True), ("Kisi ko bhi OTP na batayein. Bank kabhi OTP nahi maangta.", False),
])
def test_otp_rule_is_context_aware(text, fires):
    assert ("R001" in ids(text)) is fires


def test_awareness_messages_are_not_flagged_unless_something_actionable_is_present():
    tip = "Beware of fraud! Scammers say your account will be blocked. Never share your OTP."
    assert awareness_context(tip) and ids(tip) == set()
    assert E.scan(tip).suppressed and any(b["rule_id"] == "B003" for b in E.scan(tip).benign)
    assert "R004" in ids("Beware of fraud. Your account will be blocked. Click http://x.top/a", has_links=True)   # a link keeps it flagged
    assert "R001" in ids("Beware! Send your OTP to claim the prize")                                              # a credential request keeps it flagged


@pytest.mark.parametrize("text,rule", [
    ("Apka acct block hoga. KYC update kro warna UPI band ho jayega.", "R004"), ("Apka acct block hoga. KYC update kro warna UPI band ho jayega.", "R003"),
    ("आपका बैंक अकाउन्ट ब्लाक हो जायेगा", "R004"), ("accountband ho jayega", "R004"),
    ("I am calling from the police. A case is registered, pay fine now", "R020"), ("Pre-approved loan with no documents. Click to apply", "R019"),
    ("Job offer: selected for job, pay Rs 500 registration fee", "R021"), ("Double your money in 7 days", "R022"),
    ("PAN card update nhi kiya to khata freez ho jayega. Link pe click kro http://pan-update.click/a", "R015"),
])
def test_spelling_variants_and_new_categories_are_detected(text, rule):
    assert rule in ids(text)


def test_normalised_only_matches_carry_no_fake_highlight_span():
    ind = [i for i in E.scan("आपका बैंक अकाउन्ट ब्लाक हो जायेगा").indicators if i.rule_id == "R004"][0]
    assert ind.normalized_match and ind.span == (0, 0)


def test_rules_have_version_and_all_fifteen_required_categories_are_reachable():
    assert E.version == "2.0.0"
    required = {"OTP_SCAM", "KYC_SCAM", "BANK_ACCOUNT_THREAT", "UPI_SCAM", "REWARD_LOTTERY_SCAM", "GOVERNMENT_SUBSIDY_SCAM", "ELECTRICITY_SCAM",
                "JOB_SCAM", "LOAN_SCAM", "PHISHING_LINK", "IMPERSONATION", "URGENT_PAYMENT_REQUEST", "REMOTE_ACCESS_SCAM", "IDENTITY_THEFT", "DELIVERY_SCAM"}
    reachable = {RULE_TO_MESSAGE[r["category"]] for r in E.rules if r["category"] in RULE_TO_MESSAGE} | {"PHISHING_LINK"}
    assert required <= reachable and required <= set(CATEGORY_NAMES)


def _ind(cat, sev):
    return Indicator("T", cat, sev, "m", (0, 1), {"en": "e", "hi": "h"}, {"en": "r", "hi": "r"})


def test_message_category_follows_strongest_evidence_and_never_invents():
    assert message_category([_ind("kyc_scam", 2), _ind("credential_theft", 3)], "HIGH", "rules") == "OTP_SCAM"
    assert message_category([], "LOW", "none") == "NO_FRAUD_SIGNALS" and message_category([], "UNKNOWN", "model_only") == "UNDETERMINED"
    assert message_category([], "MEDIUM", "model_only") == "SUSPICIOUS_UNSPECIFIED"
    assert message_category([_ind("urgency", 1)], "LOW", "rules") == "NO_FRAUD_SIGNALS"          # urgency alone is not a category
    assert message_category([_ind("suspicious_url", 3), _ind("kyc_scam", 2)], "HIGH", "rules") == "KYC_SCAM"   # link = delivery, theme wins
    assert message_category([_ind("suspicious_url", 3)], "MEDIUM", "rules") == "PHISHING_LINK"


# --------------------------- languages ---------------------------
@pytest.mark.parametrize("text,code", [
    ("Apka acct block hoga. KYC update kro warna UPI band ho jayega.", "hinglish"), ("Your account will be blocked", "en"),
    ("आपका बैंक खाता बंद कर दिया जाएगा।", "hi"), ("আপনার অ্যাকাউন্ট বন্ধ হয়ে যাবে", "other"), ("ok", "unknown")])
def test_language_detection_v2(text, code):
    assert detect_language(text).code == code


def test_other_script_is_named_but_not_supported():
    r = detect_language("আপনার অ্যাকাউন্ট বন্ধ হয়ে যাবে")
    assert r.script == "Bengali" and not languages.is_supported("bn")


def test_registry_does_not_claim_regional_or_garhwali_support():
    assert set(languages.supported_codes()) == {"en", "hi", "hinglish", "mixed"}
    g = languages.get("gbm")
    assert g.status == "planned" and g.ocr_tesseract is None and not g.ui_and_explanations and "Do NOT claim" in g.notes


def test_support_report_never_exceeds_evidence():
    rep = {r["code"]: r for r in languages.support_report({"per_language": {"hi": {"status": "limited", "n": 19}}})}
    assert rep["hi"]["evaluation_status"] == "limited" and rep["en"]["evaluation_status"] == "none" and rep["gbm"]["evaluation_status"] == "none"


def test_class_weights_favour_the_minority_class():
    w = class_weights([0] * 90 + [1] * 10)
    assert w[1] > w[0] and abs(w[0] - 100 / 180) < 1e-9
