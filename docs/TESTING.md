# Testing

```
pytest                       # everything (~1 minute; trains a small model into a temp dir)
pytest tests/test_nlp_v2.py  # one module
```
| Module | Covers |
|---|---|
| `test_preprocessing` | normalisation, tokenizer, labels/synonyms, loaders, upload validation, language detection, leakage check of bundled data |
| `test_data_pipeline` | near-duplicates, provenance policy, splits, dataset version, registry, ECE/Brier/FPR/FNR, selection rule, model registry |
| `test_prediction` | artifacts/metrics schema, determinism, reproducibility, checksum refusal, explanations, HTML escaping |
| `test_nlp_v2` | Hinglish/Hindi normalisation, negation scope, awareness messages, all 15 categories, language registry (no Garhwali claim) |
| `test_fraud_rules`, `test_security_v2` | rules, URL structure, look-alikes, no network, threat-intel (mocked), schema invariants, UNKNOWN fail-safe |
| `test_risk_assessment` | risk engine, thresholds, the 10 required sample messages |
| `test_multimodal` | image/audio validation, **real OCR on generated screenshots**, pipelines screenshot->analysis and voice->analysis (pluggable engine), browser snippets |
| `test_feedback_privacy` | feedback types, consent, redaction, contributions, review, export, audit, retention, admin auth, backup, static privacy/secret audits |
| `test_app_validation` | validators, error handling, V1->V2 DB migration, translations, speech fallbacks |
| `test_release` | release ZIP exclusions/inclusions, generated model card |
| `test_ui_logic` | every page executed against a stub in a subprocess (skipped if real Streamlit is installed) |
| `test_ui_apptest` | real-Streamlit AppTest (skipped without Streamlit) |

## Results recorded in the sandbox
258 passed, 1 module skipped (`test_ui_apptest`: Streamlit not installable offline). Run with a minimal pytest stand-in because pytest could not be installed offline - **run real `pytest` once**.

## Manual UI checklist (NOT performed - no browser/Streamlit available during development)
Desktop and a ~375 px mobile viewport · Hindi typography (Devanagari rendering, large text mode) · long (2000-char) SMS · empty input · invalid input · every button · screenshot upload/remove/OCR edit · voice tab with and without an STT engine · browser read-aloud with and without a Hindi voice ·
result views LOW/MEDIUM/HIGH/UNKNOWN · feedback + contribution + deletion · staff login lockout · error/fallback states (stop the DB, remove Tesseract).
