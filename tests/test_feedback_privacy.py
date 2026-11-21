import ast
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.database.db import connect
from src.feedback import dataset_export, review_service as rv
from src.feedback.feedback_service import (CLASSIFICATION_TYPES, EXPLANATION_TYPES, ConsentRequired, clean_comment, feedback_stats, save_feedback_v2)
from src.services import admin_auth, privacy_service as ps
from src.utils.logging_utils import RedactingFilter, redact_text
from src.utils.validators import InputValidationError

ROOT = Path(__file__).resolve().parents[1]
SMS = "Your KYC pending. OTP 482913 call 9876543210 acct 123456789012 mail me@x.com"


# --------------------------- feedback v2 ---------------------------
def test_all_six_feedback_types_are_stored_separately_for_classification_and_explanation(tmp_path):
    db = tmp_path / "f.db"
    for t in CLASSIFICATION_TYPES + EXPLANATION_TYPES:
        save_feedback_v2(t, "HIGH", consent=True, model_id="m-1", message_category="KYC_SCAM", language="en", db_path=db)
    with connect(db) as c:
        kinds = dict(c.execute("SELECT feedback_type, feedback_kind FROM feedback").fetchall())
    assert {k for k, v in kinds.items() if v == "classification"} == set(CLASSIFICATION_TYPES)
    assert {k for k, v in kinds.items() if v == "explanation"} == set(EXPLANATION_TYPES)
    assert feedback_stats(db)["by_review_status"] == {"new": 6}


def test_feedback_needs_consent_and_valid_values(tmp_path):
    db = tmp_path / "f.db"
    with pytest.raises(ConsentRequired):
        save_feedback_v2("false_alarm", "LOW", consent=False, db_path=db)
    for kw in ({"feedback_type": "nonsense", "predicted_level": "LOW"}, {"feedback_type": "false_alarm", "predicted_level": "SAFE"}):
        with pytest.raises(InputValidationError):
            save_feedback_v2(consent=True, db_path=db, **kw)
    assert not db.exists() or feedback_stats(db)["by_type"] == {}


def test_comments_are_optional_length_limited_and_redacted(tmp_path):
    assert clean_comment(None) is None and clean_comment("   ") is None
    assert "482913" not in clean_comment("my otp was 482913 and phone 9876543210") and "9876543210" not in clean_comment("call 9876543210")
    with pytest.raises(InputValidationError):
        clean_comment("x" * 501)
    db = tmp_path / "f.db"
    save_feedback_v2("missed_suspicious", "LOW", consent=True, comment="phone 9876543210 mail a@b.com", db_path=db)
    with connect(db) as c:
        stored = c.execute("SELECT comment FROM feedback").fetchone()[0]
    assert "9876543210" not in stored and "a@b.com" not in stored


def test_feedback_tables_never_contain_message_text(tmp_path):
    db = tmp_path / "f.db"
    save_feedback_v2("false_alarm", "HIGH", consent=True, model_name="m", db_path=db)
    with connect(db) as c:
        cols = {t: [r[1] for r in c.execute(f"PRAGMA table_info({t})")] for t in ("feedback", "audit_log")}
    assert not [col for cs in cols.values() for col in cs if col in ("message", "message_text", "text", "sms", "body", "url")]


# --------------------------- contributions & review ---------------------------
def test_contribution_needs_its_own_consent_and_is_redacted_before_storage(tmp_path):
    db = tmp_path / "f.db"
    with pytest.raises(ConsentRequired):
        rv.submit_contribution(SMS, consent_contribute=False, db_path=db)
    r = rv.submit_contribution(SMS, consent_contribute=True, suggested_label="fraud", language="en", db_path=db)
    for secret in ("482913", "9876543210", "123456789012", "me@x.com"):
        assert secret not in r["stored_text"]
    with connect(db) as c:
        row = c.execute("SELECT message_text, token_sha256 FROM contributions").fetchone()
    assert all(s not in row[0] for s in ("482913", "9876543210")) and r["token"] not in row[1] and len(row[1]) == 64   # only a token HASH is kept


def test_exact_duplicates_are_not_stored_twice(tmp_path):
    db = tmp_path / "f.db"
    a = rv.submit_contribution("Your KYC is pending, update now", consent_contribute=True, db_path=db)
    b = rv.submit_contribution("your kyc is pending,   update now", consent_contribute=True, db_path=db)
    assert a["id"] and b["duplicate"] and b["id"] is None


