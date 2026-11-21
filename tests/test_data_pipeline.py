import json

import numpy as np
import pandas as pd
import pytest

from src.data import registry
from src.data.prepare import dataset_version
from src.data.splitting import make_splits, near_duplicate_groups
from src.models import registry as model_registry
from src.models.evaluation import calibration_report, compute_metrics, expected_calibration_error
from src.models.train_model import RECALL_FLOOR_FNR, _select


def test_near_duplicates_are_grouped_but_distinct_messages_are_not():
    msgs = ["Your account will be blocked, update KYC now at http://a.top/x",
            "Your account will be blocked, update KYC now at http://b.top/y",     # same template, other link
            "Rs 500 credited to your account via UPI",
            "Kal subah dukaan khulegi saaman le aana"]
    g = near_duplicate_groups(msgs, 0.85)
    assert g[0] == g[1] and len({g[0], g[2], g[3]}) == 3


def _frame(n_real=100, n_syn=100):
    rows = []
    for i in range(n_real):
        rows.append((f"real genuine note number {i} about farm work {i * 7}", "legitimate", 0, "real"))
        rows.append((f"real prize lottery claim urgent {i} pay fee {i * 13} now", "fraud", 1, "real"))
    for i in range(n_syn):
        rows.append((f"synthetic example {i} kyc blocked synthetic template {i * 3}", "fraud", 1, "synthetic"))
        rows.append((f"synthetic example {i} polite reminder synthetic template {i * 5}", "legitimate", 0, "synthetic"))
    return pd.DataFrame(rows, columns=["message", "label", "target", "provenance"])


def test_split_policy_keeps_synthetic_out_of_evaluation_when_real_data_is_enough():
    splits, info = make_splits(_frame(), seed=1)
    assert info["evaluation_status"] == "real_data"
    assert set(splits["validation"].provenance) == {"real"} and set(splits["test"].provenance) == {"real"}
    assert "synthetic" in set(splits["train"].provenance)
    assert all(v == 0 for v in info["group_overlap_between_splits"].values())


def test_split_is_flagged_preliminary_when_real_data_is_scarce():
    splits, info = make_splits(_frame(n_real=5, n_syn=80), seed=1)
    assert info["evaluation_status"] == "preliminary_synthetic_only" and "PRELIMINARY" in info["evaluation_note"]


def test_split_never_separates_a_near_duplicate_cluster():
    df = _frame(n_real=60, n_syn=0)
    dup = df.iloc[:30].copy()
    dup["message"] = dup.message + " ok"               # near-duplicates of 30 rows
    splits, info = make_splits(pd.concat([df, dup], ignore_index=True), seed=3)
    seen = {}
    for name, d in splits.items():
        for g in d.group:
            assert seen.setdefault(g, name) == name


def test_split_is_reproducible():
    a, _ = make_splits(_frame(), seed=5)
    b, _ = make_splits(_frame(), seed=5)
    assert list(a["test"].message) == list(b["test"].message)


def test_dataset_version_changes_with_content_not_order():
    df = _frame(10, 10).assign(label=lambda d: d.label)
    v1 = dataset_version(df)
    assert v1 == dataset_version(df.sample(frac=1, random_state=0))
    changed = df.copy()
    changed.loc[0, "label"] = "spam"
    assert dataset_version(changed) != v1


def test_registry_rejects_bad_provenance_and_detects_tampering(tmp_path):
    reg = tmp_path / "datasets.json"
    f = tmp_path / "d.csv"
    f.write_text("message,label\nhello there,legitimate\n", encoding="utf-8")
    with pytest.raises(registry.RegistryError):
        registry.register(registry.DatasetRecord("x", str(f), "me", "mit", "made_up"), reg)
    registry.register(registry.DatasetRecord("d1", str(f), "me", "cc0", "manually_verified"), reg)
    assert registry.get("d1", reg).rows == 1 and registry.verify("d1", reg)[0]
    f.write_text("message,label\nhello there,fraud\n", encoding="utf-8")
    ok, why = registry.verify("d1", reg)
    assert not ok and "changed" in why


def test_bundled_datasets_are_registered_as_synthetic():
    registry.ensure_builtin_records()
    recs = {r.id: r for r in registry.all_records()}
    assert recs["synthetic-demo-v1"].provenance == "synthetic" and recs["synthetic-hi-hinglish-v2"].provenance == "synthetic"
    assert all(r.provenance not in registry.EVALUATION_PROVENANCE for r in recs.values() if r.id.startswith("synthetic"))


# --------------------------- metrics & calibration ---------------------------
def test_ece_is_zero_for_perfectly_calibrated_and_large_for_overconfident():
    rng = np.random.default_rng(0)
    p = rng.uniform(0, 1, 5000)
    y = (rng.uniform(0, 1, 5000) < p).astype(int)
    assert expected_calibration_error(y, p, 10)[0] < 0.03
    assert expected_calibration_error(y, np.where(p > 0.5, 0.99, 0.01), 10)[0] > 0.2


def test_calibration_report_fields_and_brier():
    r = calibration_report([0, 1, 1, 0], [0.1, 0.9, 0.8, 0.2])
    assert abs(r["brier"] - np.mean([0.01, 0.01, 0.04, 0.04])) < 1e-9 and r["reliability"]


def test_metrics_include_fpr_fnr_and_auc():
    m = compute_metrics([0, 0, 1, 1], [0, 1, 1, 0], [0.1, 0.6, 0.9, 0.4])
    assert m["fpr"] == 0.5 and m["fnr"] == 0.5 and m["roc_auc"] == 0.75 and "pr_auc" in m


def _cand(pr, f2, fnr, cv=0.9, acc=0.5):
    return {"validation": {"pr_auc": pr, "f2": f2, "fnr": fnr, "accuracy": acc}, "cv_f2_mean": cv}


def test_selection_never_chases_accuracy_and_respects_the_recall_floor():
    cands = {"high_acc_but_misses_scams": _cand(0.99, 0.99, RECALL_FLOOR_FNR + 0.2, acc=0.999),
             "safer": _cand(0.90, 0.80, 0.05, acc=0.60)}
    assert _select(cands)[0] == "safer"
    ties = {"a": _cand(0.981, 0.90, 0.05, cv=0.80), "b": _cand(0.984, 0.90, 0.05, cv=0.85)}   # PR-AUC tie (<0.01) -> CV-F2 decides
    assert _select(ties)[0] == "b"


# --------------------------- model registry / versioning ---------------------------
def test_model_registry_archives_activates_and_rolls_back(tmp_path):
    reg, active, src = tmp_path / "reg", tmp_path / "active", tmp_path / "src"
    src.mkdir()
    (src / "model.joblib").write_bytes(b"m1"); (src / "calibrator.joblib").write_bytes(b"c1"); (src / "metrics.json").write_text("{}")
    model_registry.archive_and_activate("m-1", src, {"x": 1}, active, reg)
    (src / "model.joblib").write_bytes(b"m2"); (src / "calibrator.joblib").unlink()
    model_registry.archive_and_activate("m-2", src, {"x": 2}, active, reg)
    assert model_registry.active_id(reg) == "m-2" and (active / "model.joblib").read_bytes() == b"m2"
    assert not (active / "calibrator.joblib").exists()            # must not inherit the previous version's calibrator
    model_registry.activate_model("m-1", active, reg)
    assert (active / "model.joblib").read_bytes() == b"m1" and (active / "calibrator.joblib").exists()
    assert [m["model_id"] for m in model_registry.list_models(reg)] == ["m-1", "m-2"]
    with pytest.raises(FileNotFoundError):
        model_registry.activate_model("nope", active, reg)
