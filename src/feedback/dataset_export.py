"""Export HUMAN-ACCEPTED contributions as a validated dataset (provenance = manually_verified).

Exporting does not train anything. To use the file, an administrator must pass it explicitly:
    python -m src.models.train_model --extra-csv data/validated/contributed_validated.csv --extra-provenance manually_verified
"""
from __future__ import annotations

import csv
from pathlib import Path

from config import DB_PATH, VALIDATED_DIR
from src.data import registry
from src.database.db import connect
from src.feedback.review_service import audit

DEFAULT_PATH = VALIDATED_DIR / "contributed_validated.csv"


def export_validated(reviewer: str, path: Path = DEFAULT_PATH, db_path=DB_PATH, register: bool = True) -> dict:
    with connect(db_path) as c:
        rows = c.execute("""SELECT message_text, verified_label, COALESCE(language,'') FROM contributions
                            WHERE review_status='accepted' AND verified_label IS NOT NULL ORDER BY id""").fetchall()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["message", "label", "provenance", "language", "source"])
            for text, label, lang in rows:
                w.writerow([text, label, "manually_verified", lang, "user_contribution"])
        audit(c, "admin", "dataset_exported", "dataset", path.name, f"rows={len(rows)} reviewer={reviewer[:60]}")
    if register and rows:
        registry.register(registry.DatasetRecord(
            "user-contributions-validated", str(path), "Voluntary user contributions (separate consent), human-verified labels",
            "Contributed under contribution-consent-v1; administrator must confirm terms before redistribution", "manually_verified",
            [], license_verified=False, notes="Numbers/phones/e-mails were redacted before storage."))
    return {"rows": len(rows), "path": str(path)}