def test_user_can_delete_their_contribution_with_the_token(tmp_path):
    db = tmp_path / "f.db"
    r = rv.submit_contribution("some message to delete please", consent_contribute=True, db_path=db)
    assert not rv.delete_contribution("wrong-token", db) and rv.delete_contribution(r["token"], db) and not rv.list_contributions("pending", db_path=db)
    assert any(a["action"] == "contribution_deleted_by_user" for a in rv.audit_records(db_path=db))


def test_review_workflow_requires_reviewer_and_verified_label_and_flags_near_duplicates(tmp_path):
    db = tmp_path / "f.db"
    a = rv.submit_contribution("Your account will be blocked today, update KYC at the link now", consent_contribute=True, db_path=db)["id"]
    b = rv.submit_contribution("Your account will be blocked today, update KYC at the link now!!", consent_contribute=True, db_path=db)["id"]
    c = rv.submit_contribution("Kal subah dukaan khulegi saaman le aana", consent_contribute=True, db_path=db)["id"]
    with pytest.raises(ValueError):
        rv.review_contribution(a, "accept", reviewer="", verified_label="fraud", db_path=db)
    with pytest.raises(ValueError):
        rv.review_contribution(a, "accept", reviewer="r", verified_label=None, db_path=db)
    assert rv.review_contribution(a, "accept", reviewer="Asha", verified_label="fraud", db_path=db)["status"] == "accepted"
    assert rv.review_contribution(b, "accept", reviewer="Asha", verified_label="fraud", db_path=db)["status"] == "duplicate"
    assert rv.review_contribution(c, "reject", reviewer="Asha", db_path=db)["status"] == "rejected"
    assert [x["action"] for x in rv.audit_records(db_path=db) if x["actor"] == "admin"] .count("contribution_accepted") == 1


def test_export_contains_only_accepted_items_with_provenance_and_is_not_training(tmp_path):
    db = tmp_path / "f.db"
    ids = [rv.submit_contribution(t, consent_contribute=True, db_path=db)["id"] for t in ("Pay fee to claim your lottery prize now", "Meeting moved to four pm tomorrow")]
    rv.review_contribution(ids[0], "accept", reviewer="A", verified_label="fraud", db_path=db)    # second stays pending
    out = dataset_export.export_validated("A", tmp_path / "v.csv", db, register=False)
    text = (tmp_path / "v.csv").read_text(encoding="utf-8")
    assert out["rows"] == 1 and "lottery" in text and "Meeting moved" not in text and "manually_verified" in text
    assert any(a["action"] == "dataset_exported" for a in rv.audit_records(db_path=db))


def test_feedback_review_and_status_changes_are_audited(tmp_path):
    db = tmp_path / "f.db"
    fid = save_feedback_v2("false_alarm", "HIGH", consent=True, db_path=db)
    assert rv.review_feedback_item(fid, "reviewed", reviewer="A", db_path=db) and not rv.list_feedback(db_path=db)
    with pytest.raises(ValueError):
        rv.review_feedback_item(fid, "bogus", reviewer="A", db_path=db)


# --------------------------- retention / privacy ---------------------------
def test_retention_purge_deletes_only_expired_data_and_is_audited(tmp_path):
    db = tmp_path / "f.db"
    save_feedback_v2("false_alarm", "HIGH", consent=True, db_path=db)
    rv.submit_contribution("pending contribution example number one", consent_contribute=True, db_path=db)
    assert sum(ps.purge_expired(db).values()) == 0                                           # nothing is old yet
    future = datetime.now(timezone.utc) + timedelta(days=400)
    counts = ps.purge_expired(db, now=future)
    assert counts["feedback"] == 1 and counts["contributions_pending"] == 1
    assert any(a["action"] == "purge_expired" for a in rv.audit_records(db_path=db))


def test_redaction_and_privacy_summary():
    out = ps.redact_for_storage("OTP 4829 acct 123456789012 aadhaar 1234 5678 9012 call +91 98765 43210 x@y.in")
    assert not any(ch.isdigit() for ch in out.replace("[", "").replace("]", "")) or "[number]" in out
    for secret in ("4829", "123456789012", "5678", "x@y.in"):
        assert secret not in out
    s = ps.privacy_summary()
    assert s["stored_by_default"] == [] and "OTPs" in s["never_stored"] and "screenshots" in s["never_stored"]


def test_storage_status_reports_unconfirmed_persistence(tmp_path):
    st = ps.storage_status(tmp_path / "x" / "f.db")
    assert st["writable"] and st["declared_persistent"] is False and "ephemeral" in st["warning"]


