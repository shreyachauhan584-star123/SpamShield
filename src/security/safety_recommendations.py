"""Bilingual safety recommendations. Reviewed wording is kept here, never machine-translated."""
from __future__ import annotations

from src.security.fraud_rules import Indicator
from src.utils.helpers import pick

ALWAYS = [
    {"en": "Never share your OTP, PIN, CVV or password with anyone - banks never ask for them.",
     "hi": "अपना OTP, पिन, CVV या पासवर्ड किसी को न बताएँ - बैंक ये कभी नहीं माँगते।"},
    {"en": "To check a message, call your bank on the number printed on your card or passbook.",
     "hi": "संदेश की जाँच के लिए अपने कार्ड या पासबुक पर छपे नंबर पर बैंक को फ़ोन करें।"},
]
BY_LEVEL = {
    "HIGH": [
        {"en": "Do not click any link or call any number in this message.", "hi": "इस संदेश का कोई लिंक न खोलें और न ही दिए नंबर पर कॉल करें।"},
        {"en": "If you already shared details or paid money, call your bank right away and the cyber crime helpline 1930.",
         "hi": "अगर आपने जानकारी दे दी है या पैसे भेज दिए हैं, तो तुरंत बैंक को और साइबर अपराध हेल्पलाइन 1930 पर फ़ोन करें।"},
    ],
    "MEDIUM": [
        {"en": "Do not click links or reply until you have checked with the bank or company yourself.",
         "hi": "जब तक आप खुद बैंक या कंपनी से जाँच न कर लें, लिंक न खोलें और जवाब न दें।"},
        {"en": "Show the message to a family member or someone you trust.", "hi": "संदेश किसी घरवाले या भरोसेमंद व्यक्ति को दिखाएँ।"},
    ],
    "UNKNOWN": [
        {"en": "Verify the message independently before doing anything it asks.", "hi": "संदेश में जो कहा गया है उसे करने से पहले अलग से जाँच करें।"},
        {"en": "Show the message to someone you trust.", "hi": "संदेश किसी भरोसेमंद व्यक्ति को दिखाएँ।"},
    ],
    "LOW": [
        {"en": "If anything still feels odd, ask your bank or a trusted person before acting.", "hi": "अगर फिर भी कुछ अजीब लगे तो कुछ करने से पहले बैंक या किसी भरोसेमंद व्यक्ति से पूछें।"},
    ],
}
REPORTING = {
    "en": "You can report fraud at cybercrime.gov.in or by calling 1930, and report suspicious messages at sancharsaathi.gov.in. GramSuraksha AI never reports anything for you.",
    "hi": "आप ठगी की शिकायत cybercrime.gov.in पर या 1930 पर फ़ोन करके कर सकते हैं, और संदिग्ध संदेश sancharsaathi.gov.in पर बता सकते हैं। GramSuraksha AI आपकी ओर से कुछ भी रिपोर्ट नहीं करता।",
}


def build_recommendations(level: str, indicators: list[Indicator]) -> dict:
    """Returns {'actions': [bilingual dict, ...], 'report': bilingual dict}."""
    actions, sources, seen = [], [], set()

    def add(item, source):
        if item["en"] not in seen:
            seen.add(item["en"])
            actions.append(item)
            sources.append(source)

    for item in BY_LEVEL.get(level, []):
        add(item, "level")
    for ind in sorted(indicators, key=lambda i: -i.severity):
        add(ind.recommendation, ind.rule_id)
    for item in ALWAYS:
        add(item, "general")
    return {"actions": actions[:7], "action_sources": sources[:7], "report": REPORTING}


def localized(recs: dict, lang: str) -> dict:
    return {"actions": [pick(a, lang) for a in recs["actions"]], "report": pick(recs["report"], lang)}
