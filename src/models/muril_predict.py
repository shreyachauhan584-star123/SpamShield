"""Local-only inference adapter for the fine-tuned binary MuRIL checkpoint.

The checkpoint is expected at ``models/muril`` and is never downloaded at runtime.
MuRIL is the only neural binary classifier used by the live analysis service.
"""
from __future__ import annotations

import gc
import json
import os
import threading
from pathlib import Path
from typing import Any

from config import MURIL_MAX_LENGTH, MURIL_MODEL_DIR, MURIL_THRESHOLD


class MuRILUnavailable(RuntimeError):
    """Raised when the local MuRIL checkpoint or runtime is not ready."""


_WEIGHT_NAMES = (
    "model.safetensors",
    "pytorch_model.bin",
    "model.safetensors.index.json",
    "pytorch_model.bin.index.json",
)
_TOKENIZER_NAMES = ("tokenizer.json", "vocab.txt", "spiece.model", "sentencepiece.bpe.model")
_POSITIVE_WORDS = ("flagged", "fraud", "scam", "spam", "suspicious", "malicious", "phishing", "smishing")
_NEGATIVE_WORDS = ("legit", "genuine", "ham", "benign", "not_flagged", "not flagged", "not_fraud", "not_spam", "non_fraud", "non_spam", "normal")


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def inspect_checkpoint(model_dir: str | Path = MURIL_MODEL_DIR) -> dict[str, Any]:
    """Check checkpoint structure without importing torch or transformers."""
    root = Path(model_dir)
    problems: list[str] = []
    if not root.is_dir():
        return {"ready": False, "path": str(root), "problems": [f"Checkpoint folder not found: {root}"]}

    config_path = root / "config.json"
    config = _read_json(config_path)
    if config is None:
        problems.append("config.json is missing or is not valid JSON")

    weights = [name for name in _WEIGHT_NAMES if (root / name).is_file()]
    if not weights:
        problems.append("Model weights are missing (expected model.safetensors or a PyTorch weight file)")

    tokenizer_files = [name for name in _TOKENIZER_NAMES if (root / name).is_file()]
    if not tokenizer_files:
        problems.append("Tokenizer files are missing (expected tokenizer.json, vocab.txt, or a SentencePiece model)")
    if not (root / "tokenizer_config.json").is_file() and not tokenizer_files:
        problems.append("tokenizer_config.json is missing")

    num_labels = None
    if config:
        num_labels = config.get("num_labels")
        if num_labels is None and isinstance(config.get("id2label"), dict):
            num_labels = len(config["id2label"])
        if num_labels is not None:
            try:
                parsed_num_labels = int(num_labels)
            except (TypeError, ValueError):
                parsed_num_labels = None
                problems.append("config.json contains an invalid num_labels value")
            if parsed_num_labels is not None and parsed_num_labels != 2:
                problems.append(f"This integration expects a binary checkpoint (num_labels=2), found {num_labels}")

    return {
        "ready": not problems,
        "path": str(root.resolve()),
        "problems": problems,
        "weights": weights,
        "tokenizer_files": tokenizer_files,
        "num_labels": num_labels,
        "model_type": config.get("model_type") if config else None,
        "id2label": config.get("id2label") if config else None,
    }


