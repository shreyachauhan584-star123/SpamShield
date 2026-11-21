"""V1-compatible feedback API (verdict correct/incorrect). New code should use src/feedback/feedback_service.py.
NEVER stores SMS text, numbers, URLs or any message-derived content."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from config import DB_PATH
from src.database.db import connect
from src.feedback.feedback_service import ConsentRequired, FeedbackStorageError  # re-exported (same classes)
from src.utils.helpers import utc_now_iso
from src.utils.validators import validate_feedback

__all__ = ["ConsentRequired", "FeedbackStorageError", "save_feedback", "feedback_summary"]


def save_feedback(verdict: str, predicted_level: str, model_name: str | None = None,
                  corrected_label: str | None = None, consent: bool = False,
                  db_path: str | Path = DB_PATH) -> int:
    if consent is not True:
        raise ConsentRequired("Feedback is stored only after explicit consent.")
    validate_feedback(verdict, predicted_level, corrected_label)
    try:
        with connect(db_path) as conn:
            cur = conn.execute(
                "INSERT INTO feedback (created_at, verdict, predicted_level, model_name, corrected_label, review_status) VALUES (?,?,?,?,?, 'new')",
                (utc_now_iso(), verdict, predicted_level, (model_name or "")[:80] or None, corrected_label))
            return int(cur.lastrowid)
    except sqlite3.Error as exc:
        raise FeedbackStorageError("Could not write feedback.") from exc


def feedback_summary(db_path: str | Path = DB_PATH) -> dict:
    try:
        with connect(db_path) as conn:
            return {v: n for v, n in conn.execute("SELECT verdict, COUNT(*) FROM feedback GROUP BY verdict").fetchall()}
    except sqlite3.Error:
        return {}
