import io
import zipfile

import pandas as pd
import pytest

from src.content.samples import SAMPLES
from src.data.dataset_validation import validate_upload
from src.data.load_data import UCI_HELP, load_demo_dataset, load_uci_sms, normalize_label, to_binary
from src.data.preprocess import clean_dataframe, split_dataset
from src.nlp.language_detection import detect_language, with_override
from src.nlp.text_processing import normalize_for_model, token_count, tokenize
from tests.helpers import CASES


def test_normalize_placeholders_and_hinglish_preserved():
    out = normalize_for_model("Click http://bit.ly/x NOW! OTP 123456 call 9876543210 Rs.500")
    assert "urltoken" in out and "numtoken" in out and "phonetoken" in out and "rupeetoken" in out
    assert "123456" not in out and "9876543210" not in out
    assert "aapka khata band ho jayega" in normalize_for_model("Aapka KHATA band ho jayega")


def test_hindi_tokens_keep_matras_and_drop_danda():
    toks = tokenize("आपका बैंक खाता बंद कर दिया जाएगा।")
    assert "आपका" in toks and "बंद" in toks and "जाएगा" in toks
    assert all("।" not in t for t in toks)


def test_negation_words_are_not_removed():
    assert "not" in tokenize("do not share your otp") and "नहीं" in tokenize("यह सही नहीं है")


@pytest.mark.parametrize("bad", [None, 123, 4.5])
def test_normalize_non_string_is_safe(bad):
    assert normalize_for_model(bad) == ""


def test_normalize_is_idempotent_and_handles_empty():
    s = "Hello 123456 http://a.com"
    assert normalize_for_model(normalize_for_model(s)) == normalize_for_model(s)
    assert normalize_for_model("") == "" and token_count("") == 0


@pytest.mark.parametrize("raw,expected", [("ham", "legitimate"), (" SPAM ", "spam"), ("Legit", "legitimate"), ("fraud", "fraud"), ("financial_fraud", "fraud"), ("scam", "fraud"),
                                          ("promotional", "promotional"), ("???", None), (None, None)])
def test_label_normalisation(raw, expected):
    assert normalize_label(raw) == expected


def test_spam_is_not_silently_financial_fraud():
    assert normalize_label("spam") == "spam" != normalize_label("financial_fraud")
    assert [to_binary(x) for x in ("ham", "legitimate", "spam", "promotional", "suspicious", "financial_fraud", "fraud")] == [0, 0, 1, 1, 1, 1, 1]
    with pytest.raises(ValueError):
        to_binary("nonsense")


def test_load_uci_file_and_zip(tmp_path):
    body = 'ham\tOk lar... Joking wif u oni...\nspam\tFree entry in 2 a "wkly" comp to win FA Cup\n'
    f = tmp_path / "SMSSpamCollection"
    f.write_text(body, encoding="utf-8")
    df = load_uci_sms(f)
    assert list(df.label) == ["ham", "spam"] and '"wkly"' in df.message[1]
    z = tmp_path / "smsspamcollection.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("SMSSpamCollection", body)
    assert len(load_uci_sms(z)) == 2


def test_missing_uci_gives_instructions(tmp_path):
    with pytest.raises(FileNotFoundError) as e:
        load_uci_sms(tmp_path / "nope")
    assert "archive.ics.uci.edu" in str(e.value) and UCI_HELP.split(".")[0] in str(e.value)


def test_clean_dataframe_dedupes_drops_missing_and_conflicts():
    df = pd.DataFrame({"message": ["Hello there", "hello  there", "Win a PRIZE now", "Win a PRIZE now", None, "x", "Same text", "same text", "bad label row"],
                       "label": ["ham", "ham", "spam", "spam", "ham", "ham", "ham", "spam", "unknown"]})
    out, removed = clean_dataframe(df)
    assert removed["duplicates"] == 2          # "hello there" dup + "win a prize now" dup
    assert removed["conflicting_duplicates"] == 2   # "Same text" / "same text" disagree -> both dropped
    assert "Same text" not in set(out.message) and "bad label row" not in set(out.message)
    assert set(out.columns) >= {"message", "label", "target"}


def test_split_is_stratified_and_reproducible():
    df, _ = clean_dataframe(load_demo_dataset())
    a1, b1 = split_dataset(df, 0.25, 7)
    a2, b2 = split_dataset(df, 0.25, 7)
    assert list(b1.index) == list(b2.index)
    assert abs(b1.target.mean() - df.target.mean()) < 0.08
    assert not set(a1.message) & set(b1.message)   # no overlap -> no leakage


def test_split_requires_both_classes():
    df = pd.DataFrame({"message": ["a1 b", "c2 d", "e3 f"], "label": ["ham", "ham", "spam"]})
    df, _ = clean_dataframe(df)
    with pytest.raises(ValueError):
        split_dataset(df)


def test_upload_validation_rules():
    ok, rep = validate_upload("message,label\nhello there friend,ham\nwin prize now,spam\n".encode(), "a.csv")
    assert rep.ok and len(ok) == 2
    assert not validate_upload(b"x", "a.exe")[1].ok
    assert not validate_upload(b"a,b\n1,2\n", "a.csv")[1].ok                         # missing columns
    assert not validate_upload("message,label\nहै,ham\n".encode("utf-16"), "a.csv")[1].ok   # not utf-8
    assert not validate_upload(b"x" * (6 * 1024 * 1024), "a.csv")[1].ok               # too big
    _, rep = validate_upload(b"message,label\nhello there,ham\nfoo bar,weird\n", "a.csv")
    assert rep.ok and any("unknown label" in w for w in rep.warnings)
    assert not validate_upload(b"message,label\n", "a.csv")[1].ok                      # no rows


def test_demo_dataset_has_no_leakage_with_samples_or_cases():
    from src.data.load_data import load_synthetic_v2
    msgs = set(load_demo_dataset().message) | set(load_synthetic_v2().message)
    assert not msgs & set(SAMPLES.values())
    assert not msgs & set(CASES.values())


@pytest.mark.parametrize("text,code", [
    (CASES["kyc_block_en"], "en"), (CASES["kyc_hinglish"], "hinglish"), (CASES["block_hindi"], "hi"),
    ("आपका account बंद हो जाएगा, KYC update करें", "mixed"), ("வணக்கம் உங்கள் கணக்கு", "other"), ("ok", "unknown"), ("", "unknown")])
def test_language_detection(text, code):
    assert detect_language(text).code == code


def test_manual_language_override():
    auto = detect_language("ok")
    assert with_override(auto, "hi").code == "hi" and with_override(auto, "hi").source == "user"
    assert with_override(auto, "auto").code == auto.code
