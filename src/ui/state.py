"""Streamlit-side shared state and cached resources. The only module besides pages that imports streamlit."""
from __future__ import annotations

import streamlit as st

from src.services.analysis_service import build_runtime
from src.services.speech_service import get_speech_service
from src.services.translation_service import tr


@st.cache_resource(show_spinner=False)
def get_runtime():
    """Model + rules are loaded once per server process; never retrained here."""
    return build_runtime()


@st.cache_resource(show_spinner=False)
def get_speech():
    return get_speech_service()


def current_lang() -> str:
    return st.session_state.get("ui_lang", "en")


def T(key: str, **kw) -> str:
    return tr(key, current_lang(), **kw)


@st.cache_resource(show_spinner=False)
def get_ocr_status():
    from src.multimodal.ocr_service import ocr_status
    return ocr_status()


@st.cache_resource(show_spinner=False)
def get_threat_provider():
    from src.security.threat_intel import get_provider
    return get_provider()
