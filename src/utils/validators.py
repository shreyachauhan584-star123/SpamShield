"""Input validation for user-supplied SMS text and feedback fields."""
from __future__ import annotations

import re

from config import MAX_SMS_CHARS

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

ALLOWED_VERDICTS = {"correct", "incorrect"}
ALLOWED_CORRECTED = {"legitimate", "suspicious", "not_sure"}
ALLOWED_LEVELS = {"LOW", "MEDIUM", "HIGH", "UNKNOWN"}


class InputValidationError(ValueError):
    """Raised for invalid user input. `.code` is a stable machine-readable reason."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def validate_message(text: object, max_chars: int = MAX_SMS_CHARS) -> str:
    """Return a cleaned SMS string or raise InputValidationError (empty / too_long / not_text)."""
    if not isinstance(text, str):
        raise InputValidationError("not_text", "Message must be text.")
    cleaned = _CONTROL.sub("", text).strip()
    if not cleaned:
        raise InputValidationError("empty", "Message is empty.")
    if len(cleaned) > max_chars:
        raise InputValidationError("too_long", f"Message is longer than {max_chars} characters.")
    return cleaned


def validate_feedback(verdict: str, level: str, corrected: str | None) -> None:
    if verdict not in ALLOWED_VERDICTS:
        raise InputValidationError("bad_verdict", "Unknown feedback verdict.")
    if level not in ALLOWED_LEVELS:
        raise InputValidationError("bad_level", "Unknown risk level.")
    if corrected is not None and corrected not in ALLOWED_CORRECTED:
        raise InputValidationError("bad_corrected", "Unknown corrected label.")
