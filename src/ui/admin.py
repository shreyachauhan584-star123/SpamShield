"""Staff-only pages: model insights and operations. Every entry point calls require_admin()."""
from __future__ import annotations

import json

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from config import METADATA_DIR, MODELS_DIR
from src.data import registry
from src.data.dataset_validation import validate_upload
from src.data.preprocess import clean_dataframe
from src.explainability.feature_explanations import global_importance
from src.feedback import dataset_export, review_service as rv
from src.models import registry as model_registry
from src.models.evaluation import confusion_matrix_figure, evaluate_pipeline_on_dataframe, reliability_figure
from src.nlp import languages
from src.services import admin_auth, privacy_service
from src.services.feature_status import feature_status
from src.ui.guard import require_admin
from src.ui.state import get_runtime


def render_insights() -> None:
    require_admin()
    st.title("📊 Model Insights")
    st.caption("Staff only. English only. Metrics shown here are read from models/baseline/metrics.json - never invented.")
    m = get_runtime().metrics
    if not m:
        st.warning("The model has not been evaluated yet. Run `python -m src.models.train_model`.")
        return
    if m["evaluation_status"] != "real_data":
        st.error("**PRELIMINARY evaluation.** " + m["evaluation_note"])
    ds = m["dataset"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Model version", m["model_id"]); c2.metric("Dataset version", ds["version"])
    c3.metric("Rows", ds["stats"]["rows"]); c4.metric("Split (train/val/test)", " / ".join(str(ds["splits"]["sizes"][k]) for k in ("train", "validation", "test")))
    st.json({"provenance": ds["stats"].get("provenance"), "binary_distribution": ds["stats"]["binary_distribution"], "imbalance_ratio": ds["stats"]["imbalance_ratio"],
             "languages": ds["stats"].get("language_distribution"), "datasets_used": ds["datasets_used"]}, expanded=False)

    st.header("Model comparison (validation split)")
    rows = [{"candidate": k, "V1 baseline": c["is_v1_baseline"], "selected": k == m["selected"],
             **{n: c["validation"].get(n) for n in ("pr_auc", "roc_auc", "precision", "recall", "f1", "f2", "fpr", "fnr", "accuracy")},
             "cv_f2": c["cv_f2_mean"], "ms/msg": c["inference_ms_per_message"]} for k, c in m["candidates"].items()]
    df = pd.DataFrame(rows).set_index("candidate").sort_values("pr_auc", ascending=False)
    st.dataframe(df.style.format({c: "{:.3f}" for c in df.columns if df[c].dtype == float}))
    st.caption("Selection: " + m["selection_rule"])
    sel = st.selectbox("Inspect candidate", list(m["candidates"]), index=list(m["candidates"]).index(m["selected"]))
    cand = m["candidates"][sel]
    a, b = st.columns(2)
    split = a.radio("Split", ["validation", "test"], horizontal=True)
    fig = confusion_matrix_figure(cand[split]["confusion_matrix"], f"{split}")
    a.pyplot(fig); plt.close(fig)
    if "pr_curve" in cand[split]:
        b.line_chart(pd.DataFrame({"precision": cand[split]["pr_curve"]["precision"]}, index=[round(x, 3) for x in cand[split]["pr_curve"]["recall"]]))

    st.header("Calibration")
    cal = m["calibration"]
    st.write(f"Method **{cal['method']}**, status **{cal['status']}**. {cal['note']}")
    cc = st.columns(2)
    for col, sp in zip(cc, ("validation", "test")):
        r = cal[sp]
        col.write(f"{sp}: Brier raw {r['raw']['brier']:.3f} → calibrated {r['calibrated']['brier']:.3f}; ECE {r['raw']['ece']:.3f} → {r['calibrated']['ece']:.3f} (n={r['calibrated']['n']})")
        f = reliability_figure(r["raw"]["reliability"], r["calibrated"]["reliability"], f"Reliability ({sp})")
        col.pyplot(f); plt.close(f)

    st.header("Feature importance (selected model, word features)")
    rt = get_runtime()
    imp = global_importance(rt.baseline.pipeline) if rt.baseline else None
    if imp:
        x, y = st.columns(2)
        x.dataframe(pd.DataFrame(imp["toward_flagged"]), hide_index=True); y.dataframe(pd.DataFrame(imp["toward_legitimate"]), hide_index=True)

    st.header("Languages")
    st.dataframe(pd.DataFrame(languages.support_report(m)), hide_index=True)
    st.caption(f"Per-language method: {m['per_language_method']}. 'evaluated' needs >= 30 held-out messages from NON-synthetic data.")

    st.header("Validate / evaluate your own labelled CSV")
    up = st.file_uploader("CSV/TSV (message, label[, provenance])", type=["csv", "tsv"], key="insights_upload")
    if up is not None:
        data, rep = validate_upload(up.getvalue(), up.name)
        for e in rep.errors:
            st.error(e)
        for w in rep.warnings:
            st.warning(w)
        if rep.ok:
            st.json(rep.stats, expanded=False)
            if rt.baseline and st.button("Evaluate the current model on this file"):
                clean, _ = clean_dataframe(data)
                ev = evaluate_pipeline_on_dataframe(rt.baseline.pipeline, clean)
                st.write({k: round(ev[k], 3) for k in ("accuracy", "precision", "recall", "f1", "f2", "fpr", "fnr") if ev.get(k) is not None})
                st.caption("Optimistic if these messages were in the training data. The file is not saved or used for training.")


def render_admin() -> None:
    require_admin()
    st.title("🛠️ Staff area")
    reviewer = st.text_input("Your name (recorded in the audit log)", key="reviewer_name", max_chars=60)
    tabs = st.tabs(["Status", "Feedback", "Contributions", "Datasets & models", "Privacy", "Audit"])

    with tabs[0]:
        rt = get_runtime()
        st.json(feature_status(rt), expanded=False)
        st.json({"storage": privacy_service.storage_status(), "admin_login": "enabled" if admin_auth.admin_enabled() else "disabled",
                 "rules_version": rt.rule_engine.version}, expanded=False)

    with tabs[1]:
        items = rv.list_feedback(100, only_open=True)
        st.write(f"{len(items)} open feedback item(s). Feedback never contains the message.")
        for it in items:
            c1, c2 = st.columns([5, 1])
            c1.write(f"#{it['id']} · {it['feedback_type'] or 'legacy'} · level {it['predicted_level']} · {it['message_category']} · {it['language']} · {it['comment'] or ''}")
            if c2.button("Reviewed", key=f"fr{it['id']}") and reviewer.strip():
                rv.review_feedback_item(it["id"], "reviewed", reviewer=reviewer)
                st.rerun()

    with tabs[2]:
        pend = rv.list_contributions("pending", 50)
        st.write(f"{len(pend)} pending. Texts were redacted before storage. Accepting needs a human-verified label.")
        for it in pend:
            with st.container(border=True):
                st.markdown(f"**#{it['id']}** (suggested: {it['suggested_label'] or '-'}, {it['language'] or '?'})")
                st.code(it["message_text"], language=None)
                label = st.selectbox("Verified label", ["fraud", "suspicious", "spam", "promotional", "legitimate"], key=f"vl{it['id']}")
                a, b, c = st.columns(3)
                if not reviewer.strip():
                    st.caption("Enter your name above to review.")
                elif a.button("Accept", key=f"ac{it['id']}"):
                    st.info(rv.review_contribution(it["id"], "accept", reviewer=reviewer, verified_label=label)["status"]); st.rerun()
                elif b.button("Reject", key=f"rj{it['id']}"):
                    rv.review_contribution(it["id"], "reject", reviewer=reviewer); st.rerun()
                elif c.button("Delete", key=f"dl{it['id']}"):
                    rv.admin_delete_contribution(it["id"], reviewer=reviewer); st.rerun()

    with tabs[3]:
        st.subheader("Registered datasets")
        st.dataframe(pd.DataFrame([r.__dict__ for r in registry.all_records()]), hide_index=True)
        vf = METADATA_DIR / "versions.json"
        if vf.exists():
            st.subheader("Dataset versions"); st.json(json.loads(vf.read_text()), expanded=False)
        if st.button("Export accepted contributions to data/validated/") and reviewer.strip():
            st.json(dataset_export.export_validated(reviewer))
            st.caption("Exporting does NOT train anything. Use --extra-csv explicitly to include the file in a training run.")
        st.subheader("Model versions")
        st.dataframe(pd.DataFrame(model_registry.list_models()), hide_index=True)
        st.caption(f"Active: {model_registry.active_id()}  ·  experiment log: {MODELS_DIR / 'experiments' / 'log.jsonl'}")

    with tabs[4]:
        st.json(privacy_service.privacy_summary(), expanded=False)
        if st.button("Apply retention policy now") and reviewer.strip():
            st.json(privacy_service.purge_expired())

    with tabs[5]:
        st.dataframe(pd.DataFrame(rv.audit_records(200)), hide_index=True)
