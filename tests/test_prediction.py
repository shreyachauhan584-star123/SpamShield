import shutil

import pytest

from src.explainability.explain_prediction import highlight_html
from src.explainability.feature_explanations import global_importance, top_features
from src.models.evaluation import model_scores
from src.models.model_loader import ModelUnavailable, load_baseline, load_metrics
from src.models.train_model import build_pipeline
from src.data.load_data import load_demo_dataset
from src.data.preprocess import clean_dataframe, split_dataset
from tests.helpers import CASES, runtime, trained_dir


def test_artifacts_exist_and_metrics_are_real():
    d = trained_dir()
    for f in ("model.joblib", "model.joblib.sha256", "calibrator.joblib", "calibrator.joblib.sha256", "metrics.json", "metadata.json"):
        assert (d / f).exists()
    m = load_metrics(d / "metrics.json")
    assert m["schema_version"] == 2 and m["model_id"].startswith("m-") and m["dataset"]["version"].startswith("dsv-")
    assert m["is_demo_dataset"] is True and m["evaluation_status"] == "preliminary_synthetic_only"   # must be labelled preliminary
    algos = {c["algorithm"] for c in m["candidates"].values()}
    assert algos == {"naive_bayes", "logistic_regression", "linear_svm"}
    assert {c["features"] for c in m["candidates"].values()} >= {"word_1_2", "char_2_5", "word+char"}
    assert sum(c["is_v1_baseline"] for c in m["candidates"].values()) == 3        # V1 baselines kept for comparison
    for c in m["candidates"].values():
        for split in ("validation", "test"):
            assert {"precision", "recall", "f1", "f2", "accuracy", "fpr", "fnr", "roc_auc", "pr_auc", "confusion_matrix"} <= set(c[split])
    assert m["calibration"]["status"] in ("preliminary_small_sample", "validated", "rejected_worse_than_raw")
    assert {"brier", "ece", "reliability"} <= set(m["calibration"]["validation"]["calibrated"])
    assert set(m["per_language"]) >= {"en", "hi", "hinglish"}


def test_predictor_returns_score_in_range_for_many_inputs():
    p = runtime().baseline
    for text in list(CASES.values()) + ["", "   ", "आपका खाता बंद", "x" * 2000, "😀😀😀", "12345 67890"]:
        out = p.predict(text)
        assert out["available"] and 0.0 <= out["score"] <= 1.0 and out["label"] in ("flagged", "not_flagged")


def test_prediction_is_deterministic():
    p = runtime().baseline
    assert p.predict(CASES["kyc_block_en"]) == p.predict(CASES["kyc_block_en"])


def test_scam_text_scores_higher_than_personal_text():
    p = runtime().baseline
    assert p.predict("Your KYC is pending, account will be blocked, click the link now")["score"] > p.predict(CASES["personal"])["score"]


def test_training_is_reproducible():
    df, _ = clean_dataframe(load_demo_dataset())
    tr, te = split_dataset(df, 0.25, 42)
    scores = []
    for _ in range(2):
        pipe = build_pipeline("logistic_regression", C=1.0)
        pipe.fit(tr.message.tolist(), tr.target)
        scores.append(list(model_scores(pipe, te.message.tolist())))
    assert scores[0] == scores[1]


def test_tampered_or_missing_model_is_refused(tmp_path):
    d = trained_dir()
    with pytest.raises(ModelUnavailable):
        load_baseline(tmp_path / "missing.joblib")
    shutil.copy(d / "model.joblib", tmp_path / "model.joblib")
    with pytest.raises(ModelUnavailable):                       # no checksum file
        load_baseline(tmp_path / "model.joblib")
    shutil.copy(d / "model.joblib.sha256", tmp_path / "model.joblib.sha256")
    assert load_baseline(tmp_path / "model.joblib")             # intact -> loads
    with open(tmp_path / "model.joblib", "ab") as fh:
        fh.write(b"tamper")
    with pytest.raises(ModelUnavailable):
        load_baseline(tmp_path / "model.joblib")


def test_feature_explanations_only_use_words_in_the_message():
    p = runtime().baseline
    text = "Your KYC is pending, click the link now"
    feats = top_features(p.pipeline, text)
    vocab_text = text.lower()
    for f in feats["toward_flagged"] + feats["toward_legitimate"]:
        assert all(w in vocab_text or w.endswith("token") for w in f["feature"].split())
    assert global_importance(p.pipeline)["toward_flagged"]


def test_highlight_escapes_html():
    out = highlight_html("<script>alert(1)</script> share your OTP", [(32, 39)])
    assert "<script>" not in out and "&lt;script&gt;" in out and "<mark" in out
