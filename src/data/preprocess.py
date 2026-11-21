"""Cleaning, de-duplication and reproducible splitting (leakage-safe: dedupe BEFORE splitting)."""
from __future__ import annotations

import pandas as pd
from sklearn.model_selection import train_test_split

from config import RANDOM_SEED, TEST_SIZE
from src.data.dataset_validation import validate_dataframe
from src.data.load_data import to_binary
from src.nlp.text_processing import normalize_for_model


def clean_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Validate, drop missing/unknown labels, remove duplicates and contradictory duplicates."""
    df, rep = validate_dataframe(df)
    if not rep.ok:
        raise ValueError("; ".join(rep.errors))
    removed = {"invalid_or_empty": rep.stats["rows_before_validation"] - len(df)}
    df = df.copy()
    df["target"] = df["label"].map(to_binary)
    df["_key"] = df["message"].map(normalize_for_model)
    # Contradictory duplicates (same text, different binary target) are ambiguous -> drop all copies.
    conflict = df.groupby("_key")["target"].transform("nunique") > 1
    removed["conflicting_duplicates"] = int(conflict.sum())
    df = df[~conflict]
    before = len(df)
    df = df.drop_duplicates(subset="_key", keep="first")
    removed["duplicates"] = before - len(df)
    df = df.drop(columns="_key").reset_index(drop=True)
    return df, removed


def split_dataset(df: pd.DataFrame, test_size: float = TEST_SIZE, seed: int = RANDOM_SEED):
    """Stratified, seeded split. Raises if a class is too small to stratify."""
    counts = df["target"].value_counts()
    if len(counts) < 2 or counts.min() < 2:
        raise ValueError("Need at least 2 examples of each class to split. Add more data.")
    return train_test_split(df, test_size=test_size, stratify=df["target"], random_state=seed)
