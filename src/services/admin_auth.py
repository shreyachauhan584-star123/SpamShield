"""Administrator authentication. DISABLED unless GRAMSURAKSHA_ADMIN_PASSWORD_HASH is set (no default credentials).

Create a hash:  python scripts/make_admin_hash.py     (PBKDF2-HMAC-SHA256, random salt)
Failed logins are rate-limited process-wide to slow brute force.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time

ITERATIONS = 310_000
MAX_FAILS = 5
LOCK_SECONDS = 300
_state = {"fails": 0, "locked_until": 0.0}


def hash_password(password: str, iterations: int = ITERATIONS) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, iters, salt_hex, hash_hex = stored.split("$")
        if scheme != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iters))
        return hmac.compare_digest(dk.hex(), hash_hex)
    except (ValueError, TypeError):
        return False


def admin_enabled(env=None) -> bool:
    return bool((os.environ if env is None else env).get("GRAMSURAKSHA_ADMIN_PASSWORD_HASH"))


def reset_lockout() -> None:
    _state.update(fails=0, locked_until=0.0)


def try_login(password: str, env=None, now: float | None = None) -> tuple[bool, str]:
    """Returns (ok, code): code in ok | disabled | locked | bad_credentials."""
    env = os.environ if env is None else env
    now = time.monotonic() if now is None else now
    stored = env.get("GRAMSURAKSHA_ADMIN_PASSWORD_HASH")
    if not stored:
        return False, "disabled"
    if now < _state["locked_until"]:
        return False, "locked"
    if password and verify_password(password, stored):
        reset_lockout()
        return True, "ok"
    _state["fails"] += 1
    if _state["fails"] >= MAX_FAILS:
        _state.update(fails=0, locked_until=now + LOCK_SECONDS)
        return False, "locked"
    return False, "bad_credentials"
