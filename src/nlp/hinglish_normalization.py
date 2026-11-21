"""Roman-Hindi (Hinglish) normalisation: spelling variants, SMS shorthand, repeated letters, missing spaces.

Hard rules:
  * Tokens are only RENAMED or SPLIT, never dropped - negation words (mat, na, nahi, not...) always survive, so
    "OTP share karo" and "OTP share mat karo" stay different.
  * URLs, e-mail addresses and domain-like tokens are never touched.
"""
from __future__ import annotations

import re

# variant -> canonical (all lower-case)
VARIANTS = {
    "acct": "account", "accnt": "account", "acnt": "account", "acount": "account", "acunt": "account", "accout": "account", "a/c": "account",
    "blok": "block", "blck": "block", "blk": "block",
    "bnd": "band",
    "kro": "karo", "krdo": "kar do", "kardo": "kar do",
    "krein": "karein", "karen": "karein", "krien": "karein", "kren": "karein", "kijiye": "karein", "kijiyega": "karein",
    "krna": "karna", "krana": "karana",
    "jaega": "jayega", "jayga": "jayega", "jaiga": "jayega", "jayegaa": "jayega", "jaayega": "jayega", "jyega": "jayega",
    "jayegi": "jayegi", "jaegi": "jayegi",
    "apka": "aapka", "apki": "aapki", "apke": "aapke", "apko": "aapko", "aapko": "aapko",
    "nhi": "nahi", "nahin": "nahi", "nhin": "nahi", "nehi": "nahi",
    "wrna": "warna", "varna": "warna", "warnaa": "warna",
    "turat": "turant", "turrant": "turant", "turnt": "turant",
    "abi": "abhi", "abhii": "abhi", "jldi": "jaldi", "jaldii": "jaldi",
    "bhejen": "bhejein", "bhejain": "bhejein", "btao": "batao", "bataao": "batao", "btaao": "batao",
    "gya": "gaya", "gyaa": "gaya", "gyi": "gayi",
    "pls": "please", "plz": "please", "pleez": "please",
    "updt": "update", "updte": "update", "upadte": "update", "verfy": "verify", "varify": "verify",
    "lnk": "link", "clck": "click", "klik": "click", "clik": "click",
    "urgnt": "urgent", "urjent": "urgent",
    "lotry": "lottery", "lottry": "lottery", "lotary": "lottery",
    "rewrd": "reward", "rewad": "reward",
    "nmbr": "number",
    "aadhar": "aadhaar", "adhar": "aadhaar", "adhaar": "aadhaar",
    "khaata": "khata", "khta": "khata",
    "bijlee": "bijli", "bijali": "bijli",
    "inam": "inaam", "pese": "paise", "paisa": "paise",
    "freez": "freeze", "frez": "freeze",
}
_ACRONYM = [(re.compile(r"\bk\.?\s?y\.?\s?c\b\.?", re.I), "kyc"), (re.compile(r"\bo\.?\s?t\.?\s?p\b\.?", re.I), "otp"),
            (re.compile(r"\bu\.?\s?p\.?\s?i\b\.?", re.I), "upi")]
_PROTECT = re.compile(r"(\S*(?:://|www\.|@)\S*|\S+\.[a-z]{2,}/\S*)", re.I)
_WORD = re.compile(r"[A-Za-z][A-Za-z0-9/']*")
_ELONG = re.compile(r"([A-Za-z])\1{2,}")

# vocabulary for splitting run-together words ("accountband" -> "account band"); parts must be >= 3 letters
SPLIT_VOCAB = frozenset("""account band block kyc update otp upi pin aapka aapki aapke karo karein turant abhi link click card bank
khata paise bhejo batao share send verify lottery reward claim fees fee loan band hoga jayega warna nahi mat call number
refund parcel blocked suspend urgent""".split())


def split_concatenated(token: str, vocab=SPLIT_VOCAB) -> list[str] | None:
    """Return the parts if `token` is entirely made of >=2 vocabulary words, else None."""
    t = token.lower()
    if len(t) < 7 or t in vocab:
        return None
    best: list[list[str] | None] = [None] * (len(t) + 1)
    best[0] = []
    for i in range(1, len(t) + 1):
        for j in range(max(0, i - 12), i - 2):          # words of length >= 3
            if best[j] is not None and t[j:i] in vocab:
                cand = best[j] + [t[j:i]]
                if best[i] is None or len(cand) < len(best[i]):
                    best[i] = cand
    return best[-1] if best[-1] and len(best[-1]) >= 2 else None


def _fix_word(m: re.Match) -> str:
    w = m.group(0)
    low = w.lower()
    if low in VARIANTS:
        return VARIANTS[low]
    collapsed = _ELONG.sub(r"\1\1", w)                # pleaseee -> pleasee ; hellooo -> helloo
    low2 = collapsed.lower()
    if low2 in VARIANTS:
        return VARIANTS[low2]
    parts = split_concatenated(low2)
    return " ".join(parts) if parts else collapsed


def normalize_hinglish(text: str) -> str:
    """Normalise Roman-script text; leaves URLs, e-mails and non-Latin text untouched."""
    if not text:
        return ""
    pieces = _PROTECT.split(text)                       # odd indexes are protected
    out = []
    for i, piece in enumerate(pieces):
        if i % 2:
            out.append(piece)
            continue
        for rx, rep in _ACRONYM:
            piece = rx.sub(rep, piece)
        out.append(_WORD.sub(_fix_word, piece))
    return "".join(out)
