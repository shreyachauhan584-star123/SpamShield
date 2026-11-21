"""Model loading: baseline (joblib, hash-verified) and optional lazily-loaded transformer.

Security: joblib/pickle can execute code when loaded. We therefore only load artifacts from the
project's own models/ directory and verify the SHA-256 recorded at training time. Never point
this loader at files from untrusted sources.
"""
from __future__ import annotations

import importlib.util
import json
from functools import lru_cache
from pathlib import Path

import joblib

from config import ADVANCED_DIR, BASELINE_MODEL_PATH, HF_ALLOW_DOWNLOAD, METRICS_PATH
from src.models.predict import BaselinePredictor
from src.utils.helpers import sha256_file


class ModelUnavailable(RuntimeError):
    pass


def load_metrics(path: str | Path = METRICS_PATH) -> dict | None:
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _verified_load(p: Path, verify_hash: bool):
    sidecar = p.with_name(p.name + ".sha256")
    if verify_hash:
        if not sidecar.exists():
            raise ModelUnavailable(f"{p.name}: checksum file is missing; refusing to load an unverified model.")
        if sidecar.read_text().strip() != sha256_file(p):
            raise ModelUnavailable(f"{p.name}: checksum mismatch; refusing to load a modified model file.")
    try:
        return joblib.load(p)
    except Exception as exc:  # noqa: BLE001
        raise ModelUnavailable(f"{p.name} could not be loaded ({type(exc).__name__}). Re-train it with the current library versions.") from exc


def load_baseline(path: str | Path = BASELINE_MODEL_PATH, verify_hash: bool = True) -> BaselinePredictor:
    p = Path(path)
    if not p.exists():
        raise ModelUnavailable("Model file not found. Run: python -m src.models.train_model")
    pipe = _verified_load(p, verify_hash)
    metrics = load_metrics(p.with_name("metrics.json")) or {}
    cal = None
    cal_status = "unavailable"
    cp = p.with_name("calibrator.joblib")
    if cp.exists():
        try:
            cal = _verified_load(cp, verify_hash)
            cal_status = metrics.get("calibration", {}).get("status", "preliminary_small_sample")
        except ModelUnavailable:
            cal = None            # a bad calibrator must not take the whole model down; raw score is used instead
    sel = metrics.get("selected")
    name = (metrics.get("candidates", {}).get(sel, {}).get("display_name")
            or metrics.get("models", {}).get(metrics.get("best_model", ""), {}).get("display_name")
            or type(pipe.named_steps["clf"]).__name__)
    return BaselinePredictor(pipe, name, calibrator=cal, calibration_status=cal_status, model_id=metrics.get("model_id"))


# ---------------- optional advanced model (never loaded unless requested) ----------------
def advanced_available(path: Path = ADVANCED_DIR) -> bool:
    return path.exists() and all(importlib.util.find_spec(m) is not None for m in ("torch", "transformers"))


class AdvancedPredictor:
    """Wraps a LOCAL fine-tuned sequence-classification checkpoint (e.g. MuRIL/IndicBERT/mBERT).

    Loaded lazily on first predict. By default `local_files_only=True`, so nothing is downloaded
    at startup; set GRAMSURAKSHA_HF_ALLOW_DOWNLOAD=1 to allow it. Not evaluated in this repo.
    """

    kind = "advanced"
    evaluated = False

    def __init__(self, path: Path = ADVANCED_DIR):
        self.path = Path(path)
        self.model_name = f"Transformer ({self.path.name}, not evaluated)"
        self._tok = self._model = None

    def _load(self):
        if self._model is None:
            import torch  # noqa: F401
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
            kw = {"local_files_only": not HF_ALLOW_DOWNLOAD}
            self._tok = AutoTokenizer.from_pretrained(self.path, **kw)
            self._model = AutoModelForSequenceClassification.from_pretrained(self.path, **kw).eval()

    def predict(self, text: str) -> dict:
        import torch
        self._load()
        enc = self._tok(text, return_tensors="pt", truncation=True, max_length=128)
        with torch.no_grad():
            probs = torch.softmax(self._model(**enc).logits, dim=-1)[0]
        labels = {int(i): str(n).lower() for i, n in self._model.config.id2label.items()}
        pos = next((i for i, n in labels.items() if n in {"flagged", "spam", "fraud", "suspicious", "label_1"}), len(labels) - 1)
        score = float(probs[pos])
        return {"available": True, "model_name": self.model_name, "kind": "advanced",
                "label": "flagged" if score >= 0.5 else "not_flagged", "score": score}


@lru_cache(maxsize=1)
def get_advanced() -> AdvancedPredictor | None:
    return AdvancedPredictor() if advanced_available() else None
