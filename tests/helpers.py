"""Shared test helpers: trains a model ONCE into a temp dir so tests never depend on committed artifacts."""
import functools
import tempfile
from argparse import Namespace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Ten required example messages (+ extras). These must never appear in training data.
CASES = {
    "kyc_block_en": "Your account will be blocked. Update KYC immediately.",
    "lottery_en": "Congratulations! You won a lottery prize.",
    "otp_legit": "Your OTP is 123456. Do not share it.",
    "electricity_paid": "Your electricity bill has been paid successfully.",
    "kyc_hinglish": "Aapka bank account band ho jayega. KYC update karein.",
    "block_hindi": "आपका बैंक खाता बंद कर दिया जाएगा।",
    "upi_received": "You received ₹500 through UPI.",
    "govt_legit": "Your PM-KISAN instalment of Rs 2000 has been credited to your bank account.",
    "personal": "Ok, I will reach home by 8. Keep dinner ready.",
    "url_ip": "Dear user claim your reward now: http://192.168.4.7/claim?id=991",
}


@functools.lru_cache(maxsize=1)
def trained_dir() -> Path:
    from src.models.train_model import run
    d = Path(tempfile.mkdtemp(prefix="gs_model_"))
    run(Namespace(uci_path=None, extra_csv=None, no_demo=False, no_uci=True, output_dir=str(d), seed=42,
                   write_splits=False, register=False, log=False))
    return d


@functools.lru_cache(maxsize=1)
def runtime():
    from src.models.model_loader import load_baseline, load_metrics
    from src.security.fraud_rules import RuleEngine
    from src.services.analysis_service import Runtime
    d = trained_dir()
    return Runtime(RuleEngine(), load_baseline(d / "model.joblib"), None, load_metrics(d / "metrics.json"))


def _font(size=40):
    from PIL import ImageFont
    for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return None


def make_sms_screenshot(lines, dark=False, width=1080, fmt="PNG", size=40) -> bytes:
    """Synthetic phone-style screenshot (no real SMS). Returns encoded image bytes, or None if no TTF font is installed."""
    from io import BytesIO
    from PIL import Image, ImageDraw
    font = _font(size)
    if font is None:
        return None
    bg, bubble, fg = ((18, 18, 18), (45, 55, 72), (240, 240, 240)) if dark else ((245, 245, 245), (255, 255, 255), (20, 20, 20))
    h = 220 + len(lines) * (size + 18)
    img = Image.new("RGB", (width, h), bg)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((40, 120, width - 40, h - 60), 30, fill=bubble)
    y = 150
    for ln in lines:
        d.text((80, y), ln, font=font, fill=fg)
        y += size + 18
    buf = BytesIO()
    img.save(buf, fmt)
    return buf.getvalue()


def make_wav(seconds=1.0, rate=16000, channels=1, silent=False) -> bytes:
    import math
    import struct
    import wave
    from io import BytesIO
    n = int(seconds * rate)
    frames = b"".join(struct.pack("<h", 0 if silent else int(8000 * math.sin(2 * math.pi * 440 * i / rate))) * channels for i in range(n))
    buf = BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels); w.setsampwidth(2); w.setframerate(rate); w.writeframes(frames)
    return buf.getvalue()
