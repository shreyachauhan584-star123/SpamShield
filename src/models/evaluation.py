"""Metric computation and plotting helpers. Never reports accuracy alone."""
from __future__ import annotations

import numpy as np
from sklearn.metrics import (
    accuracy_score, average_precision_score, brier_score_loss, classification_report, confusion_matrix,
    f1_score, fbeta_score, precision_recall_curve, precision_score, recall_score, roc_auc_score,
)

LABEL_NAMES = ["legitimate", "flagged"]


def model_scores(pipeline, texts) -> np.ndarray:
    """Return a 0..1 'model score' for the flagged class.

    This is a model score, NOT a calibrated probability of fraud. For LinearSVC (no predict_proba)
    it is a sigmoid of the decision function, which is only a monotone rescaling.
    """
    if hasattr(pipeline, "predict_proba"):
        return pipeline.predict_proba(texts)[:, 1]
    d = pipeline.decision_function(texts)
    return 1.0 / (1.0 + np.exp(-d))


def compute_metrics(y_true, y_pred, scores=None, max_pr_points: int = 60) -> dict:
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = (int(x) for x in cm.ravel())
    out = {
        "fpr": fp / (fp + tn) if (fp + tn) else None,   # false alarms among genuine messages
        "fnr": fn / (fn + tp) if (fn + tp) else None,   # missed scams among flagged messages
        "n": int(len(y_true)),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "f2": float(fbeta_score(y_true, y_pred, beta=2, zero_division=0)),
        "confusion_matrix": cm.tolist(),
        "classification_report": classification_report(y_true, y_pred, target_names=LABEL_NAMES, output_dict=True, zero_division=0),
    }
    if scores is not None and len(set(y_true)) == 2:
        p, r, _ = precision_recall_curve(y_true, scores)
        idx = np.linspace(0, len(p) - 1, min(max_pr_points, len(p))).astype(int)
        out["average_precision"] = out["pr_auc"] = float(average_precision_score(y_true, scores))
        out["roc_auc"] = float(roc_auc_score(y_true, scores))
        out["pr_curve"] = {"precision": p[idx].tolist(), "recall": r[idx].tolist()}
    return out


def evaluate_pipeline_on_dataframe(pipeline, df) -> dict:
    """Evaluate a trained pipeline on any cleaned dataframe with columns message, target."""
    texts = df["message"].tolist()
    scores = model_scores(pipeline, texts)
    return compute_metrics(df["target"].to_numpy(), pipeline.predict(texts), scores)


def confusion_matrix_figure(cm, title="Confusion matrix"):
    import matplotlib
    matplotlib.use("Agg", force=False)
    import matplotlib.pyplot as plt

    cm = np.array(cm)
    fig, ax = plt.subplots(figsize=(3.6, 3.0))
    ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(len(LABEL_NAMES)), LABEL_NAMES)
    ax.set_yticks(range(len(LABEL_NAMES)), LABEL_NAMES)
    for (i, j), v in np.ndenumerate(cm):
        ax.text(j, i, str(v), ha="center", va="center", color="white" if v > cm.max() / 2 else "black")
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual")
    ax.set_title(title, fontsize=10)
    fig.tight_layout()
    return fig


def expected_calibration_error(y_true, probs, bins: int = 10):
    """Return (ECE, reliability) with equal-width bins. reliability = [{bin, n, mean_pred, observed}]."""
    y, p = np.asarray(y_true, dtype=float), np.asarray(probs, dtype=float)
    edges = np.linspace(0, 1, bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1]), 0, bins - 1)
    ece, rel = 0.0, []
    for b in range(bins):
        m = idx == b
        if m.any():
            conf, acc = float(p[m].mean()), float(y[m].mean())
            ece += m.mean() * abs(conf - acc)
            rel.append({"bin": b, "n": int(m.sum()), "mean_pred": round(conf, 4), "observed": round(acc, 4)})
    return float(ece), rel


def calibration_report(y_true, probs, bins: int | None = None) -> dict:
    bins = bins or (5 if len(y_true) < 200 else 10)
    ece, rel = expected_calibration_error(y_true, probs, bins)
    return {"brier": float(brier_score_loss(y_true, probs)), "ece": ece, "bins": bins, "reliability": rel, "n": int(len(y_true))}


def reliability_figure(rel_raw, rel_cal, title="Reliability diagram"):
    import matplotlib
    matplotlib.use("Agg", force=False)
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(3.8, 3.4))
    ax.plot([0, 1], [0, 1], "k--", lw=1, label="perfect")
    for rel, name in ((rel_raw, "raw score"), (rel_cal, "calibrated")):
        if rel:
            ax.plot([r["mean_pred"] for r in rel], [r["observed"] for r in rel], "o-", label=name)
    ax.set_xlabel("predicted"); ax.set_ylabel("observed fraction flagged"); ax.set_title(title, fontsize=10); ax.legend(fontsize=7)
    fig.tight_layout()
    return fig
