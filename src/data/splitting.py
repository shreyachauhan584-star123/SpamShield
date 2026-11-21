"""Leakage-resistant splitting.

* Near-duplicate messages (character n-gram cosine >= threshold) are clustered; a cluster is NEVER split across
  train / validation / test.
* Provenance policy: when enough real / manually-verified data exists, validation and test contain ONLY such data and
  synthetic/augmented rows go to training only. Otherwise the split is flagged `preliminary_synthetic_only` so the
  weakness is explicit and never silent.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import StratifiedGroupKFold

from config import RANDOM_SEED
from src.data.registry import EVALUATION_PROVENANCE
from src.nlp.text_processing import normalize_for_model

NEAR_DUP_THRESHOLD = 0.90
MIN_REAL_FOR_EVAL = 60          # real/verified rows needed before they alone form validation+test
MIN_REAL_PER_CLASS = 15


_NON_WORD = re.compile(r"[^\w\u0900-\u097F]+")


def _dup_key(text: str) -> str:
    """Normalised, punctuation-free text so "...now" and "...now!!" compare as equal."""
    return _NON_WORD.sub(" ", normalize_for_model(text)).strip()


def near_duplicate_groups(messages: list[str], threshold: float = NEAR_DUP_THRESHOLD, chunk: int = 1000) -> np.ndarray:
    """Cluster ids per message. Messages connected by cosine similarity >= threshold share a group."""
    n = len(messages)
    if n == 0:
        return np.array([], dtype=int)
    # no IDF: similarity must not depend on corpus statistics (IDF inflates unique n-grams, hiding true near-duplicates)
    X = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), preprocessor=_dup_key, use_idf=False, sublinear_tf=True).fit_transform(messages)
    rows, cols = [], []
    for s in range(0, n, chunk):
        sim = (X[s:s + chunk] @ X.T).tocoo()
        keep = (sim.data >= threshold) & (sim.row + s != sim.col)
        rows += list(sim.row[keep] + s)
        cols += list(sim.col[keep])
    g = csr_matrix((np.ones(len(rows)), (rows, cols)), shape=(n, n))
    return connected_components(g, directed=False)[1]


def _group_fold(y, groups, frac: float, seed: int):
    """Indices (rest, held_out) with ~frac held out, stratified by class and grouped."""
    k = max(2, round(1 / frac))
    sgkf = StratifiedGroupKFold(n_splits=k, shuffle=True, random_state=seed)
    rest, held = next(iter(sgkf.split(np.zeros(len(y)), y, groups)))
    return rest, held


def make_splits(df: pd.DataFrame, seed: int = RANDOM_SEED, val_frac: float = 0.2, test_frac: float = 0.2,
                threshold: float = NEAR_DUP_THRESHOLD) -> tuple[dict, dict]:
    """Return ({'train','validation','test'} DataFrames, info). `df` needs: message, target, provenance."""
    df = df.reset_index(drop=True).copy()
    df["group"] = near_duplicate_groups(df.message.tolist(), threshold)
    is_eval = df.provenance.isin(EVALUATION_PROVENANCE)
    real = df[is_eval]
    enough_real = len(real) >= MIN_REAL_FOR_EVAL and min(real.target.value_counts().reindex([0, 1]).fillna(0)) >= MIN_REAL_PER_CLASS

    if enough_real:
        pool, train_only = real.copy(), df[~is_eval].copy()
        # a near-duplicate cluster that contains any real row must not leak into training via synthetic copies
        leaky = set(train_only.group) & set(pool.group)
        train_only = train_only[~train_only.group.isin(leaky)]
        status = "real_data"
    else:
        pool, train_only, status = df.copy(), df.iloc[0:0].copy(), "preliminary_synthetic_only"

    y, g = pool.target.to_numpy(), pool.group.to_numpy()
    rest, test_idx = _group_fold(y, g, test_frac, seed)
    rest_df, test = pool.iloc[rest], pool.iloc[test_idx]
    rest2, val_idx = _group_fold(rest_df.target.to_numpy(), rest_df.group.to_numpy(), val_frac / (1 - test_frac), seed + 1)
    train, val = rest_df.iloc[rest2], rest_df.iloc[val_idx]
    train = pd.concat([train, train_only], ignore_index=True)

    splits = {"train": train.reset_index(drop=True), "validation": val.reset_index(drop=True), "test": test.reset_index(drop=True)}
    ov = {a + "/" + b: len(set(splits[a].group) & set(splits[b].group)) for a, b in (("train", "validation"), ("train", "test"), ("validation", "test"))}
    info = {
        "evaluation_status": status,
        "evaluation_note": ("Validation/test contain only real or manually verified messages." if status == "real_data" else
                            "PRELIMINARY: not enough real/verified data, so validation/test are drawn from the same (synthetic-dominated) pool. "
                            "Treat metrics as a pipeline check, not as evidence of real-world accuracy."),
        "near_duplicate_threshold": threshold, "seed": seed,
        "near_duplicate_clusters_with_multiple_messages": int((pd.Series(df.group).value_counts() > 1).sum()),
        "group_overlap_between_splits": ov,
        "sizes": {k: len(v) for k, v in splits.items()},
        "provenance_counts": {k: {p: int(c) for p, c in v.provenance.value_counts().items()} for k, v in splits.items()},
    }
    assert all(v == 0 for v in ov.values()), "near-duplicate leakage between splits"
    return splits, info
