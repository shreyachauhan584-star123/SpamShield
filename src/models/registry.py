"""Model versioning. Every training run is archived under models/registry/<model_id>/ and one version is *active*
(copied into models/baseline/, which is where the app loads from)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from config import BASELINE_DIR, MODELS_DIR

REGISTRY_DIR = MODELS_DIR / "registry"
ARTIFACTS = ("model.joblib", "model.joblib.sha256", "calibrator.joblib", "calibrator.joblib.sha256", "metrics.json", "metadata.json")


def _index(reg_dir: Path = REGISTRY_DIR) -> dict:
    f = reg_dir / "registry.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {"active": None, "models": []}


def _save(idx: dict, reg_dir: Path = REGISTRY_DIR) -> None:
    reg_dir.mkdir(parents=True, exist_ok=True)
    (reg_dir / "registry.json").write_text(json.dumps(idx, indent=2, ensure_ascii=False), encoding="utf-8")


def list_models(reg_dir: Path = REGISTRY_DIR) -> list[dict]:
    return _index(reg_dir)["models"]


def active_id(reg_dir: Path = REGISTRY_DIR) -> str | None:
    return _index(reg_dir)["active"]


def archive_and_activate(model_id: str, source_dir: Path, summary: dict, active_dir: Path = BASELINE_DIR,
                         reg_dir: Path = REGISTRY_DIR, activate: bool = True) -> None:
    dest = reg_dir / model_id
    dest.mkdir(parents=True, exist_ok=True)
    for name in ARTIFACTS:
        if (source_dir / name).exists():
            shutil.copy2(source_dir / name, dest / name)
    idx = _index(reg_dir)
    idx["models"] = [m for m in idx["models"] if m["model_id"] != model_id] + [{"model_id": model_id, **summary}]
    if activate:
        idx["active"] = model_id
    _save(idx, reg_dir)
    if activate:
        activate_model(model_id, active_dir, reg_dir)


def activate_model(model_id: str, active_dir: Path = BASELINE_DIR, reg_dir: Path = REGISTRY_DIR) -> None:
    """Make an archived version the one the app loads (roll back / forward)."""
    src = reg_dir / model_id
    if not src.exists():
        raise FileNotFoundError(f"Unknown model version {model_id}")
    active_dir.mkdir(parents=True, exist_ok=True)
    for name in ARTIFACTS:
        t = active_dir / name
        if (src / name).exists():
            shutil.copy2(src / name, t)
        elif t.exists():
            t.unlink()          # e.g. a version without a calibrator must not inherit the previous one
    idx = _index(reg_dir)
    idx["active"] = model_id
    _save(idx, reg_dir)
