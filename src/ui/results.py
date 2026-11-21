"""Result view: risk, type of scam, reasons, links, actions, read-aloud, feedback and optional contribution."""
from __future__ import annotations

from html import escape as e

import streamlit as st
import streamlit.components.v1 as components

from src.feedback.feedback_service import ConsentRequired, FeedbackStorageError, save_feedback_v2
from src.feedback.review_service import submit_contribution
from src.multimodal.text_to_speech import browser_tts_html
from src.services.analysis_service import build_view
from src.services.privacy_service import redact_for_storage, storage_status
from src.ui.guard import is_admin
from src.ui.state import T, current_lang, get_speech
from src.ui.styles import risk_card_html
from src.utils.validators import InputValidationError

_RESULT_FB = {  # (level group) -> (feedback_type if "correct", feedback_type if "wrong")
    "flagged": ("correct_fraud", "false_alarm"),
    "clear": ("correct_legitimate", "missed_suspicious"),
}


def _reset():
    for k in ("result", "fb_done", "fb_expl_done", "contrib_done", "audio", "ocr_text", "ocr_meta", "voice_text"):
        st.session_state.pop(k, None)
    st.session_state["sms_input"] = ""


def render_result() -> None:
    res, lang = st.session_state["result"], current_lang()
    view = build_view(res, lang)
    st.markdown(risk_card_html(view["level"], view["level_label"], view["headline"], view["summary"]), unsafe_allow_html=True)
    st.markdown(f"**{T('result_category')}:** {view['category']}")
    for note in view["notes"]:
        st.caption("ℹ️ " + note)

    if view["indicators"] or view["model_reason"]:
        st.subheader(T("sec_why"))
        for ind in view["indicators"]:
            st.markdown(f'<div class="gs-ind"><span class="sev">{e(ind["severity_label"])}</span> · <code>{e(ind["matched_text"])}</code>'
                        f'<div>{e(ind["explanation"])}</div></div>', unsafe_allow_html=True)
        if view["model_reason"]:
            st.markdown(f"- {view['model_reason']}")
    else:
        st.write(T("none_found"))

    if view["urls"]:
        st.subheader(T("sec_urls"))
        for u in view["urls"]:
            st.code(u["url"], language=None)               # plain text, never a clickable link
            st.markdown(f"**{T('url_domain')}:** `{u['domain']}` — {u['verdict']}")
            for f in u["findings"]:
                st.markdown(f"- {f}")
        st.caption("🚫 " + T("url_not_opened"))

    st.subheader(T("sec_actions"))
    for n, a in enumerate(view["actions"], 1):
        st.markdown(f"{n}. {a}")
    st.info(f"**{T('sec_report')}:** {view['report']}")

    with st.expander(T("sec_highlight")):
        st.markdown(f'<div class="gs-msg">{view["highlight_html"]}</div>', unsafe_allow_html=True)

    # ---- read aloud: the browser's own voice (no network); server audio only as an optional alternative ----
    labels = {"button": T("tts_btn"), "speaking": T("tts_speaking"), "no_voice": T("tts_no_voice"), "unsupported": T("tts_unsupported")}
    components.html(browser_tts_html(view["spoken"], lang, labels), height=120)
    with st.expander(T("read_aloud_alt")):
        if st.button("🔊 " + T("btn_listen"), key="listen"):
            with st.spinner(T("voice_loading")):
                sp = get_speech().synthesize(view["spoken"], lang)
            st.session_state["audio"] = {"lang": lang, "audio": sp.audio, "error": sp.error}
        aud = st.session_state.get("audio")
        if aud and aud["lang"] == lang:
            if aud["audio"]:
                st.audio(aud["audio"], format="audio/mp3")
            else:
                st.warning(T("voice_unavailable" if aud["error"] in ("disabled", "gtts_missing") else "voice_failed"))

    st.caption(view["disclaimer"])
    st.button("🔄 " + T("btn_another"), on_click=_reset, type="primary", use_container_width=True)

    if is_admin():                                          # technical details are staff-only
        with st.expander("🔧 " + T("tech_title")):
            st.json({"schema": res["schema"], "suppressed": res.get("suppressed"), "schema_errors": res.get("schema_errors")}, expanded=False)

    st.divider()
    _render_feedback(res)
    _render_contribution(res)


