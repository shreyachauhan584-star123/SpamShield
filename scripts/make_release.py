"""Build a clean release ZIP (never touches the working repository, never deletes .git).

    python scripts/make_release.py [--out dist/GramSurakshaAI-v2.zip]

Excluded: .git, virtual environments, caches, local databases/backups (user data), .env, generated split files,
experiment logs, temporary uploads, optional transformer checkpoints.
Included on purpose: models/baseline (the ACTIVE production model + checksums + metrics) and models/registry
(version history for rollback); data/synthetic, data/metadata, rules, docs, tests.
"""
import argparse
import fnmatch
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDE_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".ipynb_checkpoints", "backups", "dist", "uploads", "experiments", "checkpoint", ".mypy_cache"}
EXCLUDE_GLOBS = ["*.pyc", "*.db", "*.db-journal", "*.sqlite*", ".env", ".DS_Store", "data/train/*.csv", "data/validation/*.csv", "data/test/*.csv", "data/raw/*", "*.zip"]
KEEP = {".gitkeep"}


def _excluded(rel: Path) -> bool:
    if any(part in EXCLUDE_DIRS for part in rel.parts):
        return True
    s = rel.as_posix()
    if rel.name in KEEP:
        return False
    return any(fnmatch.fnmatch(s, g) or fnmatch.fnmatch(rel.name, g) for g in EXCLUDE_GLOBS)


def build(out: Path) -> list[str]:
    out.parent.mkdir(parents=True, exist_ok=True)
    names = []
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(ROOT.rglob("*")):
            rel = f.relative_to(ROOT)
            if f.is_file() and not _excluded(rel):
                z.write(f, Path("GramSurakshaAI") / rel)
                names.append(rel.as_posix())
    return names


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default=str(ROOT / "dist" / "GramSurakshaAI-v2.zip"))
    a = ap.parse_args()
    n = build(Path(a.out))
    print(f"wrote {a.out} with {len(n)} files")
