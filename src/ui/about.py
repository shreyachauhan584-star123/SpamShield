
"""About, privacy, limits, help, and self-service deletion."""
from __future__ import annotations

import streamlit as st

from src.feedback.review_service import delete_contribution
from src.ui.state import T


def render_page() -> None:
    st.title("ℹ️ " + T("about_title"))
    st.write(T("about_what"))

    with st.container(border=True):
        st.subheader("🔒 " + T("about_privacy_title"))

        for k in (
            "about_p1",
            "about_p2",
            "about_p3",
            "about_p4",
            "about_p5"
        ):
            st.markdown(f"- {T(k)}")

    with st.container(border=True):
        st.subheader("⚖️ " + T("about_limit_title"))

        for k in (
            "about_l1",
            "about_l2",
            "about_l3"
        ):
            st.markdown(f"- {T(k)}")

    with st.container(border=True):
        st.subheader("☎️ " + T("about_help_title"))
        st.info(T("about_help_text"))

    with st.container(border=True):
        st.subheader("🗑️ " + T("contrib_delete_title"))

        token = st.text_input(
            T("contrib_done").split(":")[0],
            key="del_token",
            type="password"
        )

        if st.button(
            T("contrib_delete_btn"),
            key="del_btn",
            use_container_width=True
        ):
            try:
                if delete_contribution(token.strip()):
                    st.success(T("contrib_deleted"))
                else:
                    st.warning(T("contrib_not_found"))

            except Exception:
                st.error(T("fb_error"))