def test_database_file_is_owner_only_on_posix(tmp_path):
    import os
    db = tmp_path / "f.db"
    save_feedback_v2("false_alarm", "LOW", consent=True, db_path=db)
    if os.name == "posix":
        assert oct(db.stat().st_mode & 0o777) == "0o600"


def test_backup_script_produces_a_consistent_copy(tmp_path):
    import importlib.util
    db = tmp_path / "f.db"
    save_feedback_v2("false_alarm", "LOW", consent=True, db_path=db)
    spec = importlib.util.spec_from_file_location("backup_db", ROOT / "scripts" / "backup_db.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    out = mod.backup(db, tmp_path / "bk", keep=2)
    assert sqlite3.connect(out).execute("SELECT COUNT(*) FROM feedback").fetchone()[0] == 1


def test_sql_injection_attempts_are_inert(tmp_path):
    db = tmp_path / "f.db"
    save_feedback_v2("false_alarm", "LOW", consent=True, model_name="x'); DROP TABLE feedback;--", comment="'; DELETE FROM audit_log; --", db_path=db)
    rv.submit_contribution("'); DROP TABLE contributions; -- long enough text", consent_contribute=True, db_path=db)
    with connect(db) as c:
        assert c.execute("SELECT COUNT(*) FROM feedback").fetchone()[0] == 1 and c.execute("SELECT COUNT(*) FROM contributions").fetchone()[0] == 1


# --------------------------- admin auth ---------------------------
def test_admin_is_disabled_without_configuration_and_has_no_default_password():
    assert not admin_auth.admin_enabled({}) and admin_auth.try_login("admin", env={}) == (False, "disabled")
    assert admin_auth.try_login("", env={}) == (False, "disabled")


def test_password_hashing_login_and_lockout():
    admin_auth.reset_lockout()
    h = admin_auth.hash_password("correct horse battery")
    assert h.startswith("pbkdf2_sha256$") and "correct horse" not in h and h != admin_auth.hash_password("correct horse battery")   # salted
    env = {"GRAMSURAKSHA_ADMIN_PASSWORD_HASH": h}
    assert admin_auth.try_login("correct horse battery", env, now=0.0) == (True, "ok")
    for i in range(admin_auth.MAX_FAILS - 1):
        assert admin_auth.try_login("wrong", env, now=1.0) == (False, "bad_credentials")
    assert admin_auth.try_login("wrong", env, now=1.0) == (False, "locked")
    assert admin_auth.try_login("correct horse battery", env, now=2.0) == (False, "locked")          # even the right password waits
    assert admin_auth.try_login("correct horse battery", env, now=1.0 + admin_auth.LOCK_SECONDS + 1) == (True, "ok")
    assert not admin_auth.verify_password("x", "garbage") and not admin_auth.verify_password("x", "md5$1$00$00")
    admin_auth.reset_lockout()


# --------------------------- logging / secrets audit ---------------------------
def test_log_records_are_redacted():
    import logging
    rec = logging.LogRecord("x", logging.INFO, "f", 1, "msg http://evil.top/a otp 482913 a@b.com", None, None)
    RedactingFilter().filter(rec)
    assert "evil.top" not in rec.msg and "482913" not in rec.msg and "a@b.com" not in rec.msg
    assert "[number]" in redact_text("code 123456")


def _py_files(*dirs):
    for d in dirs:
        yield from (ROOT / d).rglob("*.py")


def test_analysis_path_never_prints_or_logs_message_content():
    """Static audit: user-facing modules must not call print() or logging; CLI entry points are exempt."""
    bad = []
    for f in _py_files("src/services", "src/security", "src/nlp", "src/multimodal", "src/feedback", "src/explainability", "pages"):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "print":
                bad.append(f"{f.relative_to(ROOT)}:{node.lineno} print")
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "logging" and node.attr in ("info", "debug", "warning", "error", "exception"):
                bad.append(f"{f.relative_to(ROOT)}:{node.lineno} logging.{node.attr}")
    assert bad == []


def test_no_secrets_are_hardcoded():
    import re
    pat = re.compile(r"""(?i)(api[_-]?key|secret|password|token)\s*=\s*["'][A-Za-z0-9_\-]{12,}["']""")
    hits = [str(f.relative_to(ROOT)) for f in _py_files("src", "pages", "scripts", "app.py") if pat.search(f.read_text(encoding="utf-8"))]
    assert hits == []
    env = (ROOT / ".env.example").read_text()
    assert "THREAT_INTEL_API_KEY=\n" in env or env.rstrip().endswith("THREAT_INTEL_API_KEY=")
    assert ".env" in (ROOT / ".gitignore").read_text()
