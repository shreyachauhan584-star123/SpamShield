"""Dataset loading. Nothing here downloads data: the UCI file must be placed manually (see README)."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pandas as pd

from config import DEMO_DATASET_PATH, SYNTHETIC_V2_PATH, UCI_DEFAULT_PATH

# Canonical label taxonomy (V2). Definitions:
#   legitimate  genuine personal / transactional / service / awareness messages
#   promotional marketing from a business (unwanted maybe, not deceptive)
#   spam        unsolicited bulk messages (UCI "spam"; NOT assumed to be fraud)
#   suspicious  possible scam without clear fraud evidence
#   fraud       a clear attempt to defraud (phishing, OTP/KYC/UPI/lottery/advance-fee scams...)
# V1 names are kept as synonyms: ham -> legitimate, financial_fraud -> fraud.
LABEL_SYNONYMS = {
    "legitimate": "legitimate", "legit": "legitimate", "genuine": "legitimate", "ham": "legitimate",
    "promotional": "promotional", "promo": "promotional",
    "spam": "spam",
    "suspicious": "suspicious",
    "fraud": "fraud", "scam": "fraud", "financial_fraud": "fraud", "financial fraud": "fraud",
}
NON_FLAGGED = {"legitimate"}
VALID_LABELS = tuple(sorted(set(LABEL_SYNONYMS.values())))

UCI_HELP = (
    "UCI SMS Spam Collection not found. Download it manually from "
    "https://archive.ics.uci.edu/dataset/228/sms+spam+collection , unzip, and place the file "
    "'SMSSpamCollection' (or the zip itself) in data/raw/. Then re-run training."
)


def normalize_label(value) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return LABEL_SYNONYMS.get(str(value).strip().lower())


def to_binary(label: str) -> int:
    """1 = flagged (spam / promotional / suspicious / fraud), 0 = legitimate. Accepts V1 names (ham, financial_fraud)."""
    canonical = normalize_label(label)
    if canonical is None:
        raise ValueError(f"Unknown label {label!r}")
    return 0 if canonical in NON_FLAGGED else 1


def load_uci_sms(path: str | Path = UCI_DEFAULT_PATH) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        zp = path.with_name("smsspamcollection.zip")
        path = zp if zp.exists() else path
    if not path.exists():
        raise FileNotFoundError(UCI_HELP)
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as zf:
            info = zf.getinfo("SMSSpamCollection")  # fixed member name; no path traversal
            if info.file_size > 20 * 1024 * 1024:
                raise ValueError("Unexpectedly large member in zip.")
            raw = zf.read(info)
    else:
        raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    df = pd.read_csv(io.StringIO(text), sep="\t", header=None, names=["label", "message"], quoting=3, dtype=str)
    df["source"] = "uci"
    df["provenance"] = "real"
    df["dataset_id"] = "uci-sms-spam-collection"
    return df


def load_demo_dataset(path: str | Path = DEMO_DATASET_PATH, dataset_id: str = "synthetic-demo-v1") -> pd.DataFrame:
    """Bundled synthetic data (provenance = synthetic)."""
    df = pd.read_csv(path, dtype=str, encoding="utf-8")
    df["source"] = "synthetic"
    df["provenance"] = "synthetic"
    df["dataset_id"] = dataset_id
    return df


def load_synthetic_v2() -> pd.DataFrame:
    return load_demo_dataset(SYNTHETIC_V2_PATH, "synthetic-hi-hinglish-v2")


def load_labeled_csv(path: str | Path, provenance: str | None = None, dataset_id: str | None = None) -> pd.DataFrame:
    """Load a user-supplied labelled CSV. Provenance must be declared (argument or a `provenance` column)."""
    from src.data.dataset_validation import validate_upload
    from src.data.registry import check_provenance

    p = Path(path)
    df, report = validate_upload(p.read_bytes(), p.name)
    if not report.ok:
        raise ValueError("; ".join(report.errors))
    if "provenance" not in df.columns:
        if provenance is None:
            raise ValueError("Declare the provenance of this file (real, manually_verified, synthetic, augmented).")
        df["provenance"] = check_provenance(provenance)
    df["source"] = "custom"
    df["dataset_id"] = dataset_id or f"custom-{p.stem}"
    return df


def load_training_data(uci_path=None, extra_csv=None, include_demo=True, use_uci=True,
                       extra_provenance: str | None = None) -> pd.DataFrame:
    """Combine registered sources. Every row carries `source`, `provenance`, `dataset_id`."""
    frames = []
    uci = Path(uci_path) if uci_path else UCI_DEFAULT_PATH
    try:
        if use_uci:
            frames.append(load_uci_sms(uci))
    except FileNotFoundError:
        if uci_path:  # explicitly requested but missing -> error
            raise
    if include_demo:
        frames += [load_demo_dataset(), load_synthetic_v2()]
    if extra_csv:
        frames.append(load_labeled_csv(extra_csv, extra_provenance))
    if not frames:
        raise FileNotFoundError("No training data available. " + UCI_HELP)
    return pd.concat(frames, ignore_index=True)
