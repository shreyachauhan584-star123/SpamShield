"""Static, offline URL analysis. Never opens, fetches or follows any URL.

A URL is only ever described as having an 'unusual structure' - never as 'confirmed malicious'.
Future integration point: `threat_intel_lookup` (reputable API, opt-in, key via environment).
"""
from __future__ import annotations

import ipaddress
import re
from urllib.parse import unquote, urlparse

from src.security.fraud_rules import Indicator

_TLDS = ("com|in|co|org|net|gov|edu|info|xyz|top|club|online|site|live|click|link|work|app|icu|buzz|shop|store|"
         "me|ly|gl|cc|tk|ml|ga|cf|gq|ru|cn|biz|us|uk|io|page|cyou|vip|fun|bank|sbi")
URL_RE = re.compile(
    r"""(?ix)
    (?:https?://|www\.)[^\s<>"'\)\]]+
    |\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?(?:/[^\s<>"'\)\]]*)?
    |\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:%s)\b(?:/[^\s<>"'\)\]]*)?
    """ % _TLDS)

SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "goo.gl", "is.gd", "cutt.ly", "rb.gy", "shorturl.at", "ow.ly",
              "tiny.cc", "buff.ly", "t.ly", "s.id", "rebrand.ly", "bl.ink", "shorte.st", "lnkd.in"}
RISKY_TLDS = {"xyz", "top", "club", "click", "work", "tk", "ml", "ga", "cf", "gq", "icu", "buzz", "online", "site", "live", "cyou", "vip", "fun"}
_SECOND_LEVEL = {"co", "com", "gov", "nic", "org", "net", "ac", "edu"}

# brand keyword -> registered domains we know to be official (not exhaustive: result says "verify")
BRAND_DOMAINS = {
    "sbi": {"sbi.co.in", "onlinesbi.sbi", "sbi.bank.in", "sbicard.com", "sbilife.co.in", "sbimf.com", "onlinesbi.com"},
    "hdfc": {"hdfcbank.com", "hdfc.com", "hdfcbank.net", "hdfclife.com"},
    "icici": {"icicibank.com", "icicibank.co.in", "iciciprulife.com"},
    "axis": {"axisbank.com", "axisbank.co.in"},
    "paytm": {"paytm.com", "paytm.in", "paytm.me"},
    "phonepe": {"phonepe.com"},
    "npci": {"npci.org.in"},
    "uidai": {"uidai.gov.in"},
    "irctc": {"irctc.co.in"},
    "pnb": {"pnbindia.in", "netpnb.com"},
    "kotak": {"kotak.com", "kotakbank.com"},
    "jio": {"jio.com"},
    "airtel": {"airtel.in", "airtel.com"},
}
_BRAND_WORD = {b: re.compile(rf"\b{b}\b", re.I) for b in BRAND_DOMAINS}


def registered_domain(host: str) -> str:
    labels = host.lower().strip(".").split(".")
    if len(labels) >= 3 and labels[-2] in _SECOND_LEVEL and len(labels[-1]) == 2:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:]) if len(labels) >= 2 else host


def extract_urls(text: str) -> list[tuple[str, int, int]]:
    """Return (url, start, end) for each URL-like string. Emails are skipped."""
    found = []
    for m in URL_RE.finditer(text or ""):
        if m.start() > 0 and text[m.start() - 1] == "@":
            continue
        url = m.group(0).rstrip(".,;:!?)]'\"")
        if url:
            found.append((url, m.start(), m.start() + len(url)))
    return found


def _ind(rid, sev, span, url, en, hi, rec_en, rec_hi) -> Indicator:
    return Indicator(rid, "suspicious_url", sev, url[:120], span,
                     {"en": en, "hi": hi}, {"en": rec_en, "hi": rec_hi}, source="url")



_PATH_HINTS = ("login", "signin", "verify", "update", "kyc", "secure", "account", "claim", "otp", "password", "confirm", "refund", "bonus")
_HOMOGLYPH = str.maketrans({"0": "o", "1": "l", "3": "e", "5": "s", "4": "a", "7": "t"})


