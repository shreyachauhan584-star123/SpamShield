"""Train, compare, select and calibrate baseline models (V2).

    python -m src.models.train_model                 # bundled synthetic data (+ UCI automatically if present)
    python -m src.models.train_model --no-uci
    python -m src.models.train_model --extra-csv my.csv --extra-provenance manually_verified

Pipeline: prepare dataset (clean, version, duplicate-aware split) -> for every (feature set x algorithm) run a
group-aware cross-validated grid search on TRAIN -> evaluate on VALIDATION -> select -> calibrate (cross-validated on
TRAIN, assessed on VALIDATION and TEST) -> report TEST once -> archive as a new model version.

Selection never uses accuracy alone and never uses the test split.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import time
from pathlib import Path

import joblib
import numpy as np
import sklearn
from sklearn.base import clone
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import fbeta_score, make_scorer
from sklearn.model_selection import GridSearchCV, StratifiedGroupKFold
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.svm import LinearSVC

from config import BASE_DIR, BASELINE_DIR, MODELS_DIR, RANDOM_SEED, TFIDF_PARAMS, CV_FOLDS
from src.data.prepare import prepare
from src.models import registry
from src.models.evaluation import calibration_report, compute_metrics, model_scores
from src.nlp.multilingual import per_language_metrics
from src.nlp.text_processing import TOKEN_PATTERN, normalize_for_model
from src.utils.helpers import sha256_file, utc_now_iso

MODEL_SPECS = {
    "naive_bayes": (lambda: MultinomialNB(), {"clf__alpha": [0.1, 0.3, 1.0]}),
    "logistic_regression": (
        lambda: LogisticRegression(max_iter=2000, class_weight="balanced", solver="liblinear", random_state=RANDOM_SEED),
        {"clf__C": [0.5, 1.0, 4.0, 10.0]},
    ),
    "linear_svm": (lambda: LinearSVC(class_weight="balanced", random_state=RANDOM_SEED), {"clf__C": [0.1, 0.5, 1.0, 2.0]}),
}
DISPLAY_NAMES = {"naive_bayes": "Multinomial Naive Bayes", "logistic_regression": "Logistic Regression", "linear_svm": "Linear SVM"}
FEATURE_KINDS = ("word_1", "word_1_2", "word_1_3", "char_2_5", "word+char")
V1_FEATURES = "word_1_2"          # the original V1 configuration: kept as the comparison baseline
RECALL_FLOOR_FNR = 0.15           # candidates missing more than 15% of flagged messages rank below the others
MIN_VALIDATION_FOR_CALIBRATION_CLAIM = 200


def _word(ngram, base):
    return TfidfVectorizer(preprocessor=normalize_for_model, token_pattern=TOKEN_PATTERN, **{**base, "ngram_range": ngram})


def make_features(kind: str, tfidf_params: dict | None = None):
    base = {**TFIDF_PARAMS, **(tfidf_params or {})}
    char = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), preprocessor=normalize_for_model, max_features=30000, sublinear_tf=True)
    return {
        "word_1": lambda: _word((1, 1), base), "word_1_2": lambda: _word((1, 2), base), "word_1_3": lambda: _word((1, 3), base),
        "char_2_5": lambda: char, "word+char": lambda: FeatureUnion([("word", _word((1, 2), base)), ("char", char)]),
    }[kind]()


def build_pipeline(name: str, features: str = V1_FEATURES, tfidf_params: dict | None = None, **clf_params) -> Pipeline:
    clf = MODEL_SPECS[name][0]()
    if clf_params:
        clf.set_params(**clf_params)
    return Pipeline([("tfidf", make_features(features, tfidf_params)), ("clf", clf)])


def _inference_ms(pipe, texts, repeats: int = 3) -> float:
    pipe.predict(texts[:3])
    t0 = time.perf_counter()
    for _ in range(repeats):
        for t in texts:
            pipe.predict([t])
    return (time.perf_counter() - t0) / (repeats * len(texts)) * 1000


def _git_commit() -> str | None:
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=BASE_DIR, capture_output=True, text=True, timeout=5)
        return r.stdout.strip() or None
    except Exception:  # noqa: BLE001
        return None


def _select(cands: dict) -> tuple[str, str]:
    """Multi-criteria selection on VALIDATION metrics (never accuracy alone, never the test set)."""
    def key(cid):
        v = cands[cid]["validation"]
        fnr = v["fnr"] if v["fnr"] is not None else 1.0
        return (fnr <= RECALL_FLOOR_FNR, round(v.get("pr_auc", 0.0), 2), round(v["f2"], 3), round(cands[cid]["cv_f2_mean"], 3), -fnr)
    best = max(cands, key=key)
    rule = (f"validation split; candidates with FNR <= {RECALL_FLOOR_FNR} first, then highest PR-AUC (differences < 0.01 are treated as ties), then F2, then CV-F2, then lowest FNR. "
            "Accuracy is reported but never used to choose.")
    return best, rule


def train_candidates(splits: dict, seed: int, log_path: Path | None = None, run_id: str = "", dataset_version: str = ""):
    train, val, test = splits["train"], splits["validation"], splits["test"]
    Xtr, ytr, gtr = train.message.tolist(), train.target.to_numpy(), train.group.to_numpy()
    Xva, yva = val.message.tolist(), val.target.to_numpy()
    Xte, yte = test.message.tolist(), test.target.to_numpy()
    folds = max(2, min(CV_FOLDS, int(np.bincount(ytr).min())))
    cv = list(StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=seed).split(Xtr, ytr, gtr))
    scoring = {"f1": "f1", "f2": make_scorer(fbeta_score, beta=2), "pr_auc": "average_precision", "roc_auc": "roc_auc"}
    cands, fitted = {}, {}
    for feats in FEATURE_KINDS:
        for algo, (_, grid) in MODEL_SPECS.items():
            gs = GridSearchCV(build_pipeline(algo, feats), grid, scoring=scoring, refit="f2", cv=cv, n_jobs=1)
            gs.fit(Xtr, ytr)
            best, i = gs.best_estimator_, gs.best_index_
            cid = f"{algo}|{feats}"
            cands[cid] = {
                "display_name": f"{DISPLAY_NAMES[algo]} ({feats})", "algorithm": algo, "features": feats,
                "is_v1_baseline": feats == V1_FEATURES,
                "best_params": {k.replace("clf__", ""): v for k, v in gs.best_params_.items()},
                "cv_folds": folds,
                **{f"cv_{m}_mean": float(gs.cv_results_[f"mean_test_{m}"][i]) for m in ("f1", "f2", "pr_auc", "roc_auc")},
                "cv_f2_std": float(gs.cv_results_["std_test_f2"][i]),
                "validation": compute_metrics(yva, best.predict(Xva), model_scores(best, Xva)),
                "test": compute_metrics(yte, best.predict(Xte), model_scores(best, Xte)),
                "inference_ms_per_message": float(_inference_ms(best, Xte[: min(15, len(Xte))])),
                "n_train": len(Xtr), "n_validation": len(Xva), "n_test": len(Xte),
            }
            fitted[cid] = best
            if log_path:
                log_path.parent.mkdir(parents=True, exist_ok=True)
                with open(log_path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"ts": utc_now_iso(), "run_id": run_id, "dataset_version": dataset_version, "seed": seed, "candidate": cid,
                                         "params": cands[cid]["best_params"], "cv_f2": cands[cid]["cv_f2_mean"],
                                         "val_pr_auc": cands[cid]["validation"].get("pr_auc"), "val_f2": cands[cid]["validation"]["f2"],
                                         "val_fnr": cands[cid]["validation"]["fnr"]}) + "\n")
    return cands, fitted, cv


def calibrate(best_pipe, splits: dict, cv):
    """Cross-validated calibration on TRAIN; assessed on VALIDATION and TEST (never fitted on them)."""
    train, val, test = splits["train"], splits["validation"], splits["test"]
    Xtr, ytr = train.message.tolist(), train.target.to_numpy()
    method = "isotonic" if len(Xtr) >= 1000 else "sigmoid"
    cal = CalibratedClassifierCV(estimator=clone(best_pipe), method=method, cv=cv, ensemble=True)
    cal.fit(Xtr, ytr)
    out = {"method": method, "fitted_on": "train (cross-validated)"}
    for name, d in (("validation", val), ("test", test)):
        X, y = d.message.tolist(), d.target.to_numpy()
        out[name] = {"raw": calibration_report(y, model_scores(best_pipe, X)), "calibrated": calibration_report(y, cal.predict_proba(X)[:, 1])}
    v = out["validation"]
    if v["calibrated"]["n"] < MIN_VALIDATION_FOR_CALIBRATION_CLAIM:
        out["status"] = "preliminary_small_sample"
    elif v["calibrated"]["brier"] <= v["raw"]["brier"]:
        out["status"] = "validated"
    else:
        out["status"] = "rejected_worse_than_raw"
    out["note"] = ("Calibrated probabilities are shown only in technical views. Decisions use them only when status == 'validated'; "
                   "'preliminary_small_sample' means fewer than %d validation messages." % MIN_VALIDATION_FOR_CALIBRATION_CLAIM)
    return cal, out


def run(args) -> dict:
    seed = getattr(args, "seed", RANDOM_SEED)
    out_dir = Path(args.output_dir)
    prep = prepare(seed, uci_path=getattr(args, "uci_path", None), extra_csv=getattr(args, "extra_csv", None),
                   extra_provenance=getattr(args, "extra_provenance", None), include_demo=not args.no_demo,
                   use_uci=not getattr(args, "no_uci", False), write=getattr(args, "write_splits", True))
    man, splits = prep["manifest"], prep["splits"]
    dsv = man["dataset_version"]
    run_id = "run-" + hashlib.sha256(f"{dsv}{seed}{time.time_ns()}".encode()).hexdigest()[:8]
    cands, fitted, cv = train_candidates(splits, seed, MODELS_DIR / "experiments" / "log.jsonl" if getattr(args, "log", True) else None, run_id, dsv)
    best_id, rule = _select(cands)
    best = fitted[best_id]
    cal, cal_info = calibrate(best, splits, cv)

    held = __import__("pandas").concat([splits["validation"], splits["test"]])
    held_pred = best.predict(held.message.tolist())
    per_lang = per_language_metrics(held.message.tolist(), held.target.tolist(), held_pred, demo_only=man["split"]["evaluation_status"] != "real_data")

    model_id = f"m-{time.strftime('%Y%m%d')}-{hashlib.sha256((dsv + best_id + str(seed)).encode()).hexdigest()[:8]}"
    out_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(best, out_dir / "model.joblib", compress=3)
    (out_dir / "model.joblib.sha256").write_text(sha256_file(out_dir / "model.joblib") + "\n")
    joblib.dump(cal, out_dir / "calibrator.joblib", compress=3)
    (out_dir / "calibrator.joblib.sha256").write_text(sha256_file(out_dir / "calibrator.joblib") + "\n")
    for algo in MODEL_SPECS:   # V1 baselines stay available for comparison
        cid = f"{algo}|{V1_FEATURES}"
        joblib.dump(fitted[cid], out_dir / f"{algo}.joblib", compress=3)

    metrics = {
        "schema_version": 2, "model_id": model_id, "run_id": run_id, "trained_at": utc_now_iso(), "random_seed": seed,
        "versions": {"python": platform.python_version(), "scikit-learn": sklearn.__version__, "git_commit": _git_commit()},
        "positive_class": "flagged (spam / promotional / suspicious / fraud)",
        "evaluation_status": man["split"]["evaluation_status"], "evaluation_note": man["split"]["evaluation_note"],
        "is_demo_dataset": man["split"]["evaluation_status"] != "real_data",
        "dataset": {"version": dsv, "stats": man["stats"], "datasets_used": man["datasets_used"], "splits": man["split"], "removed": man["removed_during_cleaning"]},
        "candidates": cands, "selected": best_id, "selection_rule": rule,
        "calibration": cal_info, "per_language": per_lang,
        "per_language_method": "predictions of the selected model on the held-out validation + test messages",
        "model_sha256": sha256_file(out_dir / "model.joblib"), "calibrator_sha256": sha256_file(out_dir / "calibrator.joblib"),
    }
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "metadata.json").write_text(json.dumps({"model_id": model_id, "dataset_version": dsv, "selected": best_id, "seed": seed,
                                                       "trained_at": metrics["trained_at"], "versions": metrics["versions"]}, indent=2), encoding="utf-8")
    if getattr(args, "register", True):
        s = cands[best_id]
        registry.archive_and_activate(model_id, out_dir, {
            "created_at": metrics["trained_at"], "dataset_version": dsv, "selected": best_id, "evaluation_status": metrics["evaluation_status"],
            "validation_pr_auc": s["validation"].get("pr_auc"), "validation_f2": s["validation"]["f2"], "calibration_status": cal_info["status"]},
            active_dir=out_dir)
    return metrics


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--uci-path"); ap.add_argument("--extra-csv"); ap.add_argument("--extra-provenance")
    ap.add_argument("--no-uci", action="store_true", help="ignore data/raw/SMSSpamCollection even if present")
    ap.add_argument("--no-demo", action="store_true", help="exclude the bundled synthetic datasets")
    ap.add_argument("--output-dir", default=str(BASELINE_DIR)); ap.add_argument("--seed", type=int, default=RANDOM_SEED)
    m = run(ap.parse_args(argv))
    print(f"model {m['model_id']} | dataset {m['dataset']['version']} | evaluation: {m['evaluation_status']}")
    print(f"selected: {m['selected']}  ({m['candidates'][m['selected']]['display_name']})")
    for cid, c in sorted(m["candidates"].items(), key=lambda kv: -kv[1]["validation"].get("pr_auc", 0)):
        v = c["validation"]
        print(f"  {cid:32s} val PR-AUC={v.get('pr_auc', 0):.3f} F2={v['f2']:.3f} FNR={v['fnr']:.3f} FPR={v['fpr']:.3f} cvF2={c['cv_f2_mean']:.3f}")
    print("calibration:", m["calibration"]["status"], {k: round(m["calibration"]["validation"][k]["brier"], 3) for k in ("raw", "calibrated")})
    print("per-language:", {k: (v["n"], v["status"]) for k, v in m["per_language"].items()})
    if m["is_demo_dataset"]:
        print("NOTE:", m["evaluation_note"])


if __name__ == "__main__":
    main()
