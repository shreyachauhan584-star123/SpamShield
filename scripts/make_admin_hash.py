"""Print a password hash for GRAMSURAKSHA_ADMIN_PASSWORD_HASH. The password is read without echo and never stored."""
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.services.admin_auth import hash_password  # noqa: E402

if __name__ == "__main__":
    pw = getpass.getpass("New admin password (min 12 chars): ")
    if len(pw) < 12 or pw != getpass.getpass("Repeat: "):
        sys.exit("Passwords differ or are shorter than 12 characters.")
    print("\nAdd this line to your environment / .env (never commit it):\nGRAMSURAKSHA_ADMIN_PASSWORD_HASH=" + hash_password(pw))