def _render_feedback(res: dict) -> None:
    store = storage_status()
    if not store["enabled"]:
        st.caption(T("storage_off"))
        return
    level, schema = res["risk"]["level"], res["schema"]
    ctx = dict(model_id=res["ml"].get("model_id"), model_name=res["model"]["name"], message_category=schema["message_category"],
               language=res["language"]["code"], rules_version=res.get("rules_version"))
    st.subheader(T("fb_title"))
    st.caption(T("fb_voluntary"))
    consent = st.checkbox(T("fb_consent"), key="fb_consent")
    comment = st.text_input(T("fb_comment"), key="fb_comment", max_chars=500)

    def _save(ftype):
        if not consent:
            st.warning(T("fb_need_consent"))
            return False
        try:
            save_feedback_v2(ftype, level, consent=True, comment=comment, **ctx)
            return True
        except (ConsentRequired, FeedbackStorageError, InputValidationError):
            st.error(T("fb_error"))
            return False

    if st.session_state.get("fb_done"):
        st.success(T("fb_thanks"))
    else:
        st.markdown(f"**{T('fb_q_result')}**")
        c1, c2 = st.columns(2)
        if level == "UNKNOWN":
            opts = (("fb_unknown_genuine", "correct_legitimate", c1), ("fb_unknown_suspicious", "missed_suspicious", c2))
        else:
            grp = _RESULT_FB["flagged" if level in ("HIGH", "MEDIUM") else "clear"]
            opts = (("fb_result_correct", grp[0], c1), ("fb_result_wrong", grp[1], c2))
        for key, ftype, col in opts:
            if col.button(("👍 " if "correct" in ftype and "missed" not in ftype else "👎 ") + T(key), key=f"fb_{ftype}", use_container_width=True) and _save(ftype):
                st.session_state["fb_done"] = True
                st.rerun()
    if st.session_state.get("fb_expl_done"):
        st.success(T("fb_thanks"))
    else:
        st.markdown(f"**{T('fb_q_expl')}**")
        d1, d2 = st.columns(2)
        if d1.button("👍 " + T("fb_expl_yes"), key="fb_ey", use_container_width=True) and _save("explanation_helpful"):
            st.session_state["fb_expl_done"] = True
            st.rerun()
        if d2.button("👎 " + T("fb_expl_no"), key="fb_en", use_container_width=True) and _save("explanation_not_helpful"):
            st.session_state["fb_expl_done"] = True
            st.rerun()


def _render_contribution(res: dict) -> None:
    if not storage_status()["enabled"]:
        return
    with st.expander(T("contrib_title")):
        st.write(T("contrib_text"))
        st.markdown(f"**{T('contrib_preview')}**")
        st.markdown(f'<div class="gs-msg">{e(redact_for_storage(res["text"]))}</div>', unsafe_allow_html=True)
        if st.session_state.get("contrib_done"):
            d = st.session_state["contrib_done"]
            if d["duplicate"]:
                st.info(T("contrib_dup"))
            else:
                st.success(T("contrib_done"))
                st.code(d["token"], language=None)
            return
        label = st.radio(T("contrib_label"), ["legitimate", "suspicious", "fraud", "not_sure"], key="contrib_label", horizontal=True,
                         format_func=lambda x: {"legitimate": T("opt_legit"), "suspicious": T("opt_susp"), "fraud": "🚨 " + T("risk_HIGH"), "not_sure": T("opt_unsure")}[x])
        agree = st.checkbox(T("contrib_consent"), key="contrib_consent")
        if st.button(T("contrib_submit"), key="contrib_btn"):
            if not agree:
                st.warning(T("fb_need_consent"))
            else:
                try:
                    st.session_state["contrib_done"] = submit_contribution(res["text"], consent_contribute=True, language=res["language"]["code"],
                                                                          suggested_label=None if label == "not_sure" else label)
                    st.rerun()
                except (ConsentRequired, FeedbackStorageError, InputValidationError):
                    st.error(T("fb_error"))
