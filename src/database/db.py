"""SQLite helpers with versioned migrations (PRAGMA user_version).

Deployment note: SQLite on an ephemeral filesystem (e.g. Streamlit Community Cloud) loses data on restart.
Point GRAMSURAKSHA_DB_PATH at a persistent volume, or see docs/DEPLOYMENT.md for the persistence options.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from config import DB_PATH

LEVELS_SQL = "('LOW','MEDIUM','HIGH','UNKNOWN')"

# Each migration takes a connection and upgrades from (index) to (index + 1).
def _m0_to_v1(conn: sqlite3.Connection) -> None:
    """Original V1 table (levels LOW/CAUTION/HIGH/UNCERTAIN)."""
    conn.execute("""CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
        verdict TEXT NOT NULL CHECK (verdict IN ('correct','incorrect')),
        predicted_level TEXT NOT NULL CHECK (predicted_level IN ('LOW','CAUTION','HIGH','UNCERTAIN')),
        model_name TEXT,
        corrected_label TEXT CHECK (corrected_label IS NULL OR corrected_label IN ('legitimate','suspicious','not_sure')))""")


def _m1_to_v2(conn: sqlite3.Connection) -> None:
    """V2 taxonomy: CAUTION->MEDIUM, UNCERTAIN->UNKNOWN (table is rebuilt because CHECK constraints cannot be altered)."""
    conn.execute("ALTER TABLE feedback RENAME TO feedback_v1")
    conn.execute(f"""CREATE TABLE feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
        verdict TEXT NOT NULL CHECK (verdict IN ('correct','incorrect')),
        predicted_level TEXT NOT NULL CHECK (predicted_level IN {LEVELS_SQL}),
        model_name TEXT,
        corrected_label TEXT CHECK (corrected_label IS NULL OR corrected_label IN ('legitimate','suspicious','not_sure')))""")
    conn.execute("""INSERT INTO feedback (id, created_at, verdict, predicted_level, model_name, corrected_label)
        SELECT id, created_at, verdict,
               CASE predicted_level WHEN 'CAUTION' THEN 'MEDIUM' WHEN 'UNCERTAIN' THEN 'UNKNOWN' ELSE predicted_level END,
               model_name, corrected_label FROM feedback_v1""")
    conn.execute("DROP TABLE feedback_v1")


def _m2_to_v3(conn: sqlite3.Connection) -> None:
    """V2 feedback: typed classification/explanation feedback + review workflow, contributions (separate consent), audit log."""
    for col, ddl in [("feedback_kind", "TEXT"), ("feedback_type", "TEXT"), ("message_category", "TEXT"), ("language", "TEXT"), ("comment", "TEXT"),
                     ("model_id", "TEXT"), ("rules_version", "TEXT"), ("review_status", "TEXT DEFAULT 'new'"), ("reviewed_at", "TEXT"), ("reviewer", "TEXT")]:
        conn.execute(f"ALTER TABLE feedback ADD COLUMN {col} {ddl}")
    conn.execute("""CREATE TABLE contributions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
        message_text TEXT NOT NULL,                      -- redacted; stored ONLY with the separate contribution consent
        text_sha256 TEXT NOT NULL UNIQUE,                -- duplicate detection
        token_sha256 TEXT NOT NULL UNIQUE,               -- lets the contributor delete it without an account
        language TEXT, suggested_label TEXT CHECK (suggested_label IS NULL OR suggested_label IN ('legitimate','promotional','spam','suspicious','fraud')),
        consent_version TEXT NOT NULL,
        review_status TEXT NOT NULL DEFAULT 'pending' CHECK (review_status IN ('pending','accepted','rejected','duplicate')),
        verified_label TEXT CHECK (verified_label IS NULL OR verified_label IN ('legitimate','promotional','spam','suspicious','fraud')),
        reviewer TEXT, reviewed_at TEXT, notes TEXT)""")
    conn.execute("""CREATE TABLE audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL,
        target_type TEXT, target_id TEXT, detail TEXT)""")                      # never holds message content
    conn.execute("CREATE INDEX idx_contrib_status ON contributions(review_status)")


MIGRATIONS = [_m0_to_v1, _m1_to_v2, _m2_to_v3]


def migrate(conn: sqlite3.Connection) -> int:
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    for i in range(version, len(MIGRATIONS)):
        # a pre-versioning V1 database already has the table: skip creating it again, but still run later steps
        if i == 0 and conn.execute("SELECT 1 FROM sqlite_master WHERE name='feedback'").fetchone():
            pass
        else:
            MIGRATIONS[i](conn)
        conn.execute(f"PRAGMA user_version = {i + 1}")
    return len(MIGRATIONS)


@contextmanager
def connect(path: str | Path = DB_PATH):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    new = not p.exists()
    conn = sqlite3.connect(p, timeout=5)
    try:
        if new:
            try:
                p.chmod(0o600)              # owner-only on POSIX (best effort; no-op semantics on Windows)
            except OSError:
                pass
        conn.execute("PRAGMA foreign_keys = ON")
        migrate(conn)
        yield conn
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        raise
    finally:
        conn.close()
