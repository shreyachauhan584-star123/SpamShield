"""Text-to-speech behind a small interface so gTTS can later be swapped for browser-native or offline TTS.

Audio is generated in memory only (never written to disk) and cached in memory per (text, language).
"""
from __future__ import annotations

import io
import os
from dataclasses import dataclass
from functools import lru_cache

from config import TTS_SLOW

MAX_TTS_CHARS = 900
GTTS_LANG = {"en": "en", "hi": "hi"}


@dataclass(frozen=True)
class SpeechResult:
    audio: bytes | None
    error: str | None = None      # "disabled" | "gtts_missing" | "network" | "too_long" | "failed"
    mime: str = "audio/mp3"


class SpeechService:
    def synthesize(self, text: str, lang: str) -> SpeechResult:  # pragma: no cover - interface
        raise NotImplementedError


class DisabledSpeech(SpeechService):
    def synthesize(self, text: str, lang: str) -> SpeechResult:
        return SpeechResult(None, "disabled")


class GTTSSpeech(SpeechService):
    """gTTS needs internet (it calls Google's TTS endpoint). Failures are returned, not raised."""

    def __init__(self, slow: bool = TTS_SLOW):
        self.slow = slow
        self._cached = lru_cache(maxsize=32)(self._synth)

    def _synth(self, text: str, lang: str) -> SpeechResult:
        try:
            from gtts import gTTS
        except ImportError:
            return SpeechResult(None, "gtts_missing")
        try:
            buf = io.BytesIO()
            gTTS(text=text, lang=GTTS_LANG.get(lang, "en"), tld="co.in", slow=self.slow).write_to_fp(buf)
            return SpeechResult(buf.getvalue())
        except Exception as exc:  # noqa: BLE001 - gTTSError, requests errors, offline, etc.
            name = type(exc).__name__.lower()
            return SpeechResult(None, "network" if any(k in name for k in ("connection", "timeout", "gtts", "http")) else "failed")

    def synthesize(self, text: str, lang: str) -> SpeechResult:
        text = (text or "").strip()
        if not text:
            return SpeechResult(None, "failed")
        if len(text) > MAX_TTS_CHARS:
            text = text[:MAX_TTS_CHARS].rsplit(" ", 1)[0]
        res = self._cached(text, lang)
        if res.audio is None:  # do not cache failures (e.g. temporary network loss)
            self._cached.cache_clear()
        return res


def get_speech_service() -> SpeechService:
    return DisabledSpeech() if os.getenv("GRAMSURAKSHA_TTS", "gtts") == "none" else GTTSSpeech()
