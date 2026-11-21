"""GramSuraksha AI V2 - entry point: look & feel, minimal sidebar, navigation.

Run:  streamlit run app.py
Ordinary users see: Check a message, Learn & Protect, About. Staff pages exist only after an authenticated staff login
(add ?admin=1 to the URL to reveal the login box; login is disabled unless GRAMSURAKSHA_ADMIN_PASSWORD_HASH is set).
"""
import streamlit as st

from src.services.translation_service import tr
from src.ui.guard import is_admin, sidebar_admin_login
from src.ui.styles import build_css

st.set_page_config(page_title="GramSuraksha AI", page_icon="🛡️", layout="centered", initial_sidebar_state="auto")

choice = st.sidebar.radio("Language / भाषा", ["English", "हिन्दी"], key="lang_radio", horizontal=True)
st.session_state["ui_lang"] = "hi" if choice == "हिन्दी" else "en"
lang = st.session_state["ui_lang"]
t = lambda k, **kw: tr(k, lang, **kw)

size = st.sidebar.radio(t("sidebar_text_size"), [0, 1, 2], key="text_size", horizontal=True,
                        format_func=lambda i: [t("text_normal"), t("text_large"), t("text_xlarge")][i])
st.markdown(build_css(size), unsafe_allow_html=True)
st.sidebar.caption("🔒 " + t("sidebar_privacy"))

if is_admin() or "admin" in st.query_params:
    sidebar_admin_login()

pages = [
    st.Page("pages/1_Analyze_SMS.py", title=t("nav_analyze"), icon="🛡️", default=True),
    st.Page("pages/2_Fraud_Awareness.py", title=t("nav_awareness"), icon="📚"),
    st.Page("pages/4_About.py", title=t("nav_about"), icon="ℹ️"),
]
if is_admin():
    pages += [st.Page("pages/3_Model_Insights.py", title=t("nav_insights"), icon="📊"), st.Page("pages/5_Staff.py", title=t("nav_admin"), icon="🛠️")]
st.navigation(pages).run()
