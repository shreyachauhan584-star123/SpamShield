"""Privacy controls: redaction before storage, retention, deletion, and a description of what is processed/stored."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config import DB_PATH
from src.database.db import connect
from src.nlp.text_processing import normalize_for_model

CONSENT_VERSION = "contribution-consent-v1"
RETENTION_DAYS = {"feedback": 365, "contributions_pending": 90, "contributions_rejected": 30, "audit_log": 730}

_PHONE = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_DIGITS = re.compile(r"\d{4,}")
_AADHAAR = re.compile(r"(?<!\d)\d{4}[\s-]\d{4}[\s-]\d{4}(?!\d)")


def redact_for_storage(text: str) -> str:
    """Remove OTPs, phone/account/Aadhaar numbers and e-mail addresses before ANY message text is stored."""
    t = _AADHAAR.sub("[id-number]", text)
    t = _EMAIL.sub("[email]", t)
    t = _PHONE.sub("[phone]", t)
    return _DIGITS.sub("[number]", t)


def text_fingerprint(text: str) -> str:
    return hashlib.sha256(normalize_for_model(redact_for_storage(text)).encode("utf-8")).hexdigest()


def privacy_summary() -> dict:
    return {
        "processed_in_memory": ["SMS text you paste, speak or upload (screenshots are read in memory and not saved)"],
        "stored_by_default": [],
        "stored_with_feedback_consent": ["feedback type", "risk level shown", "message category", "language", "model/rules version", "optional short comment (digits redacted)"],
        "stored_with_separate_contribution_consent": ["the message text with numbers/phones/e-mails redacted (only if you choose to contribute it)"],
        "never_stored": ["OTPs", "PINs", "bank/Aadhaar/phone numbers", "screenshots", "audio", "your identity"],
        "retention_days": RETENTION_DAYS,
        "third_parties": {"gTTS (only if used)": "explanation text is sent to Google for audio", "threat intelligence (only if you opt in)": "link addresses are sent to the provider"},
    }


def purge_expired(db_path=DB_PATH, now: datetime | None = None) -> dict:
    """Apply the retention policy. Returns counts; writes an audit entry (no content)."""
    now = now or datetime.now(timezone.utc)
    cut = lambda d: (now - timedelta(days=d)).isoformat(timespec="seconds")
    with connect(db_path) as c:
        counts = {
            "feedback": c.execute("DELETE FROM feedback WHERE created_at < ?", (cut(RETENTION_DAYS["feedback"]),)).rowcount,
            "contributions_pending": c.execute("DELETE FROM contributions WHERE review_status='pending' AND created_at < ?", (cut(RETENTION_DAYS["contributions_pending"]),)).rowcount,
            "contributions_rejected": c.execute("DELETE FROM contributions WHERE review_status IN ('rejected','duplicate') AND created_at < ?", (cut(RETENTION_DAYS["contributions_rejected"]),)).rowcount,
            "audit_log": c.execute("DELETE FROM audit_log WHERE ts < ?", (cut(RETENTION_DAYS["audit_log"]),)).rowcount,
        }
        c.execute("INSERT INTO audit_log (ts, actor, action, target_type, target_id, detail) VALUES (?,?,?,?,?,?)",
                  (now.isoformat(timespec="seconds"), "system", "purge_expired", None, None, str(counts)))
    return counts


def storage_status(db_path: Path = DB_PATH) -> dict:
    """Is feedback storage usable here? (UI hides feedback/contribution forms when it is not.)"""
    import os
    d = Path(db_path).parent
    try:
        d.mkdir(parents=True, exist_ok=True)
        writable = os.access(d, os.W_OK)
    except OSError:
        writable = False
    persistent = os.getenv("GRAMSURAKSHA_DB_PERSISTENT", "0") == "1"
    return {"enabled": writable and os.getenv("GRAMSURAKSHA_STORAGE", "sqlite") != "none", "writable": writable, "path": str(db_path),
            "declared_persistent": persistent,
            "warning": None if persistent else "Storage is not declared persistent (GRAMSURAKSHA_DB_PERSISTENT=1). On hosts with an ephemeral disk, data is lost on restart."}
