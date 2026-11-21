import importlib.util
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def test_release_zip_excludes_dev_clutter_and_user_data_but_keeps_production_artifacts(tmp_path):
    rel = _load("make_release")
    stray = [ROOT / "data" / "feedback.db", ROOT / ".env"]
    for s in stray:
        s.write_text("secret user data")
    try:
        names = set(rel.build(tmp_path / "r.zip"))
    finally:
        for s in stray:
            s.unlink()
    assert not [n for n in names if n.startswith((".git/", ".venv/")) or "__pycache__" in n or n.endswith((".db", ".pyc"))]
    assert ".env" not in names and "data/feedback.db" not in names
    for must in ("README.md", "requirements.txt", ".env.example", ".gitignore", "app.py", "models/baseline/model.joblib", "models/baseline/model.joblib.sha256",
                 "models/baseline/metrics.json", "data/rules/fraud_rules.json", "data/metadata/datasets.json", "docs/MODEL_CARD.md"):
        assert must in names, must
    with zipfile.ZipFile(tmp_path / "r.zip") as z:
        assert z.testzip() is None and all(n.startswith("GramSurakshaAI/") for n in z.namelist())


def test_model_card_is_generated_from_real_metrics():
    card = (ROOT / "docs" / "MODEL_CARD.md").read_text(encoding="utf-8")
    m = json.loads((ROOT / "models" / "baseline" / "metrics.json").read_text(encoding="utf-8"))
    assert m["model_id"] in card and m["selected"].replace("|", " / ") in card and m["dataset"]["version"] in card
    if m["evaluation_status"] != "real_data":
        assert "PRELIMINARY EVALUATION" in card
