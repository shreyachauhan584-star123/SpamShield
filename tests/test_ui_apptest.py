"""Real-Streamlit UI tests (Streamlit's AppTest). WRITTEN BUT NOT RUN in the development sandbox (Streamlit unavailable there).
Run them with:  pytest tests/test_ui_apptest.py"""
import pytest

st_testing = pytest.importorskip("streamlit.testing.v1")


def _app(path="pages/1_Analyze_SMS.py"):
    return st_testing.AppTest.from_file(path, default_timeout=90)


def test_home_renders_without_exception_and_shows_three_input_tabs():
    at = _app().run()
    assert not at.exception and len(at.tabs) >= 3


def test_pasted_scam_message_gets_a_high_risk_result():
    at = _app().run()
    at.text_area(key="sms_input").set_value("Your account will be blocked. Update KYC immediately: http://sbi-kyc-update.xyz/login")
    at.button(key="go_paste").click().run()
    assert not at.exception
    assert "HIGH" in at.session_state["result"]["risk"]["level"]


def test_empty_message_shows_a_friendly_error_not_a_crash():
    at = _app().run()
    at.button(key="go_paste").click().run()
    assert not at.exception and at.error


def test_staff_pages_are_blocked_for_ordinary_users():
    for page in ("pages/3_Model_Insights.py", "pages/5_Staff.py"):
        at = _app(page).run()
        assert not at.exception and at.error and not at.dataframe


def test_learn_and_about_pages_render():
    for page in ("pages/2_Fraud_Awareness.py", "pages/4_About.py"):
        assert not _app(page).run().exception
