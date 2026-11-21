"""Consent-based feedback. Classification feedback and explanation feedback are separate. No message text is stored here."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from config import DB_PATH
from src.database.db import connect
from src.services.privacy_service import redact_for_storage
from src.utils.helpers import utc_now_iso
from src.utils.validators import ALLOWED_CORRECTED, InputValidationError

CLASSIFICATION_TYPES = ("correct_fraud", "false_alarm", "missed_suspicious", "correct_legitimate")
EXPLANATION_TYPES = ("explanation_helpful", "explanation_not_helpful")
_VERDICT = {"correct_fraud": "correct", "correct_legitimate": "correct", "explanation_helpful": "correct",
            "false_alarm": "incorrect", "missed_suspicious": "incorrect", "explanation_not_helpful": "incorrect"}
LEVELS = ("LOW", "MEDIUM", "HIGH", "UNKNOWN")
MAX_COMMENT = 500


class ConsentRequired(PermissionError):
    pass


class FeedbackStorageError(RuntimeError):
    pass


def clean_comment(comment: str | None) -> str | None:
    if not comment or not comment.strip():
        return None
    c = "".join(ch for ch in comment if ch.isprintable() or ch in "\n\t").strip()
    if len(c) > MAX_COMMENT:
        raise InputValidationError("comment_too_long", f"Comment is longer than {MAX_COMMENT} characters.")
    return redact_for_storage(c)


def save_feedback_v2(feedback_type: str, predicted_level: str, *, consent: bool, model_id: str | None = None, model_name: str | None = None,
                     message_category: str | None = None, language: str | None = None, comment: str | None = None,
                     corrected_label: str | None = None, rules_version: str | None = None, db_path: str | Path = DB_PATH) -> int:
    if consent is not True:
        raise ConsentRequired("Feedback is stored only after explicit consent.")
    if feedback_type not in _VERDICT:
        raise InputValidationError("bad_feedback_type", "Unknown feedback type.")
    if predicted_level not in LEVELS:
        raise InputValidationError("bad_level", "Unknown risk level.")
    if corrected_label is not None and corrected_label not in ALLOWED_CORRECTED:
        raise InputValidationError("bad_corrected", "Unknown corrected label.")
    kind = "classification" if feedback_type in CLASSIFICATION_TYPES else "explanation"
    note = clean_comment(comment)
    try:
        with connect(db_path) as c:
            cur = c.execute(
                """INSERT INTO feedback (created_at, verdict, predicted_level, model_name, corrected_label, feedback_kind, feedback_type,
                   message_category, language, comment, model_id, rules_version, review_status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?, 'new')""",
                (utc_now_iso(), _VERDICT[feedback_type], predicted_level, (model_name or "")[:80] or None, corrected_label, kind, feedback_type,
                 (message_category or "")[:40] or None, (language or "")[:12] or None, note, (model_id or "")[:40] or None, (rules_version or "")[:12] or None))
            return int(cur.lastrowid)
    except sqlite3.Error as exc:
        raise FeedbackStorageError("Could not write feedback.") from exc


def feedback_stats(db_path: str | Path = DB_PATH) -> dict:
    try:
        with connect(db_path) as c:
            by_type = dict(c.execute("SELECT COALESCE(feedback_type,'legacy'), COUNT(*) FROM feedback GROUP BY 1").fetchall())
            by_status = dict(c.execute("SELECT COALESCE(review_status,'new'), COUNT(*) FROM feedback GROUP BY 1").fetchall())
        return {"by_type": by_type, "by_review_status": by_status}
    except sqlite3.Error:
        return {"by_type": {}, "by_review_status": {}}
