"""Validation of labeled SMS datasets and uploaded CSV files (no unsafe parsing, size/row caps)."""
from __future__ import annotations

import io
from dataclasses import dataclass, field

import pandas as pd

from config import MAX_UPLOAD_MB, MAX_UPLOAD_ROWS
from src.data.load_data import VALID_LABELS, normalize_label


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors


def dataset_stats(df: pd.DataFrame) -> dict:
    lens = df["message"].astype(str).str.len()
    counts = df["label"].value_counts()
    flagged = int((~df["label"].isin(["legitimate"])).sum())
    legit = int(len(df) - flagged)
    ratio = (max(flagged, legit) / max(1, min(flagged, legit))) if len(df) else 0.0
    extra = {"binary_distribution": {"legitimate": legit, "flagged": flagged}, "imbalance_ratio": round(ratio, 2),
             "imbalanced": ratio > 3.0}
    if "provenance" in df.columns:
        extra["provenance"] = {k: int(v) for k, v in df["provenance"].value_counts().items()}
    return extra | {
        "rows": int(len(df)),
        "class_distribution": {k: int(v) for k, v in df["label"].value_counts().items()},
        "duplicate_messages": int(df["message"].duplicated().sum()),
        "missing_values": int(df[["message", "label"]].isna().sum().sum()),
        "message_length": {"min": int(lens.min()) if len(lens) else 0, "mean": float(lens.mean()) if len(lens) else 0.0, "max": int(lens.max()) if len(lens) else 0},
    }


def validate_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, ValidationReport]:
    """Check columns, normalise labels, drop unusable rows. Returns (cleaned_df, report)."""
    rep = ValidationReport()
    df = df.rename(columns={c: str(c).strip().lower() for c in df.columns})
    missing = {"message", "label"} - set(df.columns)
    if missing:
        rep.errors.append(f"Missing required column(s): {', '.join(sorted(missing))}. Expected: message, label.")
        return df, rep
    n0 = len(df)
    df = df.copy()
    df["message"] = df["message"].astype("string").str.strip()
    df["label"] = df["label"].map(normalize_label)
    bad_label = df["label"].isna() & df["message"].notna()
    if bad_label.any():
        rep.warnings.append(f"{int(bad_label.sum())} row(s) dropped: unknown label. Valid labels: {', '.join(VALID_LABELS)}.")
    empty = df["message"].isna() | (df["message"] == "")
    if empty.any():
        rep.warnings.append(f"{int(empty.sum())} row(s) dropped: empty message.")
    if "provenance" in df.columns:
        from src.data.registry import PROVENANCE
        badp = ~df["provenance"].isin(PROVENANCE)
        if badp.any():
            rep.errors.append(f"Invalid provenance value(s). Allowed: {', '.join(PROVENANCE)}.")
    df = df[~(df["label"].isna() | empty)].reset_index(drop=True)
    df["message"] = df["message"].astype(str)
    if len(df) == 0:
        rep.errors.append("No usable rows after validation.")
    elif df["label"].map(lambda x: x == "legitimate").nunique() < 2:
        rep.warnings.append("Dataset contains only one class (legitimate vs flagged); it cannot be used to train alone.")
    rep.stats = dataset_stats(df) if len(df) else {}
    rep.stats["rows_before_validation"] = n0
    return df, rep


def validate_upload(data: bytes, filename: str) -> tuple[pd.DataFrame, ValidationReport]:
    """Validate an uploaded CSV/TSV. Never executes content; only parses text."""
    rep = ValidationReport()
    empty = pd.DataFrame(columns=["message", "label"])
    if not filename.lower().endswith((".csv", ".tsv")):
        rep.errors.append("Only .csv or .tsv files are accepted.")
        return empty, rep
    if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
        rep.errors.append(f"File is larger than {MAX_UPLOAD_MB} MB.")
        return empty, rep
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        rep.errors.append("File must be UTF-8 encoded (needed for Hindi text).")
        return empty, rep
    sep = "\t" if filename.lower().endswith(".tsv") else ","
    try:
        df = pd.read_csv(io.StringIO(text), sep=sep, dtype=str, nrows=MAX_UPLOAD_ROWS + 1)
    except Exception as exc:  # noqa: BLE001 - parser errors vary; report a safe message
        rep.errors.append(f"Could not parse file: {type(exc).__name__}.")
        return empty, rep
    if len(df) > MAX_UPLOAD_ROWS:
        rep.errors.append(f"File has more than {MAX_UPLOAD_ROWS:,} rows.")
        return empty, rep
    return validate_dataframe(df)
