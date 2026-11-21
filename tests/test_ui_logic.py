"""Runs every page's code against the stub in a subprocess. Skipped when real Streamlit is installed (use test_ui_apptest.py)."""
import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_all_pages_run_against_the_stub_and_obey_privacy_and_admin_guards():
    if importlib.util.find_spec("streamlit") is not None:
        pytest.skip("real Streamlit is installed; the AppTest tests cover the UI")
    env = {**os.environ, "GRAMSURAKSHA_DB_PATH": os.path.join(tempfile.mkdtemp(), "f.db"), "GRAMSURAKSHA_TTS": "none"}
    r = subprocess.run([sys.executable, str(ROOT / "tests" / "stubs" / "ui_smoke.py")], capture_output=True, text=True, env=env, cwd=ROOT, timeout=300)
    assert r.returncode == 0, r.stdout[-1500:] + r.stderr[-1500:]
    assert "SMOKE_OK" in r.stdout and r.stdout.count("STOPPED (guard)") == 3      # logged out x2 + expired session
