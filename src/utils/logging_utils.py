"""Safe logging: messages are never logged by the app; as defence in depth every record is redacted anyway."""
from __future__ import annotations

import logging
import re

_PATTERNS = [(re.compile(r"https?://\S+|www\.\S+", re.I), "[url]"), (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[email]"),
             (re.compile(r"\d{4,}"), "[number]")]


def redact_text(s: str) -> str:
    for rx, rep in _PATTERNS:
        s = rx.sub(rep, s)
    return s


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_text(str(record.getMessage()))
        record.args = ()
        return True


def get_logger(name: str = "gramsuraksha") -> logging.Logger:
    log = logging.getLogger(name)
    if not any(isinstance(f, RedactingFilter) for f in log.filters):
        log.addFilter(RedactingFilter())
    return log
