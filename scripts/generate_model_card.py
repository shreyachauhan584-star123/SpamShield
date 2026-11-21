"""Render docs/MODEL_CARD.md from models/baseline/metrics.json so published numbers can never drift from the real run.
    python scripts/generate_model_card.py"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def f(x, n=3):
    return "-" if x is None else f"{x:.{n}f}"


def render(m: dict) -> str:
    ds, cal = m["dataset"], m["calibration"]
    L = [f"# Model card - {m['model_id']}", "",
         f"_Generated from `models/baseline/metrics.json` on {m['trained_at']} (do not edit by hand; run `python scripts/generate_model_card.py`)._", ""]
    if m["evaluation_status"] != "real_data":
        L += ["> **PRELIMINARY EVALUATION.** " + m["evaluation_note"], ""]
    L += ["## Intended use", "A decision *aid* that helps people judge whether an SMS may be a scam and what to do next. It never blocks or reports anything automatically, "
          "never says a message is safe, and returns UNKNOWN when it cannot assess.", "",
          "## Data", f"* Dataset version `{ds['version']}`, {ds['stats']['rows']} messages; provenance counts: `{ds['stats'].get('provenance')}`.",
          f"* Split (near-duplicate-grouped, stratified): train {ds['splits']['sizes']['train']} / validation {ds['splits']['sizes']['validation']} / test {ds['splits']['sizes']['test']}.",
          f"* Language mix: `{ds['stats'].get('language_distribution')}`. Class balance (legitimate/flagged): `{ds['stats']['binary_distribution']}`.",
          f"* Sources: `{ds['datasets_used']}`. Seed {m['random_seed']}.", "",
          "## Selection", f"Rule: {m['selection_rule']}", f"Selected: **{m['selected'].replace('|', ' / ')}** (algorithm / feature set).", "",
          "## Candidates (validation split; the test split was not used for selection)", "",
          "| candidate | V1 baseline | PR-AUC | ROC-AUC | precision | recall | F2 | FPR | FNR | accuracy |", "|---|---|---|---|---|---|---|---|---|---|"]
    for k, c in sorted(m["candidates"].items(), key=lambda kv: -(kv[1]["validation"].get("pr_auc") or 0)):
        v = c["validation"]
        name = k.replace('|', ' / ')
        L.append(f"| {'**'+name+'**' if k == m['selected'] else name} | {'yes' if c['is_v1_baseline'] else ''} | {f(v.get('pr_auc'))} | {f(v.get('roc_auc'))} | "
                 f"{f(v['precision'])} | {f(v['recall'])} | {f(v['f2'])} | {f(v['fpr'])} | {f(v['fnr'])} | {f(v['accuracy'])} |")
    t = m["candidates"][m["selected"]]["test"]
    L += ["", f"Selected model on the held-out **test** split (n={t['n']}): precision {f(t['precision'])}, recall {f(t['recall'])}, F2 {f(t['f2'])}, "
          f"FPR {f(t['fpr'])}, FNR {f(t['fnr'])}, PR-AUC {f(t.get('pr_auc'))}. With this few messages one error moves recall by several points.", "",
          "### False positives vs false negatives",
          "* **False negative** (a scam called harmless) can cost the user money: the costliest error, so a recall floor (FNR) is part of model selection and the rule engine works independently of the model.",
          "* **False positive** (a genuine message flagged) costs time and trust; too many teach users to ignore warnings, so rules are conservative and understand negation and awareness messages.", "",
          "## Calibration", f"Method `{cal['method']}` fitted by cross-validation on train; status **{cal['status']}**. {cal['note']}", "",
          "| split | Brier raw | Brier calibrated | ECE raw | ECE calibrated | n |", "|---|---|---|---|---|---|"]
    for sp in ("validation", "test"):
        r = cal[sp]
        L.append(f"| {sp} | {f(r['raw']['brier'])} | {f(r['calibrated']['brier'])} | {f(r['raw']['ece'])} | {f(r['calibrated']['ece'])} | {r['calibrated']['n']} |")
    L += ["", "Raw scores are **not** probabilities and are never shown to users as such.", "",
          "## Language evaluation (held-out validation + test messages)", "", "| language | n | status | precision | recall |", "|---|---|---|---|---|"]
    for k, v in m["per_language"].items():
        L.append(f"| {k} | {v['n']} | {v['status']} | {f(v.get('precision'))} | {f(v.get('recall'))} |")
    L += ["", "`evaluated` needs >= 30 held-out messages from non-synthetic data; `limited` = used cautiously; `none` = the model is ignored and only rules apply.", "",
          "## Risk levels (`config.RiskThresholds`)",
          "LOW / MEDIUM / HIGH / UNKNOWN. HIGH needs rule/URL evidence (>= 5 evidence points, or >= 6 including a limited model contribution, or two strong indicators, or one strong indicator with support); "
          "the model alone can never produce HIGH. LOW means *no obvious fraud patterns*, never *safe*. UNKNOWN: too short, unsupported language, ambiguous or lightly-tested model signal, or internal inconsistency.", "",
          "## Known limitations",
          "* Training data is small and (unless you added real data) synthetic; every number above is a pipeline check, not real-world accuracy.",
          "* Hindi/Hinglish are the least tested; Devanagari text is assumed Hindi (Marathi/Garhwali cannot be told apart).",
          "* Rules are heuristics and can miss new wording; URL checks are structural only.",
          f"* Library versions: `{m['versions']}`. Joblib files are version-sensitive and only loaded after SHA-256 verification.", ""]
    return "\n".join(L)


if __name__ == "__main__":
    m = json.loads((ROOT / "models" / "baseline" / "metrics.json").read_text(encoding="utf-8"))
    (ROOT / "docs" / "MODEL_CARD.md").write_text(render(m), encoding="utf-8")
    print("wrote docs/MODEL_CARD.md")
