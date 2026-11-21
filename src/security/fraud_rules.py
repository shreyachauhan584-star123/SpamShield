"""Configurable regex rule engine. Rules live in data/rules/fraud_rules.json."""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from config import MAX_SMS_CHARS, RULES_PATH
from src.nlp.contextual_analysis import awareness_context, is_negated
from src.nlp.hindi_normalization import normalize_script

_FLAGS = re.IGNORECASE | re.UNICODE | re.DOTALL
_GUARD_WINDOW = 30


@dataclass(frozen=True)
class Indicator:
    rule_id: str
    category: str
    severity: int            # 1 low, 2 medium, 3 high
    matched_text: str
    span: tuple[int, int]
    explanation: dict        # {"en":..., "hi":...}
    recommendation: dict
    source: str = "rule"     # "rule" or "url"
    pattern: str = ""
    normalized_match: bool = False   # matched only after spelling normalisation (no exact span in the original)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["span"] = list(self.span)
        return d


@dataclass
class RuleScan:
    indicators: list[Indicator] = field(default_factory=list)
    benign: list[dict] = field(default_factory=list)
    suppressed: list[dict] = field(default_factory=list)   # matches removed for a documented reason (traceability)
    awareness: bool = False
    rules_version: str = ""


class RuleEngine:
    def __init__(self, rules: dict | None = None, path: str | Path = RULES_PATH):
        cfg = rules if rules is not None else json.loads(Path(path).read_text(encoding="utf-8"))
        self.version = str(cfg.get("version", "0"))
        self.rules = []
        for r in cfg["rules"]:
            self.rules.append({
                **r,
                "_pats": [re.compile(p, _FLAGS) for p in r["patterns"]],
                "_guard": re.compile(r["negation_guard"], _FLAGS) if r.get("negation_guard") else None,
                "_suppress": re.compile(r["suppress_if"], _FLAGS) if r.get("suppress_if") else None,
            })
        self._by_id = {r["id"]: r for r in self.rules}
        self.benign_rules = []
        for b in cfg.get("benign_contexts", []):
            self.benign_rules.append({
                **b,
                "_pats": [re.compile(p, _FLAGS) for p in b["patterns"]],
                "_req": re.compile(b["requires"], _FLAGS) if b.get("requires") else None,
            })

    def scan(self, text: str, has_links: bool = False) -> RuleScan:
        """Scan the original text, then (for spelling variants) its normalised form.

        Matches under negation are ignored for `negatable` rules ("do not share your OTP", "OTP share mat karna").
        In a fraud-AWARENESS message ("Beware! Never share your OTP"), matches are suppressed unless an *actionable*
        request (credential/payment/app request), a phone number to call or a link is also present.
        """
        text = (text or "")[: MAX_SMS_CHARS * 2]
        scan = RuleScan(rules_version=self.version)
        variants = [(text, False)]
        norm = normalize_script(text)
        if norm != text:
            variants.append((norm, True))
        found: dict[str, Indicator] = {}
        for r in self.rules:
            for vtext, is_norm in variants:
                if r["id"] in found:
                    break
                if r["_suppress"] and r["_suppress"].search(vtext):
                    continue
                hit = self._first_match(r, vtext)
                if hit:
                    m, pat = hit
                    found[r["id"]] = Indicator(
                        r["id"], r["category"], int(r["severity"]), m.group(0)[:120],
                        (0, 0) if is_norm else (m.start(), m.end()),
                        r["explanation"], r["recommendation"], "rule", pat, normalized_match=is_norm)
        indicators = list(found.values())

        scan.awareness = awareness_context(text)
        if scan.awareness:
            actionable = has_links or any(self._by_id[i.rule_id].get("actionable") for i in indicators)
            if not actionable:
                scan.suppressed = [{"rule_id": i.rule_id, "reason": "awareness_context", "matched_text": i.matched_text} for i in indicators]
                indicators = []
        scan.indicators = indicators
        for b in self.benign_rules:
            if b["_req"] and not b["_req"].search(text):
                continue
            for p in b["_pats"]:
                m = p.search(text)
                if m:
                    scan.benign.append({"rule_id": b["id"], "matched_text": m.group(0)[:80], "explanation": b["explanation"]})
                    break
        if scan.awareness and not any(b["rule_id"] == "B003" for b in scan.benign):
            scan.benign.append({"rule_id": "B003", "matched_text": "", "explanation": {
                "en": "The message looks like a fraud-awareness tip that warns you not to share secrets.",
                "hi": "संदेश ठगी से बचाव की सलाह जैसा लगता है, जिसमें गोपनीय जानकारी न देने को कहा गया है।"}})
        return scan

    @staticmethod
    def _first_match(rule: dict, text: str):
        for pat in rule["_pats"]:
            for m in pat.finditer(text):
                if rule["_guard"] is not None:
                    window = text[max(0, m.start() - _GUARD_WINDOW): m.start()]
                    if rule["_guard"].search(window):
                        continue  # e.g. "do not share your OTP" is a warning, not a request
                if rule.get("negatable") and is_negated(text, m.start(), m.end()):
                    continue
                return m, pat.pattern
        return None
