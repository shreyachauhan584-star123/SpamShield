"""Prediction wrapper around a fitted sklearn pipeline (+ optional calibrator)."""
from __future__ import annotations

from dataclasses import dataclass

from src.models.evaluation import model_scores


@dataclass
class BaselinePredictor:
    pipeline: object
    model_name: str
    kind: str = "baseline"
    evaluated: bool = True
    calibrator: object | None = None
    calibration_status: str = "unavailable"   # unavailable | preliminary_small_sample | validated | rejected_worse_than_raw
    model_id: str | None = None

    def predict(self, text: str) -> dict:
        raw = float(model_scores(self.pipeline, [text])[0])      # raw model score: NOT a probability
        label = int(self.pipeline.predict([text])[0])
        cal = None
        if self.calibrator is not None and self.calibration_status != "rejected_worse_than_raw":
            cal = float(self.calibrator.predict_proba([text])[0, 1])
        # Decisions use the calibrated probability only once calibration has been validated on enough independent data.
        decision = cal if (cal is not None and self.calibration_status == "validated") else raw
        return {
            "available": True, "model_name": self.model_name, "model_id": self.model_id, "kind": self.kind,
            "label": "flagged" if label == 1 else "not_flagged",
            "score": raw, "calibrated_probability": cal, "calibration_status": self.calibration_status,
            "decision_value": decision,
        }


def unavailable(reason: str) -> dict:
    return {"available": False, "model_name": None, "kind": None, "label": None, "score": None, "error": reason}
