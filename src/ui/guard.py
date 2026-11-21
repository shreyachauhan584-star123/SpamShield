"""Administrator session handling for the Streamlit UI. Staff pages are never shown to ordinary users."""
from __future__ import annotations

import time

import streamlit as st

from src.services import admin_auth
from src.ui.state import T

SESSION_SECONDS = 30 * 60


def is_admin() -> bool:
    if not st.session_state.get("is_admin"):
        return False
    if time.time() - st.session_state.get("admin_since", 0) > SESSION_SECONDS:      # idle/expired session
        st.session_state["is_admin"] = False
        return False
    return True


def require_admin() -> None:
    if not is_admin():
        st.error(T("admin_required"))
        st.stop()


def sidebar_admin_login() -> None:
    """Rendered only when ?admin=1 is in the URL or an admin session already exists."""
    with st.sidebar.expander("🔐 " + T("admin_login"), expanded=not is_admin()):
        if is_admin():
            if st.button(T("admin_logout"), key="admin_logout"):
                st.session_state["is_admin"] = False
                st.rerun()
            return
        if not admin_auth.admin_enabled():
            st.caption(T("admin_disabled"))
            return
        pw = st.text_input(T("admin_password"), type="password", key="admin_pw")
        if st.button(T("admin_btn_login"), key="admin_btn"):
            ok, code = admin_auth.try_login(pw)
            if ok:
                st.session_state.update(is_admin=True, admin_since=time.time())
                st.rerun()
            st.error(T("admin_locked" if code == "locked" else "admin_bad"))
