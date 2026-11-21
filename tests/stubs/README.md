Minimal stand-in for `streamlit`, used ONLY by tests/test_ui_logic.py when real Streamlit is not installed.
It executes the page code to catch logic errors (NameError, KeyError, wrong data flow). It does NOT check layout,
widget behaviour or the real Streamlit API - use the AppTest tests (tests/test_ui_apptest.py) with real Streamlit for that.
