"""OPTIONAL: fine-tune a multilingual transformer (MuRIL / IndicBERT / mBERT) and compare it with the baselines.

STATUS: implemented but NOT executed in the development environment (no torch/transformers/network there).
Treat it as unverified until you have run it. The basic application never needs it.

    pip install -r requirements-advanced.txt
    python -m src.models.transformer_training --model-name google/muril-base-cased --allow-download --epochs 3

* Uses the SAME prepared splits and the SAME metric code as the baseline models, so numbers are directly comparable.
* Downloading model weights is an explicit admin action (--allow-download). Without it only local files are used.
* Output: models/advanced/checkpoint/ (model + tokenizer) and models/advanced/metrics.json. The app only offers
  the transformer to administrators, and shows it as "not evaluated" unless that metrics file exists.
Model ids (verify on huggingface.co before use): google/muril-base-cased, ai4bharat/indic-bert, bert-base-multilingual-cased.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

from config import ADVANCED_DIR, RANDOM_SEED
from src.models.evaluation import compute_metrics
from src.utils.helpers import utc_now_iso

DEFAULT_MODEL = "google/muril-base-cased"


def class_weights(labels: list[int]) -> list[float]:
    """Inverse-frequency weights [w_legit, w_flagged] (pure python; unit-tested)."""
    c = Counter(labels)
    n, k = len(labels), 2
    return [n / (k * max(1, c.get(i, 0))) for i in range(k)]


def _require_torch():
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
    except ImportError as exc:
        raise SystemExit("Transformer training needs torch and transformers: pip install -r requirements-advanced.txt "
                         f"({exc.name} is missing). The baseline application does not need them.") from exc


def train(model_name: str, epochs: int, batch_size: int, lr: float, max_len: int, seed: int, allow_download: bool, out_dir: Path) -> dict:
    _require_torch()
    import numpy as np
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    from src.data.prepare import prepare

    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    prep = prepare(seed, write=False)
    sp = prep["splits"]
    device = "cuda" if torch.cuda.is_available() else "cpu"
    tok = AutoTokenizer.from_pretrained(model_name, local_files_only=not allow_download)
    model = AutoModelForSequenceClassification.from_pretrained(model_name, num_labels=2, local_files_only=not allow_download).to(device)

    def enc(texts):
        return tok(texts, truncation=True, max_length=max_len, padding=True, return_tensors="pt")

    def predict(texts):
        model.eval(); out = []
        with torch.no_grad():
            for i in range(0, len(texts), 32):
                b = {k: v.to(device) for k, v in enc(texts[i:i + 32]).items()}
                out += torch.softmax(model(**b).logits, dim=-1)[:, 1].cpu().tolist()
        return np.array(out)

    tr = sp["train"]
    X, y = tr.message.tolist(), tr.target.tolist()
    loss_fn = torch.nn.CrossEntropyLoss(weight=torch.tensor(class_weights(y), dtype=torch.float, device=device))
    opt = torch.optim.AdamW(model.parameters(), lr=lr)
    best_pr, best_state, history = -1.0, None, []
    for ep in range(epochs):
        model.train()
        order = np.random.permutation(len(X))
        for i in range(0, len(order), batch_size):
            idx = order[i:i + batch_size]
            b = {k: v.to(device) for k, v in enc([X[j] for j in idx]).items()}
            loss = loss_fn(model(**b).logits, torch.tensor([y[j] for j in idx], device=device))
            loss.backward(); opt.step(); opt.zero_grad()
        val = sp["validation"]
        s = predict(val.message.tolist())
        m = compute_metrics(val.target.to_numpy(), (s >= 0.5).astype(int), s)
        history.append({"epoch": ep + 1, "val_pr_auc": m.get("pr_auc"), "val_f2": m["f2"]})
        if m.get("pr_auc", 0) > best_pr:
            best_pr = m.get("pr_auc", 0)
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    model.load_state_dict(best_state)
    te = sp["test"]
    st = predict(te.message.tolist())
    result = {"trained_at": utc_now_iso(), "model_name": model_name, "device": device, "seed": seed,
              "dataset_version": prep["manifest"]["dataset_version"], "evaluation_status": prep["manifest"]["split"]["evaluation_status"],
              "history": history, "test": compute_metrics(te.target.to_numpy(), (st >= 0.5).astype(int), st),
              "note": "Selected epoch by validation PR-AUC. Compare with the baseline in models/baseline/metrics.json (same splits)."}
    ck = out_dir / "checkpoint"
    ck.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(ck); tok.save_pretrained(ck)
    (out_dir / "metrics.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model-name", default=DEFAULT_MODEL); ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--batch-size", type=int, default=16); ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--max-len", type=int, default=128); ap.add_argument("--seed", type=int, default=RANDOM_SEED)
    ap.add_argument("--allow-download", action="store_true"); ap.add_argument("--output-dir", default=str(ADVANCED_DIR.parent))
    a = ap.parse_args(argv)
    r = train(a.model_name, a.epochs, a.batch_size, a.lr, a.max_len, a.seed, a.allow_download, Path(a.output_dir))
    print(json.dumps({k: r[k] for k in ("model_name", "dataset_version", "evaluation_status", "history")}, indent=2))
    print("test:", {k: round(v, 3) for k, v in r["test"].items() if isinstance(v, float)})


if __name__ == "__main__":
    sys.exit(main())
