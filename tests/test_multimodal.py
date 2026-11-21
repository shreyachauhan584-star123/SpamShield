import glob
import os
import tempfile

import pytest

from src.multimodal import image_processing as ip
from src.multimodal import ocr_service as ocr
from src.multimodal import speech_recognition as stt
from src.multimodal.text_to_speech import browser_dictation_html, browser_tts_html
from src.services.analysis_service import analyze_sms
from src.services.feature_status import feature_status
from tests.helpers import make_sms_screenshot, make_wav, runtime

LINES = ["Your account will be blocked today.", "Update your KYC immediately:", "http://sbi-kyc-update.xyz/login"]


def _need_ocr():
    if not ocr.ocr_status()["available"]:
        pytest.skip("Tesseract not installed")
    if make_sms_screenshot(["x"]) is None:
        pytest.skip("no TrueType font for test images")


# --------------------------- image validation ---------------------------
@pytest.mark.parametrize("data,code", [(b"", "empty"), (None, "empty"), (b"not an image at all", "not_an_image"),
                                       (b"\x89PNG\r\n\x1a\n" + b"\x00" * 50, "not_an_image"), (b"GIF89a" + b"\x00" * 50, "not_an_image")])
def test_bad_uploads_are_rejected(data, code):
    with pytest.raises(ip.ImageValidationError) as e:
        ip.validate_image(data)
    assert e.value.code == code


def test_oversized_and_tiny_and_pixel_bomb_images_are_rejected():
    from io import BytesIO
    from PIL import Image
    with pytest.raises(ip.ImageValidationError) as e:
        ip.validate_image(b"\x89PNG" + b"0" * (6 * 1024 * 1024))
    assert e.value.code == "too_large"
    buf = BytesIO(); Image.new("RGB", (20, 20)).save(buf, "PNG")
    with pytest.raises(ip.ImageValidationError) as e:
        ip.validate_image(buf.getvalue())
    assert e.value.code == "too_small"
    buf = BytesIO(); Image.new("1", (6000, 6000)).save(buf, "PNG")                 # 36 MP, tiny file: a decompression-bomb shape
    with pytest.raises(ip.ImageValidationError) as e:
        ip.validate_image(buf.getvalue())
    assert e.value.code == "too_many_pixels"


def test_real_format_is_checked_not_the_filename_and_unsupported_formats_rejected():
    from io import BytesIO
    from PIL import Image
    buf = BytesIO(); Image.new("RGB", (200, 200), "white").save(buf, "BMP")
    with pytest.raises(ip.ImageValidationError) as e:
        ip.validate_image(buf.getvalue())
    assert e.value.code == "unsupported_format"
    png = make_sms_screenshot(LINES) or pytest.skip("no font")
    assert ip.validate_image(png).mode == "RGB"


def test_transparent_png_is_flattened_to_white():
    from io import BytesIO
    from PIL import Image
    buf = BytesIO(); Image.new("RGBA", (200, 200), (0, 0, 0, 0)).save(buf, "PNG")
    assert ip.validate_image(buf.getvalue()).getpixel((5, 5)) == (255, 255, 255)


# --------------------------- OCR ---------------------------
@pytest.mark.parametrize("dark", [False, True])
def test_ocr_reads_light_and_dark_mode_screenshots(dark):
    _need_ocr()
    r = ocr.extract_text(make_sms_screenshot(LINES, dark=dark))
    t = r.text.lower()
    assert "account" in t and "blocked" in t and "kyc" in t, r.text
    assert "http://" in t and "sbi" in t, r.text            # URL string preserved well enough to analyse
    assert r.needs_review is True and r.confidence is not None and r.confidence > 60


def test_ocr_handles_jpeg_and_smaller_screens():
    _need_ocr()
    r = ocr.extract_text(make_sms_screenshot(LINES, width=720, fmt="JPEG", size=30))
    assert "blocked" in r.text.lower()


def test_ocr_on_blank_image_reports_no_text_instead_of_inventing_some():
    _need_ocr()
    from io import BytesIO
    from PIL import Image
    buf = BytesIO(); Image.new("RGB", (800, 600), "white").save(buf, "PNG")
    r = ocr.extract_text(buf.getvalue())
    assert r.text == "" and "no_text_found" in r.warnings and r.low_confidence


def test_ocr_leaves_no_temporary_files_behind_and_writes_nothing():
    _need_ocr()
    before = set(glob.glob(os.path.join(tempfile.gettempdir(), "tess*")))
    ocr.extract_text(make_sms_screenshot(LINES))
    assert set(glob.glob(os.path.join(tempfile.gettempdir(), "tess*"))) == before


def test_hindi_request_without_language_pack_warns_instead_of_pretending():
    _need_ocr()
    r = ocr.extract_text(make_sms_screenshot(LINES), language="hi")
    if not ocr.ocr_status()["hindi_available"]:
        assert "hindi_pack_missing" in r.warnings and r.language == "eng"


