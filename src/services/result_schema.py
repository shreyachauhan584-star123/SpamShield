"""Structured analysis result + validation (stdlib dataclasses; no extra dependency).

Invariants enforced by `validate_result` (and tested):
  * risk_level in LOW / MEDIUM / HIGH / UNKNOWN; message_category from the documented taxonomy
  * HIGH is backed by non-model evidence; LOW carries no strong (severity 3) indicator
  * every explanation points at real evidence (a rule/URL indicator, the model, a note or a benign context)
  * `confidence` is None unless the calibration was validated; scores are never presented as probabilities
  * URLs are never opened or resolved
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from src.security.categories import VALID_CATEGORIES

SCHEMA_VERSION = "2.0"
RISK_LEVELS = ("LOW", "MEDIUM", "HIGH", "UNKNOWN")


@dataclass
class Explanation:
    ref: str                  # rule id (R004, U002...), "model", "note:<key>", "benign:<id>"
    kind: str                 # rule | url | model | note | benign
    text: dict


@dataclass
class Action:
    text: dict
    source: str               # rule id | "level" | "general"


@dataclass
class AnalysisResult:
    risk_level: str
    message_category: str
    category_name: dict
    detected_language: dict
    model_prediction: dict
    rule_evidence: list = field(default_factory=list)
    url_findings: list = field(default_factory=list)
    explanations: list = field(default_factory=list)
    recommended_actions: list = field(default_factory=list)
    confidence: dict | None = None
    uncertainty: dict = field(default_factory=dict)
    rules_version: str = ""
    threat_intel: dict = field(default_factory=lambda: {"used": False})
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict:
        return asdict(self)


def validate_result(r: dict) -> list[str]:
    """Return a list of violations (empty = valid)."""
    errs = []
    if r.get("risk_level") not in RISK_LEVELS:
        errs.append("invalid risk_level")
    if r.get("message_category") not in VALID_CATEGORIES:
        errs.append("invalid message_category")
    evidence = list(r.get("rule_evidence", [])) + [i for u in r.get("url_findings", []) for i in u.get("indicators", [])]
    ids = {e["rule_id"] for e in evidence}
    if r.get("risk_level") == "HIGH" and not evidence:
        errs.append("HIGH without rule/URL evidence")
    if r.get("risk_level") == "LOW" and any(e["severity"] >= 3 for e in evidence):
        errs.append("LOW with a strong indicator")
    for ex in r.get("explanations", []):
        ok = (ex["ref"] in ids or ex["ref"] == "model" or ex["ref"].startswith(("note:", "benign:")))
        if not ok or not ex["text"].get("en") or not ex["text"].get("hi"):
            errs.append(f"untraceable or untranslated explanation: {ex.get('ref')}")
    for a in r.get("recommended_actions", []):
        if not a["text"].get("en") or not a["text"].get("hi") or not a.get("source"):
            errs.append("incomplete action")
    cal = r.get("model_prediction", {}).get("calibration_status")
    if r.get("confidence") is not None and cal != "validated":
        errs.append("confidence reported without validated calibration")
    for u in r.get("url_findings", []):
        if u.get("opened") or u.get("resolved"):
            errs.append("URL was opened or resolved")
    return errs
