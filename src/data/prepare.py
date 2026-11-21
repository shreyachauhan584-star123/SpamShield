"""Dataset preparation CLI: load -> validate -> clean -> version -> language-tag -> split -> write manifests.

    python -m src.data.prepare                      # bundled synthetic data (+ UCI if present in data/raw)
    python -m src.data.prepare --extra-csv x.csv --extra-provenance manually_verified
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from config import METADATA_DIR, RANDOM_SEED, TEST_DIR, TRAIN_DIR, UCI_DEFAULT_PATH, VALIDATION_DIR
from src.data import registry
from src.data.dataset_validation import dataset_stats
from src.data.load_data import load_training_data
from src.data.preprocess import clean_dataframe
from src.data.splitting import make_splits
from src.nlp.language_detection import detect_language
from src.nlp.text_processing import normalize_for_model
from src.utils.helpers import sha256_file, utc_now_iso

SPLIT_DIRS = {"train": TRAIN_DIR, "validation": VALIDATION_DIR, "test": TEST_DIR}
COLUMNS = ["message", "label", "target", "language", "provenance", "dataset_id", "group"]


def dataset_version(df: pd.DataFrame) -> str:
    """Content hash: changes whenever any message, label or provenance changes."""
    h = hashlib.sha256()
    for key in sorted(zip(df.message.map(normalize_for_model), df.label, df.provenance)):
        h.update("\x1f".join(key).encode("utf-8") + b"\n")
    return "dsv-" + h.hexdigest()[:10]


def prepare(seed: int = RANDOM_SEED, write: bool = True, **load_kwargs) -> dict:
    registry.ensure_builtin_records()
    raw = load_training_data(**load_kwargs)
    if (UCI_DEFAULT_PATH).exists() and "uci" in set(raw.source):
        registry.register(registry.uci_record(UCI_DEFAULT_PATH))
    df, removed = clean_dataframe(raw)
    df["language"] = df.message.map(lambda m: detect_language(m).code)
    version = dataset_version(df)
    splits, info = make_splits(df, seed)
    stats = dataset_stats(df)
    stats["language_distribution"] = {k: int(v) for k, v in df.language.value_counts().items()}

    manifest = {
        "dataset_version": version, "created_at": utc_now_iso(), "removed_during_cleaning": removed, "stats": stats,
        "datasets_used": {d: registry.get(d).version if registry.get(d) else d for d in sorted(set(df.dataset_id))},
        "split": info,
        "warnings": ([f"Class imbalance ratio {stats['imbalance_ratio']}:1"] if stats.get("imbalanced") else [])
                    + ([info["evaluation_note"]] if info["evaluation_status"] != "real_data" else []),
    }
    if write:
        manifest["files"] = {}
        for name, d in splits.items():
            SPLIT_DIRS[name].mkdir(parents=True, exist_ok=True)
            f = SPLIT_DIRS[name] / f"{name}.csv"
            d[COLUMNS].to_csv(f, index=False, encoding="utf-8")
            manifest["files"][name] = {"path": str(f.relative_to(f.parents[2])), "rows": len(d), "sha256": sha256_file(f)}
        METADATA_DIR.mkdir(parents=True, exist_ok=True)
        (METADATA_DIR / "splits.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        vf = METADATA_DIR / "versions.json"
        hist = json.loads(vf.read_text()) if vf.exists() else []
        if not any(h["dataset_version"] == version for h in hist):
            hist.append({"dataset_version": version, "created_at": manifest["created_at"], "rows": len(df),
                         "provenance": stats.get("provenance"), "datasets_used": manifest["datasets_used"]})
            vf.write_text(json.dumps(hist, indent=2), encoding="utf-8")
    return {"df": df, "splits": splits, "manifest": manifest}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--uci-path"); ap.add_argument("--extra-csv"); ap.add_argument("--extra-provenance")
    ap.add_argument("--no-uci", action="store_true"); ap.add_argument("--no-demo", action="store_true")
    ap.add_argument("--seed", type=int, default=RANDOM_SEED)
    a = ap.parse_args(argv)
    out = prepare(a.seed, uci_path=a.uci_path, extra_csv=a.extra_csv, extra_provenance=a.extra_provenance,
                  include_demo=not a.no_demo, use_uci=not a.no_uci)
    m = out["manifest"]
    print("dataset", m["dataset_version"], "| rows", m["stats"]["rows"], "| provenance", m["stats"].get("provenance"))
    print("split sizes", m["split"]["sizes"], "| evaluation:", m["split"]["evaluation_status"])
    for w in m["warnings"]:
        print("WARNING:", w)


if __name__ == "__main__":
    main()
