"""Consistent online backup of the feedback database (sqlite3 backup API) with simple rotation.
    python scripts/backup_db.py [--dest backups] [--keep 14]"""
import argparse
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import DB_PATH  # noqa: E402


def backup(db: Path = DB_PATH, dest: Path = Path("backups"), keep: int = 14) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    out = dest / f"feedback-{time.strftime('%Y%m%d-%H%M%S')}.db"
    src, dst = sqlite3.connect(db), sqlite3.connect(out)
    try:
        src.backup(dst)
    finally:
        dst.close(); src.close()
    try:
        out.chmod(0o600)
    except OSError:
        pass
    for old in sorted(dest.glob("feedback-*.db"))[:-keep]:
        old.unlink()
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--dest", default="backups"); ap.add_argument("--keep", type=int, default=14)
    a = ap.parse_args()
    print("backup written:", backup(DB_PATH, Path(a.dest), a.keep))