def _levenshtein(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _deobfuscate(label: str) -> str:
    """Undo common look-alike tricks: digits for letters, 'rn' for 'm', 'vv' for 'w', hyphens."""
    return label.lower().replace("-", "").translate(_HOMOGLYPH).replace("rn", "m").replace("vv", "w")


def lookalike_brand(reg: str) -> str | None:
    """Brand whose official domain label this domain imitates (edit distance 1-2 after de-obfuscation), else None."""
    label = reg.split(".")[0]
    if len(label) < 5:
        return None
    candidates = {_deobfuscate(label)} | {_deobfuscate(part) for part in label.split("-") if len(part) >= 5}
    for brand, domains in BRAND_DOMAINS.items():
        if reg in domains:
            return None
        for d in domains:
            official = d.split(".")[0]
            if len(official) < 5:
                continue
            for clean in candidates:
                if clean != official and 0 < _levenshtein(clean, official) <= 2:
                    return brand
                if clean == official and label != official and len(label.split("-")) == 1:
                    return brand           # e.g. "hdfcbank" spelled with digits/homoglyphs on another TLD
    return None


def analyze_url(url: str, span: tuple[int, int], message: str = "") -> dict:
    has_scheme = bool(re.match(r"https?://", url, re.I))
    inds: list[Indicator] = []
    malformed = False
    try:
        parsed = urlparse(url if has_scheme else "http://" + url)
        host = (parsed.hostname or "").lower()
        _ = parsed.port                      # raises ValueError for an invalid port
    except ValueError:
        parsed, host, malformed = urlparse("http://invalid"), "", True
    reg = registered_domain(host) if host else ""
    rec_en = "Do not tap this link. If you must check it, ask someone you trust or visit the official website by typing its address yourself."
    rec_hi = "इस लिंक पर टैप न करें। जाँचना ज़रूरी हो तो किसी भरोसेमंद व्यक्ति से पूछें या आधिकारिक वेबसाइट का पता खुद टाइप करके खोलें।"

    is_ip = False
    try:
        ipaddress.ip_address(host)
        is_ip = True
    except ValueError:
        pass

    if reg in SHORTENERS or host in SHORTENERS:
        inds.append(_ind("U001", 2, span, url, "This is a shortened link, so you cannot see where it really goes.",
                         "यह छोटा किया हुआ लिंक है, इसलिए पता नहीं चलता कि यह असल में कहाँ ले जाएगा।", rec_en, rec_hi))
    if is_ip:
        inds.append(_ind("U002", 3, span, url, "The link uses a number address (IP) instead of a normal website name. Genuine banks and companies do not do this.",
                         "लिंक में सामान्य वेबसाइट नाम की जगह नंबर वाला पता (IP) है। असली बैंक या कंपनियाँ ऐसा नहीं करतीं।", rec_en, rec_hi))
    if has_scheme and parsed.scheme == "http" and not is_ip:
        inds.append(_ind("U003", 1, span, url, "The link does not use a secure connection (http, not https).",
                         "लिंक सुरक्षित कनेक्शन (https) का इस्तेमाल नहीं करता।", rec_en, rec_hi))
    if "@" in parsed.netloc:
        inds.append(_ind("U004", 3, span, url, "The link contains an '@' sign, a trick used to hide the real website.",
                         "लिंक में '@' का निशान है, जिससे असली वेबसाइट छिपाई जाती है।", rec_en, rec_hi))
    if malformed:
        inds.append(_ind("U013", 1, span, url, "The link is malformed and could not be read properly.",
                         "लिंक की बनावट ग़लत है और ठीक से पढ़ा नहीं जा सका।", rec_en, rec_hi))
    if "xn--" in host or any(ord(c) > 127 for c in host):
        inds.append(_ind("U005", 2, span, url, "The website name uses special look-alike characters.",
                         "वेबसाइट के नाम में मिलते-जुलते दिखने वाले खास अक्षर हैं।", rec_en, rec_hi))
    if not is_ip and host and (host.count(".") >= 4 or host.count("-") >= 3):
        inds.append(_ind("U006", 1, span, url, "The website name is unusually long or has many dashes or parts.",
                         "वेबसाइट का नाम असामान्य रूप से लंबा है या उसमें बहुत सारे डैश/हिस्से हैं।", rec_en, rec_hi))
    tld = host.rsplit(".", 1)[-1] if "." in host else ""
    if tld in RISKY_TLDS and reg not in SHORTENERS:
        inds.append(_ind("U008", 1, span, url, f"The website ending '.{tld}' is cheap and often used for throw-away sites. This alone does not prove anything.",
                         f"वेबसाइट का अंत '.{tld}' सस्ता है और अक्सर कुछ दिन वाली साइटों में इस्तेमाल होता है। केवल इससे कुछ साबित नहीं होता।", rec_en, rec_hi))

    full = unquote(url).lower()
    if "%" in host or url.count("%") >= 3:
        inds.append(_ind("U011", 2 if "%" in host else 1, span, url, "The link hides characters with percent-encoding, which can disguise where it goes.",
                         "लिंक में अक्षर प्रतिशत-कोड (%) से छिपाए गए हैं, जिससे असली पता छिप सकता है।", rec_en, rec_hi))
    path_q = (unquote(parsed.path or "") + "?" + unquote(parsed.query or "")).lower()
    hits = [h for h in _PATH_HINTS if h in path_q]
    if hits and not is_ip:
        inds.append(_ind("U010", 1, span, url, f"The link path asks you to '{hits[0]}' something. Scam pages often use such words; genuine sites do too, so this is only a hint.",
                         f"लिंक के रास्ते में '{hits[0]}' जैसा शब्द है। ठगी वाले पेज अक्सर ऐसे शब्द रखते हैं, पर असली साइटें भी रखती हैं, इसलिए यह सिर्फ़ एक इशारा है।", rec_en, rec_hi))
    look = lookalike_brand(reg) if reg and not is_ip and reg not in SHORTENERS else None
    if look:
        inds.append(_ind("U009", 3, span, url, f"The website name ({reg}) looks like a copy of '{look.upper()}' with letters swapped or changed.",
                         f"वेबसाइट का नाम ({reg}) '{look.upper()}' की नक़ल जैसा है, जिसमें अक्षर बदले गए हैं।", rec_en, rec_hi))

    brand_hit = None
    for brand, domains in BRAND_DOMAINS.items():
        in_host = re.search(rf"(?<![a-z0-9]){brand}(?![a-z0-9])|{brand}[-.]", host) is not None
        in_msg = bool(_BRAND_WORD[brand].search(message or ""))
        if (in_host or in_msg) and reg not in domains and not is_ip and reg not in SHORTENERS:
            brand_hit = (brand, 3 if in_host else 2)
            break
    if brand_hit and not look:
        b, sev = brand_hit
        inds.append(_ind("U007", sev, span, url,
                         f"The message mentions or imitates '{b.upper()}', but the link's website ({reg}) is not one we recognise as official. Our list is not complete, so please verify.",
                         f"संदेश में '{b.upper()}' का नाम है, पर लिंक की वेबसाइट ({reg}) हमारी जानी हुई आधिकारिक वेबसाइटों में नहीं है। हमारी सूची अधूरी हो सकती है, इसलिए जाँच ज़रूर करें।",
                         rec_en, rec_hi))
    return {
        "url": url, "host": host, "registered_domain": reg, "span": list(span),
        "is_shortened": reg in SHORTENERS, "is_ip": is_ip,
        "structure_verdict": "unusual_structure" if inds else "no_unusual_structure_found",
        "resolved": False,           # shortened links are NEVER expanded: destination unknown, not "malicious"
        "malformed": malformed,
        "opened": False,  # we never open or fetch URLs
        "indicators": inds,
    }


def analyze_urls(text: str) -> list[dict]:
    seen, out = set(), []
    for url, s, e in extract_urls(text):
        if url.lower() in seen:
            continue
        seen.add(url.lower())
        out.append(analyze_url(url, (s, e), text))
    if len({u["registered_domain"] or u["url"] for u in out}) >= 3:
        first = out[0]
        first["indicators"].append(_ind("U012", 1, tuple(first["span"]), "multiple links", "The message contains several different links, which is unusual for a genuine notice.",
                                        "संदेश में कई अलग-अलग लिंक हैं, जो असली सूचना में कम होता है।", "Do not tap any of them.", "इनमें से किसी पर टैप न करें।"))
        first["structure_verdict"] = "unusual_structure"
    return out


def threat_intel_lookup(url: str):  # pragma: no cover - intentionally not implemented
    """Future integration point for a reputable threat-intelligence API (opt-in, key from env)."""
    raise NotImplementedError("No threat-intelligence provider is configured.")
