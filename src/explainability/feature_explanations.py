"""Feature-level explanations for the linear baselines (LR / SVM / Naive Bayes).

For a linear model, contribution_i = tfidf_i * weight_i is exactly the additive attribution SHAP's
LinearExplainer would give (zero baseline), so we compute it directly: no extra dependency.
"""
from __future__ import annotations

import numpy as np

from src.nlp.text_processing import FRIENDLY_TOKENS


def _weights(clf) -> np.ndarray | None:
    if hasattr(clf, "coef_"):
        return np.asarray(clf.coef_).ravel()
    if hasattr(clf, "feature_log_prob_"):   # MultinomialNB: log-likelihood ratio flagged vs legitimate
        return clf.feature_log_prob_[1] - clf.feature_log_prob_[0]
    return None


def top_features(pipeline, text: str, k: int = 8) -> dict:
    """Return {'toward_flagged': [...], 'toward_legitimate': [...]} for this message."""
    vec, clf = pipeline.named_steps["tfidf"], pipeline.named_steps["clf"]
    w = _weights(clf)
    X = vec.transform([text]).tocoo()
    if w is None or X.nnz == 0:
        return {"toward_flagged": [], "toward_legitimate": []}
    names = vec.get_feature_names_out()
    # combined word+char models: explain with human-readable WORD features only
    items = [(names[j].removeprefix("word__"), float(v * w[j])) for j, v in zip(X.col, X.data)
             if not str(names[j]).startswith("char__")]
    pos = sorted([i for i in items if i[1] > 0], key=lambda x: -x[1])[:k]
    neg = sorted([i for i in items if i[1] < 0], key=lambda x: x[1])[:k]
    fmt = lambda lst: [{"feature": f, "friendly": FRIENDLY_TOKENS.get(f, f), "contribution": round(c, 4)} for f, c in lst]
    return {"toward_flagged": fmt(pos), "toward_legitimate": fmt(neg)}


def global_importance(pipeline, k: int = 15) -> dict | None:
    vec, clf = pipeline.named_steps["tfidf"], pipeline.named_steps["clf"]
    w = _weights(clf)
    if w is None:
        return None
    names = np.array([str(n).removeprefix("word__") for n in vec.get_feature_names_out()])
    keep = np.array([not str(n).startswith("char__") for n in vec.get_feature_names_out()])
    w = np.where(keep, w, np.nan)
    order = np.argsort(np.nan_to_num(w, nan=0.0))
    order = order[keep[order]]
    f = lambda idx: [{"feature": names[i], "weight": round(float(w[i]), 4)} for i in idx]
    return {"toward_flagged": f(order[::-1][:k]), "toward_legitimate": f(order[:k])}
