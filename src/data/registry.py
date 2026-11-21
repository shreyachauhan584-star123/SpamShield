"""Dataset registry: where every dataset came from, under which licence, and how trustworthy its labels are.

Provenance values keep real, synthetic, augmented and manually verified examples distinguishable at all times:
  real               collected from real-world messages (e.g. UCI SMS Spam Collection)
  manually_verified  real or contributed messages whose labels a human reviewed
  synthetic          written by the project for illustration/coverage (NOT real-world evidence)
  augmented          derived from other examples by automated transformation
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from config import BASE_DIR, DEMO_DATASET_PATH, METADATA_DIR, SYNTHETIC_V2_PATH
from src.utils.helpers import sha256_file, utc_now_iso

PROVENANCE = ("real", "manually_verified", "synthetic", "augmented")
EVALUATION_PROVENANCE = ("real", "manually_verified")     # only these may be used for validation/test when enough exist
REGISTRY_PATH = METADATA_DIR / "datasets.json"


class RegistryError(ValueError):
    pass


@dataclass
class DatasetRecord:
    id: str
    path: str                      # relative to project root
    source: str
    license: str
    provenance: str
    languages: list[str] = field(default_factory=list)
    rows: int = 0
    sha256: str = ""
    license_verified: bool = False
    notes: str = ""
    added_at: str = ""

    @property
    def version(self) -> str:
        return f"{self.id}@{self.sha256[:8]}" if self.sha256 else self.id


def check_provenance(value: str) -> str:
    if value not in PROVENANCE:
        raise RegistryError(f"provenance must be one of {PROVENANCE}, got {value!r}")
    return value


def _read(path: Path = REGISTRY_PATH) -> dict:
    if not path.exists():
        return {"datasets": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def _write(data: dict, path: Path = REGISTRY_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def register(rec: DatasetRecord, registry_path: Path = REGISTRY_PATH) -> DatasetRecord:
    """Insert/update a record. Checksum and row count are computed from the actual file."""
    check_provenance(rec.provenance)
    p = (BASE_DIR / rec.path) if not Path(rec.path).is_absolute() else Path(rec.path)
    if p.exists():
        rec.sha256 = sha256_file(p)
        rec.rows = max(0, sum(1 for _ in open(p, encoding="utf-8", errors="ignore")) - (1 if p.suffix == ".csv" else 0))
    rec.added_at = rec.added_at or utc_now_iso()
    data = _read(registry_path)
    data["datasets"][rec.id] = asdict(rec)
    _write(data, registry_path)
    return rec


def get(dataset_id: str, registry_path: Path = REGISTRY_PATH) -> DatasetRecord | None:
    d = _read(registry_path)["datasets"].get(dataset_id)
    return DatasetRecord(**d) if d else None


def all_records(registry_path: Path = REGISTRY_PATH) -> list[DatasetRecord]:
    return [DatasetRecord(**d) for d in _read(registry_path)["datasets"].values()]


def verify(dataset_id: str, registry_path: Path = REGISTRY_PATH) -> tuple[bool, str]:
    """True if the file on disk still matches the registered checksum (detects silent edits)."""
    rec = get(dataset_id, registry_path)
    if rec is None:
        return False, "not registered"
    p = BASE_DIR / rec.path
    if not p.exists():
        return False, "file missing"
    return (sha256_file(p) == rec.sha256, "ok" if sha256_file(p) == rec.sha256 else "checksum changed since registration")


def _rel(p: Path) -> str:
    try:
        return str(p.resolve().relative_to(BASE_DIR))
    except ValueError:
        return str(p)


def ensure_builtin_records(registry_path: Path = REGISTRY_PATH) -> None:
    """Register the bundled synthetic files (idempotent)."""
    builtin = [
        DatasetRecord("synthetic-demo-v1", _rel(DEMO_DATASET_PATH), "Written by the GramSuraksha project author", "Project-authored; licence to be set by the project owner",
                      "synthetic", ["en", "hinglish", "hi"], notes="149 illustrative messages; not real SMS", license_verified=True),
        DatasetRecord("synthetic-hi-hinglish-v2", _rel(SYNTHETIC_V2_PATH), "Written by the GramSuraksha project author", "Project-authored; licence to be set by the project owner",
                      "synthetic", ["hinglish", "hi"], notes="Spelling variants, negation and awareness messages; not real SMS", license_verified=True),
    ]
    for rec in builtin:
        if (BASE_DIR / rec.path).exists():
            register(rec, registry_path)


def uci_record(path: Path) -> DatasetRecord:
    return DatasetRecord("uci-sms-spam-collection", _rel(path), "https://archive.ics.uci.edu/dataset/228/sms+spam+collection",
                         "CC BY 4.0 as listed on the UCI page - verify before redistributing", "real", ["en"],
                         license_verified=False, notes="English only; 'spam' is mostly promotional, not necessarily fraud")