def _normalize_label(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _is_negative_label(value: Any) -> bool:
    label = _normalize_label(value)
    return any(token in label for token in _NEGATIVE_WORDS)


def _is_positive_label(value: Any) -> bool:
    label = _normalize_label(value)
    return not _is_negative_label(label) and any(token in label for token in _POSITIVE_WORDS)


def _extract_label_maps(root: Path, config: dict[str, Any]) -> tuple[dict[int, str], dict[str, int]]:
    id2label: dict[int, str] = {}
    label2id: dict[str, int] = {}

    raw_id2label = config.get("id2label")
    if isinstance(raw_id2label, dict):
        for key, value in raw_id2label.items():
            try:
                id2label[int(key)] = str(value)
            except (TypeError, ValueError):
                continue
    raw_label2id = config.get("label2id")
    if isinstance(raw_label2id, dict):
        for key, value in raw_label2id.items():
            try:
                label2id[_normalize_label(key)] = int(value)
            except (TypeError, ValueError):
                continue

    # Optional training sidecars are accepted but never required when config.json is explicit.
    for filename in ("label_mapping.json", "label_map.json", "labels.json", "metadata.json"):
        sidecar = _read_json(root / filename)
        if not sidecar:
            continue
        nested = sidecar.get("label_mapping") if isinstance(sidecar.get("label_mapping"), dict) else sidecar
        if not id2label and isinstance(nested.get("id2label"), dict):
            for key, value in nested["id2label"].items():
                try:
                    id2label[int(key)] = str(value)
                except (TypeError, ValueError):
                    continue
        if not label2id and isinstance(nested.get("label2id"), dict):
            for key, value in nested["label2id"].items():
                try:
                    label2id[_normalize_label(key)] = int(value)
                except (TypeError, ValueError):
                    continue
        labels = nested.get("labels")
        if not id2label and isinstance(labels, list):
            id2label = {i: str(label) for i, label in enumerate(labels)}
    return id2label, label2id


def resolve_positive_label_id(config: dict[str, Any], model_dir: str | Path = MURIL_MODEL_DIR) -> int:
    """Resolve the flagged class from config/sidecars; project binary convention is 1=flagged."""
    root = Path(model_dir)
    id2label, label2id = _extract_label_maps(root, config)
    override = os.getenv("GRAMSURAKSHA_MURIL_POSITIVE_LABEL_ID", "").strip()
    if override:
        try:
            positive_id = int(override)
        except ValueError as exc:
            raise MuRILUnavailable("GRAMSURAKSHA_MURIL_POSITIVE_LABEL_ID must be 0 or 1") from exc
        if positive_id not in (0, 1):
            raise MuRILUnavailable("GRAMSURAKSHA_MURIL_POSITIVE_LABEL_ID must be 0 or 1")
        return positive_id

    positives = [idx for idx, name in id2label.items() if _is_positive_label(name)]
    if not positives:
        positives = [idx for name, idx in label2id.items() if _is_positive_label(name)]
    if len(positives) == 1:
        return positives[0]
    if len(positives) > 1:
        raise MuRILUnavailable(f"Ambiguous flagged-class mapping in checkpoint: {id2label or label2id}")

    labels = list(id2label.values()) + list(label2id.keys())
    generic = not labels or all(_normalize_label(v) in ("label_0", "label_1", "0", "1") for v in labels)
    if generic:
        # The GramSurakshaAI MuRIL training pipeline defines 0=legitimate, 1=flagged.
        return 1

    negatives = [idx for idx, name in id2label.items() if _is_negative_label(name)]
    if not negatives:
        negatives = [idx for name, idx in label2id.items() if _is_negative_label(name)]
    if len(negatives) == 1:
        return 1 - negatives[0]
    raise MuRILUnavailable(
        "Could not identify the flagged class from config.json. Add label2id/id2label "
        "(legitimate=0, flagged=1) or set GRAMSURAKSHA_MURIL_POSITIVE_LABEL_ID."
    )


class MuRILPredictor:
    """Thread-safe local MuRIL inference with CUDA FP16 and CPU fallback."""

    kind = "transformer"
    model_name = "Fine-tuned MuRIL (binary)"

    def __init__(self, model_dir: str | Path = MURIL_MODEL_DIR):
        self.model_dir = Path(model_dir)
        self.checkpoint = inspect_checkpoint(self.model_dir)
        if not self.checkpoint["ready"]:
            raise MuRILUnavailable("; ".join(self.checkpoint["problems"]))
        config = _read_json(self.model_dir / "config.json") or {}
        raw_num_labels = config.get("num_labels")
        if raw_num_labels is None:
            raw_num_labels = len(config.get("id2label", {})) or 2
        try:
            num_labels = int(raw_num_labels)
        except (TypeError, ValueError) as exc:
            raise MuRILUnavailable("config.json does not declare a valid num_labels value") from exc
        if num_labels != 2:
            raise MuRILUnavailable("The supplied model is not a binary sequence classifier (expected two labels).")
        self.positive_label_id = resolve_positive_label_id(config, self.model_dir)
        self.max_length = max(16, min(int(MURIL_MAX_LENGTH), int(config.get("max_position_embeddings", 512))))
        self.threshold = float(MURIL_THRESHOLD)
        if not 0.0 < self.threshold < 1.0:
            raise MuRILUnavailable("GRAMSURAKSHA_MURIL_THRESHOLD must be between 0 and 1")
        self._lock = threading.RLock()
        self._torch = None
        self._tokenizer = None
        self._model = None
        self._device = "not_loaded"
        self._load_error: str | None = None

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    @property
    def device(self) -> str:
        return self._device

    def _load(self) -> None:
        if self._model is not None:
            return
        with self._lock:
            if self._model is not None:
                return
            try:
                import torch
                from transformers import AutoConfig, AutoModelForSequenceClassification, AutoTokenizer
            except ImportError as exc:
                raise MuRILUnavailable(
                    "MuRIL runtime dependencies are missing. Run setup_muril_gpu.bat "
                    "or install requirements-muril.txt and PyTorch."
                ) from exc

            local = str(self.model_dir.resolve())
            try:
                config = AutoConfig.from_pretrained(local, local_files_only=True, trust_remote_code=False)
                try:
                    tokenizer = AutoTokenizer.from_pretrained(
                        local, local_files_only=True, use_fast=True, trust_remote_code=False
                    )
                except Exception:
                    tokenizer = AutoTokenizer.from_pretrained(
                        local, local_files_only=True, use_fast=False, trust_remote_code=False
                    )

                requested_device = os.getenv("GRAMSURAKSHA_MURIL_DEVICE", "auto").strip().lower()
                cuda_available = bool(torch.cuda.is_available())
                if requested_device not in ("auto", "cpu", "cuda"):
                    raise MuRILUnavailable("GRAMSURAKSHA_MURIL_DEVICE must be auto, cpu, or cuda")
                use_cuda = cuda_available and requested_device != "cpu"
                if requested_device == "cuda" and not cuda_available:
                    raise MuRILUnavailable("CUDA was requested but PyTorch cannot see an NVIDIA CUDA device")

                use_fp16 = os.getenv("GRAMSURAKSHA_MURIL_FP16", "1").strip().lower() not in ("0", "false", "no")
                dtype = torch.float16 if use_cuda and use_fp16 else torch.float32
                try:
                    model = AutoModelForSequenceClassification.from_pretrained(
                        local, config=config, local_files_only=True, trust_remote_code=False,
                        use_safetensors=True, low_cpu_mem_usage=True, torch_dtype=dtype,
                    )
                    device = torch.device("cuda:0" if use_cuda else "cpu")
                    model.to(device)
                except Exception as exc:
                    if not (use_cuda and self._is_oom(exc)):
                        raise
                    try:
                        del model
                    except UnboundLocalError:
                        pass
                    gc.collect()
                    torch.cuda.empty_cache()
                    model = AutoModelForSequenceClassification.from_pretrained(
                        local, config=config, local_files_only=True, trust_remote_code=False,
                        use_safetensors=True, low_cpu_mem_usage=True, torch_dtype=torch.float32,
                    )
                    model.to(torch.device("cpu"))
                    device = torch.device("cpu")

                model.eval()
                self._torch = torch
                self._tokenizer = tokenizer
                self._model = model
                self._device = str(device)
            except MuRILUnavailable:
                raise
            except Exception as exc:  # keep library internals out of end-user stack traces
                self._load_error = f"{type(exc).__name__}: {exc}"
                raise MuRILUnavailable(f"MuRIL could not load the local checkpoint: {self._load_error}") from exc

    @staticmethod
    def _is_oom(exc: BaseException) -> bool:
        return "out of memory" in str(exc).lower() or type(exc).__name__ == "OutOfMemoryError"

    def _run_logits(self, text: str):
        encoded = self._tokenizer(
            text, truncation=True, max_length=self.max_length, padding=True, return_tensors="pt"
        )
        encoded = {key: value.to(self._device) for key, value in encoded.items()}
        with self._torch.inference_mode():
            return self._model(**encoded).logits[0]

    def _fallback_to_cpu(self) -> None:
        if self._device.startswith("cuda") and self._model is not None:
            self._model.to("cpu")
            self._model.float()
            self._device = "cpu"
            if self._torch is not None and self._torch.cuda.is_available():
                self._torch.cuda.empty_cache()

    def predict(self, text: str) -> dict[str, Any]:
        self._load()
        with self._lock:
            try:
                logits = self._run_logits(text)
            except RuntimeError as exc:
                if not (self._device.startswith("cuda") and self._is_oom(exc)):
                    raise
                self._fallback_to_cpu()
                logits = self._run_logits(text)
            probs = self._torch.softmax(logits.float(), dim=-1).detach().cpu().tolist()
            if len(probs) != 2 or not all(float(v) == float(v) for v in probs):
                raise MuRILUnavailable("MuRIL returned invalid binary class scores")
            positive_score = float(probs[self.positive_label_id])
            predicted = "flagged" if positive_score >= self.threshold else "not_flagged"
            return {
                "available": True,
                "model_name": self.model_name,
                "model_id": f"muril-local-{self.model_dir.name}",
                "kind": self.kind,
                "label": predicted,
                "score": positive_score,
                "decision_value": positive_score,
                "calibrated_probability": None,
                "calibration_status": "not_calibrated",
                "threshold": self.threshold,
                "positive_label_id": self.positive_label_id,
                "class_scores": {"legitimate": float(probs[1 - self.positive_label_id]),
                                 "flagged": positive_score},
                "device": self._device,
                "max_length": self.max_length,
            }


def load_muril_predictor(model_dir: str | Path = MURIL_MODEL_DIR) -> MuRILPredictor:
    return MuRILPredictor(model_dir)


def _status_for_language(entry: dict[str, Any], evaluation_is_real: bool) -> str:
    status = str(entry.get("status", "")).lower()
    samples = int(entry.get("samples", entry.get("n", 0)) or 0)
    if status in ("evaluated", "limited", "none"):
        return status
    matrix = entry.get("confusion_matrix")
    has_both_classes = False
    if isinstance(matrix, list) and len(matrix) >= 2:
        try:
            has_both_classes = sum(matrix[0]) > 0 and sum(matrix[1]) > 0
        except (TypeError, IndexError):
            has_both_classes = False
    if samples >= 30 and has_both_classes and evaluation_is_real:
        return "evaluated"
    if samples >= 10 and has_both_classes:
        return "limited"
    return "none"


def load_muril_metrics(model_dir: str | Path = MURIL_MODEL_DIR) -> dict[str, Any] | None:
    """Read checkpoint-local evaluation metrics; absent metrics never imply language support."""
    root = Path(model_dir)
    candidates = (root / "metrics.json", root / "evaluation_metrics.json", root.parent / "muril_metrics.json")
    for path in candidates:
        raw = _read_json(path)
        if not raw:
            continue
        test = raw.get("test") if isinstance(raw.get("test"), dict) else {}
        report = test or (raw.get("validation") if isinstance(raw.get("validation"), dict) else {})
        per_language = report.get("per_language") if isinstance(report.get("per_language"), dict) else raw.get("per_language", {})
        if not isinstance(per_language, dict):
            per_language = {}
        evaluation_status = str(raw.get("evaluation_status", raw.get("metadata", {}).get("evaluation_status", ""))).lower()
        evaluation_is_real = evaluation_status in ("real_data", "independently_reviewed", "verified_real_data")
        statuses = {}
        for lang in ("en", "hi", "hinglish", "mixed"):
            entry = per_language.get(lang, {})
            statuses[lang] = {**entry, "status": _status_for_language(entry, evaluation_is_real)}
        overall = report.get("overall", {}) if isinstance(report, dict) else {}
        return {
            "source": str(path),
            "evaluation_status": evaluation_status or "not_declared",
            "per_language": statuses,
            "test": {"overall": overall},
            "metadata": raw.get("metadata", {}),
        }
    return None
