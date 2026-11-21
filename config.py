"""Central configuration for GramSuraksha AI.

No secrets live here. Anything sensitive (future API keys) is read from environment variables.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
EXTERNAL_DIR = DATA_DIR / "external"        # third-party datasets you download manually (never auto-downloaded)
SYNTHETIC_DIR = DATA_DIR / "synthetic"      # author-written illustrative data
VALIDATED_DIR = DATA_DIR / "validated"      # manually verified examples
TRAIN_DIR = DATA_DIR / "train"
VALIDATION_DIR = DATA_DIR / "validation"
TEST_DIR = DATA_DIR / "test"
METADATA_DIR = DATA_DIR / "metadata"        # dataset registry, versions, split manifests
RULES_PATH = DATA_DIR / "rules" / "fraud_rules.json"
MODELS_DIR = BASE_DIR / "models"
BASELINE_DIR = MODELS_DIR / "baseline"
ADVANCED_DIR = Path(os.getenv("GRAMSURAKSHA_ADV_MODEL_DIR", MODELS_DIR / "advanced" / "checkpoint"))
BASELINE_MODEL_PATH = BASELINE_DIR / "model.joblib"
METRICS_PATH = BASELINE_DIR / "metrics.json"

# --- Local MuRIL model configuration ---
MURIL_MODEL_DIR = Path(
    os.getenv("GRAMSURAKSHA_MURIL_DIR", BASE_DIR / "models" / "muril")
)
MURIL_MAX_LENGTH = int(os.getenv("GRAMSURAKSHA_MURIL_MAX_LENGTH", "128"))
MURIL_THRESHOLD = float(os.getenv("GRAMSURAKSHA_MURIL_THRESHOLD", "0.50"))

ENABLE_LEGACY_MULTICLASS = (
    os.getenv("GRAMSURAKSHA_ENABLE_LEGACY_MULTICLASS", "0")
    .strip()
    .lower() in ("1", "true", "yes")
)

DB_PATH = Path(os.getenv("GRAMSURAKSHA_DB_PATH", DATA_DIR / "feedback.db"))
UCI_DEFAULT_PATH = RAW_DIR / "SMSSpamCollection"
DEMO_DATASET_PATH = SYNTHETIC_DIR / "demo_sms_dataset.csv"
SYNTHETIC_V2_PATH = SYNTHETIC_DIR / "hindi_hinglish_synthetic_v2.csv"

# --- reproducibility / training -------------------------------------------------
RANDOM_SEED = 42
TEST_SIZE = 0.25
CV_FOLDS = 5
TFIDF_PARAMS = dict(ngram_range=(1, 2), max_features=20000, lowercase=True, sublinear_tf=True)

# --- input limits -----------------------------------------------------------------
MAX_SMS_CHARS = 2000          # longer input is rejected, not silently truncated
MAX_UPLOAD_MB = 5
MAX_UPLOAD_ROWS = 100_000
MIN_TOKENS_FOR_ASSESSMENT = 4  # shorter messages give too little evidence

# --- per-language evaluation gates (see docs/model_card.md) --------------------------
MIN_EVAL_SAMPLES_EVALUATED = 30   # >= this (and both classes present, non-demo data) => "evaluated"
MIN_EVAL_SAMPLES_LIMITED = 10     # >= this => "limited"; below => model is ignored for that language

# --- runtime flags (environment) -----------------------------------------------------
HF_ALLOW_DOWNLOAD = os.getenv("GRAMSURAKSHA_HF_ALLOW_DOWNLOAD", "0") == "1"  # never download at startup
TTS_SLOW = os.getenv("GRAMSURAKSHA_TTS_SLOW", "1") == "1"                     # slower speech for clarity
THREAT_INTEL_API_KEY = os.getenv("THREAT_INTEL_API_KEY")  # future integration point; unused today


@dataclass(frozen=True)
class RiskThresholds:
    """Configurable thresholds for the risk engine (documented in docs/model_card.md)."""

    ml_caution: float = 0.50   # model score at/above which the model "leans suspicious"
    ml_high: float = 0.85      # model score at/above which the model "strongly leans suspicious"
    caution_points: int = 2    # total evidence points for MEDIUM
    high_points: int = 6       # total evidence points for HIGH
    high_evidence_points: int = 5  # rule/URL-only points that alone justify HIGH
    category_cap: int = 4      # max points one indicator category can contribute
    strong_severity: int = 3


RISK_THRESHOLDS = RiskThresholds()

# --- multimodal limits (V2) -----------------------------------------------------------
MAX_IMAGE_MB = 5
MAX_IMAGE_PIXELS = 25_000_000
MIN_IMAGE_SIDE = 40
OCR_TIMEOUT_SECONDS = 20
OCR_LOW_CONFIDENCE = 60.0          # mean word confidence (0-100) below which the UI warns the user
MAX_AUDIO_MB = 5
MAX_AUDIO_SECONDS = 60
