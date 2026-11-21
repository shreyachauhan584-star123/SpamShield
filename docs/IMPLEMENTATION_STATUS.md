# GramSuraksha AI V2 — implementation status & final report

_Phases 1–8 were worked through in order (Phase 7 before 6 so the UI could build on it). Last full run: **258 tests passed, 1 module skipped**._

## Environment constraints (affect what could be verified)
Python 3.12 (project targets 3.11+), **no network**, **no Streamlit**, **no pytest** (a minimal stand-in ran the suite), Tesseract 5.3.4 with **English only**, no torch/transformers/gTTS/speech engines, no Docker, no browser.
A clean-virtualenv install and a real `streamlit run` were therefore **not possible**.

## Fully implemented AND tested here
* Dataset pipeline: registry/provenance/licence/checksums, 5-label taxonomy + V1 synonyms, validation, duplicate + near-duplicate handling, group-aware stratified splits, provenance policy, versions, manifests.
* Training: 15 candidates, group CV, validation-based selection (FNR floor/PR-AUC/F2), calibration (Brier/ECE/reliability), ROC/PR-AUC/FPR/FNR, experiment log, model registry (archive/activate/rollback), SHA-256 verified loading, V1 baselines kept.
* NLP: Hinglish + Hindi normalisation, negation scope, awareness messages, language registry (no unsupported claims), tokenizer negator fix.
* Detection: 21 rules (15 categories), URL analysis (look-alike/encoding/malformed/multi-link/Unicode), threat-intel interface (mocked transport), validated schema, UNKNOWN fail-safe, traceable explanations, category taxonomy.
* Multimodal: image validation, **real OCR on generated light/dark screenshots**, audio validation, pluggable STT interface (tested with a fake engine), screenshot→analysis and voice→analysis pipelines, safe browser TTS/dictation HTML.
* Privacy/security: v3 DB migration (V1 DB upgrade tested), typed feedback, separate-consent contributions, admin review/export/audit, retention, deletion, admin auth + lockout, redaction, DB backup, static audits (no secrets, no content logging), release packaging.
* Docs, model card generated from metrics, notebooks (executed outside Jupyter).

## Implemented but depends on external setup / not exercised
| Item | Needs |
|---|---|
| Streamlit UI (layout, `st.navigation`, widgets, responsive CSS) | real Streamlit + browser. Page logic ran against a stub; `tests/test_ui_apptest.py` written, **not run** |
| Hindi OCR | Tesseract `hin` pack (absent here) |
| Voice input (faster-whisper / Vosk) | engine install + models (absent) |
| Browser read-aloud / dictation | real browser; Hindi voice on the device |
| gTTS audio | internet |
| Safe Browsing lookups | API key + internet (only mocked transport tested) |
| Transformer fine-tuning/inference | torch, transformers, model download (script never run) |
| Docker / Streamlit Cloud / HF Spaces | those platforms (files written, unverified) |
| `pip-audit` | internet |

## Partially implemented
* **Language identification**: improved heuristic only (still lexicon/script based). A trained identifier is not installable offline.
* **Calibration**: implemented and reported, but status is `preliminary_small_sample` (41 validation rows) so it never drives decisions yet.
* **Real-data evaluation**: machinery is in place; no real labelled data was available, so all metrics are `preliminary_synthetic_only`. English/Hindi/Hinglish have dedicated held-out coverage (42/19/21 messages) but only at status `limited`.
* **Persistence for hosted deployments**: SQLite + documented volume/`storage=none`; no network DB backend.
* **Manual UI testing**: checklist written in docs/TESTING.md; not performed.

## Not implemented (and why)
* PaddleOCR (heavy stack; Tesseract chosen, interface allows adding it). * YAML rules (JSON used, no new dependency). * The exact requested directory tree (justified in ARCHITECTURE.md).
* Regional languages incl. Garhwali: registry entries only, **deliberately no data or claims**. * Postgres/other DB backend. * Clean-venv install verification, Windows verification, real-browser verification (environment limits).

## Acceptance criteria (honest)
[x] V1 functionality operational (V1 tests kept; DB migrated) · [x] core pipeline end to end · [~] EN/HI/Hinglish dedicated evaluation coverage (synthetic, `limited`) · [x] dataset validation + training · [x] reproducible baseline comparison · [x] leakage-resistant splits ·
[x] calibration/uncertainty handled responsibly · [x] context-aware rules · [x] negation tested · [x] safe, explainable URL analysis · [x] screenshot upload + OCR (English tested; Hindi needs pack) · [x] OCR text editable before analysis ·
[~] voice input (interface + validation tested; no engine here) · [~] TTS (browser/gTTS untested live) · [x] results explain risk/evidence/actions · [~] HI/EN explanations usable (needs native review) · [~] redesigned UI (written; not rendered in real Streamlit) ·
[x] consent-based feedback, not auto-trained · [x] privacy/security controls · [~] DB persistence (documented; host-dependent) · [x] unit/integration/security tests pass · [~] README accurate (setup commands not executed on Windows/clean venv) · [x] clean release packaging · [~] no unsupported claims (kept explicit).

## Files
**Created (major):** `src/data/{registry,splitting,prepare}.py`, `src/models/{registry,transformer_training}.py`, `src/nlp/{hindi_normalization,hinglish_normalization,contextual_analysis,languages}.py`, `src/security/{categories,threat_intel}.py`,
`src/services/{result_schema,privacy_service,admin_auth,feature_status}.py`, `src/multimodal/*`, `src/feedback/*`, `src/ui/{home,results,education,about,admin,guard}.py`, `pages/5_Staff.py`, `scripts/{make_release,generate_model_card,make_admin_hash,backup_db,make_synthetic_v2}.py`,
`data/synthetic/hindi_hinglish_synthetic_v2.csv`, `data/metadata/*`, `Dockerfile`, `packages.txt`, `docs/*` (uppercase set), 9 new test modules, `tests/stubs/`.
**Modified (major):** `config.py`, `src/models/{train_model,evaluation,predict,model_loader}.py`, `src/data/{load_data,dataset_validation,preprocess}.py`, `src/nlp/{text_processing,language_detection}.py`, `src/security/{fraud_rules,url_analysis,risk_assessment,safety_recommendations}.py`,
`src/services/analysis_service.py`, `src/database/{db,feedback}.py`, `data/rules/fraud_rules.json`, locales, `app.py`, `pages/*`, notebooks, requirements, `.env.example`, `.gitignore`.
**Removed:** `seaborn` use, `train_all`, V1 lowercase docs, dev-mode UI controls, `data/custom/` (moved to `data/synthetic/`).
**Dependencies:** added `scipy` (explicit), `Pillow`, `pytesseract`; optional `opencv-python-headless`, `faster-whisper`, `vosk`; removed `seaborn`.

## Commands
```
pip install -r requirements.txt && streamlit run app.py          # Windows: .venv\Scripts\activate first
python -m src.models.train_model && python scripts/generate_model_card.py
pytest
python scripts/make_release.py
```
## Next step if work resumes
1. Run real `pytest` and `streamlit run app.py`; fix whatever the real UI shows (checklist in docs/TESTING.md). 2. Install Tesseract `hin`; test Hindi screenshots. 3. Obtain real labelled Hindi/Hinglish data → retrain → re-read `evaluation_status`.
4. Native-speaker review of Hindi strings. 5. Try the transformer script on a machine with torch + network. 6. `pip-audit`.
