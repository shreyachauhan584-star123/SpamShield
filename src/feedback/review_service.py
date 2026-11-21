"""Contributions (message text, separate explicit consent) and the administrator review workflow.

Nothing here trains a model. A contribution only reaches a dataset after a human accepts it AND an administrator
explicitly exports and registers it (dataset_export.py). Every administrative action is written to the audit log.
"""
from __future__ import annotations

import secrets
import sqlite3
from pathlib import Path

from config import DB_PATH
from src.data.load_data import VALID_LABELS, normalize_label
from src.data.splitting import near_duplicate_groups
from src.database.db import connect
from src.feedback.feedback_service import ConsentRequired, FeedbackStorageError
from src.services.privacy_service import CONSENT_VERSION, redact_for_storage, text_fingerprint
from src.utils.helpers import sha256_text, utc_now_iso
from src.utils.validators import validate_message

REVIEW_STATUSES = ("pending", "accepted", "rejected", "duplicate")


def audit(conn, actor: str, action: str, target_type: str | None = None, target_id=None, detail: str = "") -> None:
    conn.execute("INSERT INTO audit_log (ts, actor, action, target_type, target_id, detail) VALUES (?,?,?,?,?,?)",
                 (utc_now_iso(), actor, action, target_type, None if target_id is None else str(target_id), detail[:200]))


def submit_contribution(text: str, *, consent_contribute: bool, suggested_label: str | None = None, language: str | None = None,
                        db_path: str | Path = DB_PATH) -> dict:
    """Store a redacted example for review. Needs its OWN consent (not the feedback consent). Returns the redacted text,
    the id and a one-time deletion token (only a hash of the token is stored)."""
    if consent_contribute is not True:
        raise ConsentRequired("Contributing a message requires a separate, explicit consent.")
    clean = validate_message(text)
    stored = redact_for_storage(clean)
    label = normalize_label(suggested_label) if suggested_label else None
    token = secrets.token_urlsafe(16)
    try:
        with connect(db_path) as c:
            try:
                cur = c.execute(
                    """INSERT INTO contributions (created_at, message_text, text_sha256, token_sha256, language, suggested_label, consent_version)
                       VALUES (?,?,?,?,?,?,?)""",
                    (utc_now_iso(), stored, text_fingerprint(clean), sha256_text(token), (language or "")[:12] or None, label, CONSENT_VERSION))
            except sqlite3.IntegrityError:
                return {"id": None, "duplicate": True, "stored_text": stored, "token": None}
            audit(c, "user", "contribution_submitted", "contribution", cur.lastrowid, f"consent={CONSENT_VERSION}")
            return {"id": int(cur.lastrowid), "duplicate": False, "stored_text": stored, "token": token}
    except sqlite3.Error as exc:
        raise FeedbackStorageError("Could not store the contribution.") from exc


def delete_contribution(token: str, db_path: str | Path = DB_PATH) -> bool:
    """User-initiated deletion with the token shown at submission time (no account needed)."""
    if not token:
        return False
    with connect(db_path) as c:
        row = c.execute("SELECT id FROM contributions WHERE token_sha256 = ?", (sha256_text(token),)).fetchone()
        if not row:
            return False
        c.execute("DELETE FROM contributions WHERE id = ?", (row[0],))
        audit(c, "user", "contribution_deleted_by_user", "contribution", row[0])
        return True


def list_contributions(status: str = "pending", limit: int = 50, db_path: str | Path = DB_PATH) -> list[dict]:
    if status not in REVIEW_STATUSES:
        raise ValueError("unknown status")
    with connect(db_path) as c:
        rows = c.execute("""SELECT id, created_at, message_text, language, suggested_label, review_status, verified_label, reviewer, notes
                            FROM contributions WHERE review_status = ? ORDER BY id LIMIT ?""", (status, int(limit))).fetchall()
    keys = ("id", "created_at", "message_text", "language", "suggested_label", "review_status", "verified_label", "reviewer", "notes")
    return [dict(zip(keys, r)) for r in rows]


