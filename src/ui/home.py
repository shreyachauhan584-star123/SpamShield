"""Home page: three ways to give a message (paste / screenshot / voice) -> analysis -> result view."""
from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

from config import MAX_SMS_CHARS
from src.content.samples import SAMPLES
from src.multimodal import ocr_service as ocr
from src.multimodal import speech_recognition as stt
from src.multimodal.image_processing import ImageValidationError
from src.multimodal.text_to_speech import browser_dictation_html
from src.services.analysis_service import analyze_sms
from src.ui.results import render_result
from src.ui.state import T, current_lang, get_ocr_status, get_runtime, get_threat_provider
from src.ui.styles import hero_html


def _run(text: str) -> None:
    provider = get_threat_provider() if st.session_state.get("use_threat_intel") else None   # opt-in only
    try:
        res = analyze_sms(text, st.session_state.get("msg_lang"), "baseline", get_runtime(), threat_provider=provider)
    except Exception:  # noqa: BLE001 - never show a stack trace to a user
        res = {"ok": False, "error_code": "generic"}
    if res["ok"]:
        st.session_state["result"] = res
        st.rerun()
    else:
        st.error(T(f"err_{res['error_code']}", max=MAX_SMS_CHARS))


def _sample(text: str) -> None:
    st.session_state["sms_input"] = text


def _clear() -> None:
    st.session_state["sms_input"] = ""


def _paste_tab() -> None:
    st.text_area(T("input_label"), key="sms_input", height=170, placeholder=T("input_placeholder"))
    st.selectbox(T("msg_language"), ["auto", "en", "hi", "hinglish", "mixed"], key="msg_lang", format_func=lambda c: T(f"lang_{c}"))
    c1, c2 = st.columns([3, 1])
    if c1.button("🔎 " + T("btn_analyze"), type="primary", use_container_width=True, key="go_paste"):
        _run(st.session_state.get("sms_input", ""))
    c2.button(T("btn_clear"), on_click=_clear, use_container_width=True)
    with st.expander(T("samples_title")):
        cols = st.columns(2)
        for i, (k, text) in enumerate(SAMPLES.items()):
            cols[i % 2].button(T(k), key=f"s_{k}", on_click=_sample, args=(text,), use_container_width=True)


def _image_tab() -> None:
    status = get_ocr_status()
    if not status["available"]:
        st.warning(T("ocr_unavailable"))
        return
    up = st.file_uploader(T("img_upload"), type=["png", "jpg", "jpeg", "webp"], key="img_upload")
    st.caption(T("img_hint"))
    if up is None:                                          # removing the picture also removes what was read from it
        st.session_state.pop("ocr_meta", None)
        st.session_state.pop("ocr_text", None)
        return
    st.image(up.getvalue(), use_container_width=True)
    if st.button("📷 " + T("btn_read_image"), key="read_img", use_container_width=True):
        try:
            with st.spinner(T("voice_loading")):
                r = ocr.extract_text(up.getvalue(), st.session_state.get("msg_lang") or "auto")
            st.session_state["ocr_meta"] = {"warnings": r.warnings, "confidence": r.confidence}
            st.session_state["ocr_text"] = r.text
        except ImageValidationError as exc:
            st.error(T(f"err_image_{exc.code}"))
        except ocr.OCRUnavailable:
            st.error(T("ocr_unavailable"))
    meta = st.session_state.get("ocr_meta")
    if meta is not None:
        for w in meta["warnings"]:
            key = {"low_confidence": "ocr_low", "no_text_found": "ocr_empty", "hindi_pack_missing": "ocr_hindi_missing",
                   "ocr_timeout": "ocr_timeout", "truncated": "ocr_truncated"}.get(w)
            if key:
                st.warning(T(key))
        st.info(T("ocr_edit"))
        st.text_area(T("ocr_label"), key="ocr_text", height=170)            # the user always confirms/edits the OCR text
        if st.button("🔎 " + T("btn_analyze"), type="primary", use_container_width=True, key="go_ocr"):
            _run(st.session_state.get("ocr_text", ""))


def _voice_tab() -> None:
    st.write(T("voice_intro"))
    lang = current_lang()
    engines_ok = any(e["available"] for e in stt.available_engines())
    if engines_ok and hasattr(st, "audio_input"):
        audio = st.audio_input(T("voice_intro"), key="voice_audio")
        if audio is not None and st.button("📝 " + T("btn_transcribe"), key="transcribe", use_container_width=True):
            try:
                with st.spinner(T("voice_loading")):
                    st.session_state["voice_text"] = stt.transcribe(audio.getvalue(), lang).text
            except stt.AudioValidationError as exc:
                st.error(T(f"err_audio_{exc.code}"))
            except stt.STTUnavailable:
                st.warning(T("voice_no_engine"))
        if "voice_text" in st.session_state:
            st.text_area(T("voice_edit"), key="voice_text", height=140)
            if st.button("🔎 " + T("btn_analyze"), type="primary", use_container_width=True, key="go_voice"):
                _run(st.session_state.get("voice_text", ""))
        return
    st.info(T("voice_no_engine"))
    labels = {"start": T("dict_start"), "stop": T("dict_stop"), "listening": T("dict_listening"), "unsupported": T("tts_unsupported"),
              "copy": T("dict_copy"), "copied": T("dict_copied"), "result_label": T("dict_result")}
    components.html(browser_dictation_html(lang, labels), height=260)


def render_page() -> None:
    st.session_state.setdefault("sms_input", "")
    if st.session_state.get("result"):
        render_result()
        return
    st.markdown(hero_html(T("app_title"), T("app_subtitle"), T("app_tagline")), unsafe_allow_html=True)
    st.write(T("home_how"))
    t1, t2, t3 = st.tabs(["✍️ " + T("tab_paste"), "📷 " + T("tab_image"), "🎤 " + T("tab_voice")])
    with t1:
        _paste_tab()
    with t2:
        _image_tab()
    with t3:
        _voice_tab()
    if get_threat_provider() is not None:
        st.checkbox(T("threat_optin"), key="use_threat_intel")
    st.caption("🔒 " + T("privacy_note_input"))
