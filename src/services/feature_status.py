"""One place that reports which optional features really work in this installation (shown on the admin page).
Never raises. Never reports a feature as available because it is merely configured."""
from __future__ import annotations

import importlib.util
import os

from config import ADVANCED_DIR, DB_PATH
from src.models.model_loader import advanced_available, load_metrics
from src.multimodal.ocr_service import ocr_status
from src.multimodal.speech_recognition import available_engines
from src.security.threat_intel import get_provider


def feature_status(runtime=None) -> dict:
    ocr = ocr_status()
    stt = available_engines()
    m = (runtime.metrics if runtime is not None else None) or load_metrics()
    try:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        db_ok, db_note = os.access(DB_PATH.parent, os.W_OK), str(DB_PATH)
    except OSError as exc:
        db_ok, db_note = False, type(exc).__name__
    adv_metrics = (ADVANCED_DIR.parent / "metrics.json").exists()
    return {
        "baseline_model": {"available": bool(runtime and runtime.baseline) if runtime is not None else None,
                           "model_id": (m or {}).get("model_id"), "evaluation_status": (m or {}).get("evaluation_status"),
                           "error": getattr(runtime, "baseline_error", None)},
        "ocr": ocr,
        "speech_input": {"available": any(e["available"] for e in stt), "engines": stt, "browser_dictation": "client-side; depends on the user's browser"},
        "speech_output": {"browser_tts": "client-side; depends on voices installed on the user's device",
                          "gtts_installed": importlib.util.find_spec("gtts") is not None, "gtts_needs_internet": True},
        "transformer": {"available": advanced_available(), "evaluated": adv_metrics,
                        "note": "Not offered to users unless installed AND evaluated; see docs/ML_PIPELINE.md"},
        "threat_intel": {"configured": get_provider() is not None, "default": "off (opt-in per analysis)"},
        "database": {"writable_directory": db_ok, "path": db_note, "persistence": "depends on the hosting platform; see docs/DEPLOYMENT.md"},
    }
