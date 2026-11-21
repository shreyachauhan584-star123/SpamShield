import importlib
import sqlite3
import sys
import types

import pytest

from src.database.feedback import ConsentRequired, FeedbackStorageError, feedback_summary, save_feedback
from src.services.analysis_service import analyze_sms
from src.services.speech_service import GTTSSpeech
from src.services.translation_service import missing_keys, tr
from src.utils.helpers import redact_sensitive
from src.utils.validators import InputValidationError, validate_message
from tests.helpers import runtime


@pytest.mark.parametrize("bad,code", [(None, "not_text"), (5, "not_text"), ("", "empty"), ("   \n\t ", "empty"), ("x" * 2001, "too_long")])
def test_invalid_messages_rejected(bad, code):
    with pytest.raises(InputValidationError) as e:
        validate_message(bad)
    assert e.value.code == code


def test_validate_strips_control_chars_but_keeps_unicode():
    assert validate_message("hi\x00 there\x07 आपका") == "hi there आपका"


@pytest.mark.parametrize("bad,code", [("", "empty"), (None, "not_text"), ("y" * 5000, "too_long")])
def test_analyze_returns_error_not_exception(bad, code):
    res = analyze_sms(bad, runtime=runtime())
    assert res == {"ok": False, "error_code": code}


def test_analyze_works_when_model_is_missing():
    from src.security.fraud_rules import RuleEngine
    from src.services.analysis_service import Runtime
    rt = Runtime(RuleEngine(), None, "model missing", None)
    res = analyze_sms("Your account will be blocked. Update KYC immediately.", runtime=rt)
    assert res["ok"] and res["ml"]["available"] is False and res["risk"]["level"] in ("MEDIUM", "HIGH")
    assert "note_model_unavailable" in res["risk"]["notes"]


def test_hinglish_hindi_and_emoji_do_not_crash():
    for t in ["Aapka khata band ho jayega turant KYC karein", "आपका खाता बंद होगा 😀", "🙂🙂🙂🙂🙂"]:
        assert analyze_sms(t, runtime=runtime())["ok"]


# --------------------------- feedback / privacy ---------------------------
def test_feedback_requires_explicit_consent(tmp_path):
    db = tmp_path / "f.db"
    with pytest.raises(ConsentRequired):
        save_feedback("correct", "LOW", consent=False, db_path=db)
    with pytest.raises(ConsentRequired):
        save_feedback("correct", "LOW", consent=None, db_path=db)
    assert not db.exists() or feedback_summary(db) == {}


def test_feedback_stores_no_message_content(tmp_path):
    db = tmp_path / "f.db"
    rid = save_feedback("incorrect", "HIGH", "Logistic Regression", "legitimate", consent=True, db_path=db)
    assert rid == 1 and feedback_summary(db) == {"incorrect": 1}
    cols = [r[1] for r in sqlite3.connect(db).execute("PRAGMA table_info(feedback)")]
    assert not {c for c in cols if c in ("message", "message_text", "text", "sms", "body", "url", "content")}   # no column can hold message content
    assert {"id", "created_at", "verdict", "predicted_level", "model_name", "corrected_label"} <= set(cols)


@pytest.mark.parametrize("args", [("maybe", "LOW", None), ("correct", "SAFE", None), ("incorrect", "LOW", "evil")])
def test_feedback_rejects_invalid_values(tmp_path, args):
    with pytest.raises(ValueError):
        save_feedback(args[0], args[1], None, args[2], consent=True, db_path=tmp_path / "f.db")


def test_feedback_db_errors_are_wrapped(tmp_path):
    with pytest.raises(FeedbackStorageError):
        save_feedback("correct", "LOW", consent=True, db_path=tmp_path)   # a directory is not a database


def test_redaction_masks_otp_and_account_numbers():
    out = redact_sensitive("OTP 482913 account 123456789012 ok")
    assert "482913" not in out and "123456789012" not in out


# --------------------------- translations ---------------------------
def test_locale_files_have_identical_keys():
    assert missing_keys() == {"missing_in_hi": set(), "missing_in_en": set()}


def test_translation_fallback_and_format():
    assert tr("err_too_long", "hi", max=2000).count("2000") == 1
    assert tr("no_such_key", "hi") == "no_such_key"
    assert tr("btn_analyze", "xx") == tr("btn_analyze", "en")


# --------------------------- speech ---------------------------
def _fake_gtts(monkeypatch_mod, behaviour):
    mod = types.ModuleType("gtts")

    class gTTS:
        def __init__(self, text, lang, tld, slow):
            if behaviour == "offline":
                raise ConnectionError("no internet")
            self.text = text

        def write_to_fp(self, fp):
            fp.write(b"ID3fake-audio")
    mod.gTTS = gTTS
    return mod


def test_speech_handles_missing_package_offline_and_success():
    saved = sys.modules.pop("gtts", None)
    try:
        sys.modules["gtts"] = None            # makes `import gtts` raise ImportError
        assert GTTSSpeech().synthesize("hello", "en").error == "gtts_missing"
        sys.modules["gtts"] = _fake_gtts(None, "offline")
        assert GTTSSpeech().synthesize("hello", "en").error == "network"
        sys.modules["gtts"] = _fake_gtts(None, "ok")
        svc = GTTSSpeech()
        r = svc.synthesize("नमस्ते", "hi")
        assert r.audio == b"ID3fake-audio" and svc.synthesize("नमस्ते", "hi") == r
        assert GTTSSpeech().synthesize("   ", "en").audio is None
    finally:
        if saved is None:
            sys.modules.pop("gtts", None)
        else:
            sys.modules["gtts"] = saved


def test_v1_feedback_database_is_migrated_to_v2_taxonomy(tmp_path):
    """A database created by GramSuraksha V1 (CAUTION/UNCERTAIN) must upgrade in place without losing rows."""
    db = tmp_path / "v1.db"
    conn = sqlite3.connect(db)
    conn.execute("""CREATE TABLE feedback (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
        verdict TEXT NOT NULL CHECK (verdict IN ('correct','incorrect')),
        predicted_level TEXT NOT NULL CHECK (predicted_level IN ('LOW','CAUTION','HIGH','UNCERTAIN')),
        model_name TEXT, corrected_label TEXT)""")
    conn.executemany("INSERT INTO feedback (created_at, verdict, predicted_level, model_name) VALUES ('t','correct',?,'m')",
                     [("CAUTION",), ("UNCERTAIN",), ("HIGH",)])
    conn.commit()
    conn.close()
    save_feedback("correct", "MEDIUM", "m", consent=True, db_path=db)   # forces migration, then accepts V2 values
    rows = sqlite3.connect(db).execute("SELECT predicted_level FROM feedback ORDER BY id").fetchall()
    assert [r[0] for r in rows] == ["MEDIUM", "UNKNOWN", "HIGH", "MEDIUM"]
    assert sqlite3.connect(db).execute("PRAGMA user_version").fetchone()[0] >= 2