def _near_duplicate_of_accepted(c, text: str) -> int | None:
    acc = c.execute("SELECT id, message_text FROM contributions WHERE review_status='accepted'").fetchall()
    if not acc:
        return None
    groups = near_duplicate_groups([text] + [a[1] for a in acc], 0.92)
    for gid, (cid, _) in zip(groups[1:], acc):
        if gid == groups[0]:
            return cid
    return None


def review_contribution(contribution_id: int, decision: str, *, reviewer: str, verified_label: str | None = None, notes: str = "",
                        db_path: str | Path = DB_PATH) -> dict:
    """decision: accept | reject. Accepting needs a human-verified label; near-duplicates of accepted items are flagged."""
    if decision not in ("accept", "reject"):
        raise ValueError("decision must be accept or reject")
    if not reviewer or not reviewer.strip():
        raise ValueError("reviewer is required for the audit trail")
    label = normalize_label(verified_label) if verified_label else None
    if decision == "accept" and label not in VALID_LABELS:
        raise ValueError(f"accepting requires a verified label from {VALID_LABELS}")
    with connect(db_path) as c:
        row = c.execute("SELECT message_text, review_status FROM contributions WHERE id = ?", (contribution_id,)).fetchone()
        if not row:
            raise KeyError(contribution_id)
        status = "rejected"
        if decision == "accept":
            dup = _near_duplicate_of_accepted(c, row[0])
            status = "duplicate" if dup else "accepted"
        c.execute("UPDATE contributions SET review_status=?, verified_label=?, reviewer=?, reviewed_at=?, notes=? WHERE id=?",
                  (status, label if status == "accepted" else None, reviewer.strip()[:60], utc_now_iso(), (notes or "")[:300], contribution_id))
        audit(c, "admin", f"contribution_{status}", "contribution", contribution_id, f"reviewer={reviewer.strip()[:60]}")
        return {"id": contribution_id, "status": status}


def admin_delete_contribution(contribution_id: int, *, reviewer: str, db_path: str | Path = DB_PATH) -> bool:
    with connect(db_path) as c:
        n = c.execute("DELETE FROM contributions WHERE id = ?", (contribution_id,)).rowcount
        if n:
            audit(c, "admin", "contribution_deleted_by_admin", "contribution", contribution_id, f"reviewer={reviewer[:60]}")
        return bool(n)


def review_feedback_item(feedback_id: int, status: str, *, reviewer: str, db_path: str | Path = DB_PATH) -> bool:
    if status not in ("reviewed", "actioned", "dismissed"):
        raise ValueError("status must be reviewed, actioned or dismissed")
    with connect(db_path) as c:
        n = c.execute("UPDATE feedback SET review_status=?, reviewer=?, reviewed_at=? WHERE id=?", (status, reviewer[:60], utc_now_iso(), feedback_id)).rowcount
        if n:
            audit(c, "admin", f"feedback_{status}", "feedback", feedback_id, f"reviewer={reviewer[:60]}")
        return bool(n)


def list_feedback(limit: int = 100, only_open: bool = True, db_path: str | Path = DB_PATH) -> list[dict]:
    q = """SELECT id, created_at, feedback_type, predicted_level, message_category, language, comment, review_status
           FROM feedback {} ORDER BY id DESC LIMIT ?""".format("WHERE COALESCE(review_status,'new')='new'" if only_open else "")
    with connect(db_path) as c:
        rows = c.execute(q, (int(limit),)).fetchall()
    keys = ("id", "created_at", "feedback_type", "predicted_level", "message_category", "language", "comment", "review_status")
    return [dict(zip(keys, r)) for r in rows]


def audit_records(limit: int = 200, db_path: str | Path = DB_PATH) -> list[dict]:
    with connect(db_path) as c:
        rows = c.execute("SELECT id, ts, actor, action, target_type, target_id, detail FROM audit_log ORDER BY id DESC LIMIT ?", (int(limit),)).fetchall()
    return [dict(zip(("id", "ts", "actor", "action", "target_type", "target_id", "detail"), r)) for r in rows]
