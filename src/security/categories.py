"""Message-category taxonomy shown to users and stored in the structured result."""
from __future__ import annotations

from src.security.fraud_rules import Indicator

CATEGORY_NAMES = {
    "OTP_SCAM": {"en": "OTP scam", "hi": "OTP ठगी"},
    "KYC_SCAM": {"en": "KYC update scam", "hi": "KYC अपडेट ठगी"},
    "BANK_ACCOUNT_THREAT": {"en": "Bank account blocking threat", "hi": "बैंक खाता बंद होने की धमकी"},
    "UPI_SCAM": {"en": "UPI payment scam", "hi": "UPI भुगतान ठगी"},
    "REWARD_LOTTERY_SCAM": {"en": "Fake reward or lottery", "hi": "नकली इनाम या लॉटरी"},
    "GOVERNMENT_SUBSIDY_SCAM": {"en": "Fake government scheme", "hi": "नकली सरकारी योजना"},
    "ELECTRICITY_SCAM": {"en": "Electricity bill scam", "hi": "बिजली बिल ठगी"},
    "JOB_SCAM": {"en": "Fake job offer", "hi": "नकली नौकरी का ऑफ़र"},
    "LOAN_SCAM": {"en": "Loan scam", "hi": "लोन ठगी"},
    "PHISHING_LINK": {"en": "Suspicious link (phishing)", "hi": "संदिग्ध लिंक (फ़िशिंग)"},
    "IMPERSONATION": {"en": "Impersonation of an official", "hi": "अधिकारी बनकर ठगी"},
    "URGENT_PAYMENT_REQUEST": {"en": "Urgent or advance payment request", "hi": "जल्दी या पहले पैसे भेजने की माँग"},
    "REMOTE_ACCESS_SCAM": {"en": "Remote-access app scam", "hi": "रिमोट-एक्सेस ऐप ठगी"},
    "IDENTITY_THEFT": {"en": "Identity or card-detail theft attempt", "hi": "पहचान या कार्ड जानकारी चुराने की कोशिश"},
    "DELIVERY_SCAM": {"en": "Fake parcel or courier message", "hi": "नकली पार्सल या कूरियर संदेश"},
    "INVESTMENT_SCAM": {"en": "Investment scam", "hi": "निवेश ठगी"},
    "SUSPICIOUS_UNSPECIFIED": {"en": "Looks similar to unwanted messages", "hi": "अनचाहे संदेशों जैसा लगता है"},
    "NO_FRAUD_SIGNALS": {"en": "No obvious fraud signals", "hi": "ठगी के साफ़ संकेत नहीं"},
    "UNDETERMINED": {"en": "Could not be determined", "hi": "तय नहीं हो सका"},
}
# rule/URL indicator category -> message category
RULE_TO_MESSAGE = {
    "credential_theft": "OTP_SCAM", "kyc_scam": "KYC_SCAM", "account_threat": "BANK_ACCOUNT_THREAT", "upi_fraud": "UPI_SCAM",
    "lottery_prize": "REWARD_LOTTERY_SCAM", "fake_government": "GOVERNMENT_SUBSIDY_SCAM", "utility_threat": "ELECTRICITY_SCAM",
    "job_scam": "JOB_SCAM", "investment_job_scam": "JOB_SCAM", "loan_scam": "LOAN_SCAM", "suspicious_url": "PHISHING_LINK",
    "malicious_app": "PHISHING_LINK", "authority_impersonation": "IMPERSONATION", "fake_support": "IMPERSONATION",
    "advance_fee": "URGENT_PAYMENT_REQUEST", "remote_access": "REMOTE_ACCESS_SCAM", "id_update_scam": "IDENTITY_THEFT",
    "parcel_scam": "DELIVERY_SCAM", "investment_scam": "INVESTMENT_SCAM",
}
# `urgency` is a modifier of other scams, not a category by itself.
PRIORITY = ["OTP_SCAM", "REMOTE_ACCESS_SCAM", "UPI_SCAM", "IMPERSONATION", "IDENTITY_THEFT", "KYC_SCAM", "BANK_ACCOUNT_THREAT",
            "LOAN_SCAM", "JOB_SCAM", "INVESTMENT_SCAM", "REWARD_LOTTERY_SCAM", "URGENT_PAYMENT_REQUEST", "GOVERNMENT_SUBSIDY_SCAM",
            "ELECTRICITY_SCAM", "DELIVERY_SCAM", "PHISHING_LINK"]
VALID_CATEGORIES = tuple(CATEGORY_NAMES)


def message_category(indicators: list[Indicator], level: str, basis: str) -> str:
    """Category of the strongest evidence; never invented when there is none."""
    if level == "UNKNOWN":
        return "UNDETERMINED"
    scored: dict[str, int] = {}
    for i in indicators:
        cat = RULE_TO_MESSAGE.get(i.category)
        if cat:
            scored[cat] = max(scored.get(cat, 0), int(i.severity))
    if len(scored) > 1:
        scored.pop("PHISHING_LINK", None)       # a link is the delivery mechanism; the scam theme is what the user needs to know
    if scored:
        return max(scored, key=lambda c: (scored[c], -PRIORITY.index(c) if c in PRIORITY else -99))
    if basis == "model_only":
        return "SUSPICIOUS_UNSPECIFIED"
    return "NO_FRAUD_SIGNALS"


def category_name(code: str, lang: str = "en") -> str:
    return CATEGORY_NAMES.get(code, CATEGORY_NAMES["UNDETERMINED"]).get(lang) or CATEGORY_NAMES[code]["en"]
