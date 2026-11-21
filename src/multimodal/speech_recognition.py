"""Speech-to-text for voice input, behind a small pluggable engine interface.

No paid API is required. Supported OFFLINE engines (install separately, see README 'Voice setup'):
  * faster-whisper  (pip install faster-whisper; model weights downloaded once by an administrator)
  * Vosk            (pip install vosk; set VOSK_MODEL_EN / VOSK_MODEL_HI to downloaded model folders)
Without any engine installed, the app tells the user so and keeps the text box. A browser dictation helper
(Web Speech API) is offered separately in text_to_speech.py. Only WAV input is accepted (no untrusted decoders).
"""
from __future__ import annotations

import os
import wave
from array import array
from dataclasses import dataclass
from io import BytesIO

from config import HF_ALLOW_DOWNLOAD, MAX_AUDIO_MB, MAX_AUDIO_SECONDS


class AudioValidationError(ValueError):
    """`.code`: empty | too_large | not_wav | unsupported | too_long | silent"""

    def __init__(self, code: str, message: str = ""):
        super().__init__(message or code)
        self.code = code


class STTUnavailable(RuntimeError):
    pass


@dataclass
class STTResult:
    text: str
    language: str | None
    engine: str


def validate_wav(data) -> dict:
    if not isinstance(data, (bytes, bytearray)) or not data:
        raise AudioValidationError("empty")
    if len(data) > MAX_AUDIO_MB * 1024 * 1024:
        raise AudioValidationError("too_large")
    try:
        with wave.open(BytesIO(bytes(data)), "rb") as w:
            ch, width, rate, frames = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
            raw = w.readframes(min(frames, rate))   # first second, to detect silence
    except (wave.Error, EOFError):
        raise AudioValidationError("not_wav") from None
    if ch not in (1, 2) or width != 2 or rate < 8000:
        raise AudioValidationError("unsupported")
    seconds = frames / float(rate)
    if seconds > MAX_AUDIO_SECONDS:
        raise AudioValidationError("too_long")
    if seconds <= 0 or not any(raw):
        raise AudioValidationError("silent")
    return {"channels": ch, "rate": rate, "seconds": round(seconds, 2)}


def _mono_pcm(data: bytes) -> tuple[bytes, int]:
    with wave.open(BytesIO(data), "rb") as w:
        ch, rate, raw = w.getnchannels(), w.getframerate(), w.readframes(w.getnframes())
    if ch == 2:
        a = array("h", raw)
        raw = array("h", a[0::2]).tobytes()
    return raw, rate


class STTEngine:
    name = "none"

    def available(self) -> tuple[bool, str]:  # pragma: no cover - interface
        raise NotImplementedError

    def transcribe(self, wav: bytes, language: str | None) -> STTResult:  # pragma: no cover - interface
        raise NotImplementedError


class FasterWhisperEngine(STTEngine):
    name = "faster-whisper"
    _model = None

    def available(self):
        try:
            import faster_whisper  # noqa: F401
            return True, ""
        except ImportError:
            return False, "pip install faster-whisper (and download a model once; see README)"

    def transcribe(self, wav, language):
        from faster_whisper import WhisperModel
        if FasterWhisperEngine._model is None:
            FasterWhisperEngine._model = WhisperModel(os.getenv("GRAMSURAKSHA_WHISPER_MODEL", "small"), device="cpu", compute_type="int8",
                                                      local_files_only=not HF_ALLOW_DOWNLOAD)
        segs, info = FasterWhisperEngine._model.transcribe(BytesIO(wav), language=language if language in ("en", "hi") else None, vad_filter=True)
        return STTResult(" ".join(s.text.strip() for s in segs).strip(), getattr(info, "language", None), self.name)


class VoskEngine(STTEngine):
    name = "vosk"

    def _path(self, language):
        return os.getenv("VOSK_MODEL_HI" if language == "hi" else "VOSK_MODEL_EN")

    def available(self):
        try:
            import vosk  # noqa: F401
        except ImportError:
            return False, "pip install vosk and set VOSK_MODEL_EN / VOSK_MODEL_HI to model folders"
        if not (self._path("en") or self._path("hi")):
            return False, "Vosk installed but VOSK_MODEL_EN / VOSK_MODEL_HI are not set"
        return True, ""

    def transcribe(self, wav, language):
        import json

        from vosk import KaldiRecognizer, Model
        lang = "hi" if language == "hi" else "en"
        path = self._path(lang)
        if not path or not os.path.isdir(path):
            raise STTUnavailable(f"No Vosk model configured for '{lang}'.")
        pcm, rate = _mono_pcm(wav)
        rec = KaldiRecognizer(Model(path), rate)
        rec.AcceptWaveform(pcm)
        return STTResult(json.loads(rec.FinalResult()).get("text", "").strip(), lang, self.name)


_ENGINES: list[STTEngine] = [FasterWhisperEngine(), VoskEngine()]


def register_engine(engine: STTEngine, first: bool = True) -> None:
    """Plug in another engine (also used by tests)."""
    _ENGINES.insert(0 if first else len(_ENGINES), engine)


def available_engines() -> list[dict]:
    out = []
    for e in _ENGINES:
        ok, why = e.available()
        out.append({"engine": e.name, "available": ok, "reason": why})
    return out


def transcribe(data: bytes, language: str | None = None) -> STTResult:
    """Validate audio, then transcribe with the first available engine. Raises AudioValidationError / STTUnavailable."""
    validate_wav(data)
    for e in _ENGINES:
        if e.available()[0]:
            res = e.transcribe(bytes(data), language)
            if not res.text:
                raise AudioValidationError("silent", "No speech was recognised.")
            return res
    raise STTUnavailable("No speech-recognition engine is installed. " + "; ".join(f"{x['engine']}: {x['reason']}" for x in available_engines()))