def test_url_repair_only_fixes_prefix_spacing():
    assert ocr.repair_urls("see http : / / bit.ly/a and www . x.com") == "see http://bit.ly/a and www.x.com"
    assert ocr.repair_urls("Sbi0O1l stays") == "Sbi0O1l stays"           # never guesses characters


def test_ocr_to_analysis_pipeline_keeps_the_user_in_the_loop():
    _need_ocr()
    r = ocr.extract_text(make_sms_screenshot(LINES))
    edited = r.text.replace("\n", " ")                                    # what the user confirms (and may edit)
    out = analyze_sms(edited, runtime=runtime())
    assert out["ok"] and out["risk"]["level"] == "HIGH" and out["schema"]["message_category"] in ("KYC_SCAM", "BANK_ACCOUNT_THREAT")


# --------------------------- speech input ---------------------------
@pytest.mark.parametrize("data,code", [(b"", "empty"), (b"RIFFxxxx", "not_wav"), (b"x" * (6 * 1024 * 1024), "too_large")])
def test_bad_audio_is_rejected(data, code):
    with pytest.raises(stt.AudioValidationError) as e:
        stt.validate_wav(data)
    assert e.value.code == code


def test_audio_limits_and_silence():
    assert stt.validate_wav(make_wav(1.0))["rate"] == 16000 and stt.validate_wav(make_wav(0.5, channels=2))["channels"] == 2
    with pytest.raises(stt.AudioValidationError) as e:
        stt.validate_wav(make_wav(61, rate=8000))
    assert e.value.code == "too_long"
    with pytest.raises(stt.AudioValidationError) as e:
        stt.validate_wav(make_wav(1.0, silent=True))
    assert e.value.code == "silent"


def test_without_an_engine_voice_input_says_so_clearly():
    if any(e["available"] for e in stt.available_engines()):
        pytest.skip("a real engine is installed")
    with pytest.raises(stt.STTUnavailable) as e:
        stt.transcribe(make_wav(1.0))
    assert "faster-whisper" in str(e.value) and "vosk" in str(e.value).lower()


def test_voice_to_text_to_analysis_pipeline_with_a_pluggable_engine():
    class Fake(stt.STTEngine):
        name = "fake"
        def available(self): return True, ""
        def transcribe(self, wav, language): return stt.STTResult("Your account will be blocked. Update KYC immediately.", language, self.name)
    stt._ENGINES.insert(0, Fake())
    try:
        res = stt.transcribe(make_wav(1.0), "en")
        assert res.engine == "fake"
        assert analyze_sms(res.text, runtime=runtime())["risk"]["level"] in ("MEDIUM", "HIGH")
    finally:
        stt._ENGINES.pop(0)


def test_empty_transcript_is_an_error_not_an_empty_analysis():
    class Mute(stt.STTEngine):
        name = "mute"
        def available(self): return True, ""
        def transcribe(self, wav, language): return stt.STTResult("", language, self.name)
    stt._ENGINES.insert(0, Mute())
    try:
        with pytest.raises(stt.AudioValidationError):
            stt.transcribe(make_wav(1.0))
    finally:
        stt._ENGINES.pop(0)


# --------------------------- browser speech snippets ---------------------------
LAB = {"button": "Listen", "speaking": "Speaking", "no_voice": "No Hindi voice on this device", "unsupported": "Not supported",
       "start": "Speak", "stop": "Stop", "listening": "Listening", "copy": "Copy", "copied": "Copied", "result_label": "Heard text"}


def test_tts_html_cannot_be_broken_out_of_by_message_text():
    evil = '</script><script>alert(1)</script> "quote" \u2028 </SCRIPT>'
    out = browser_tts_html(evil, "hi", LAB)
    assert out.count("</script>") == 1                       # only our own closing tag
    assert "alert(1)" in out and "<\\/script>" in out


def test_tts_never_reads_hindi_with_a_non_hindi_voice_and_admits_missing_voices():
    out = browser_tts_html("नमस्ते", "hi", LAB)
    assert "hi-IN" in out and "LOCALE.startsWith('hi')" in out and "L.no_voice" in out and "No Hindi voice" in out


def test_dictation_html_labels_are_escaped_and_locale_is_whitelisted():
    out = browser_dictation_html("xx<script>", {**LAB, "result_label": '"><img src=x>'})
    assert "en-IN" in out and "<img src=x>" not in out


def test_feature_status_never_raises_and_reports_missing_engines_honestly():
    s = feature_status(runtime())
    assert s["baseline_model"]["available"] is True and s["ocr"]["available"] in (True, False)
    assert s["speech_input"]["available"] is any(e["available"] for e in s["speech_input"]["engines"])
    assert s["threat_intel"]["configured"] in (True, False) and s["transformer"]["evaluated"] is False
