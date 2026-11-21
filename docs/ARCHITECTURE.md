# Architecture (V2)

V2 extends the V1 repository in place. The proposed `core/ nlp/ detection/ multimodal/ ...` tree was **not** adopted wholesale: V1's `src/`
layout already separated concerns, and moving ~50 files would have broken every import for no functional gain. New V2 code lives in new
modules under `src/`. Mapping from the requested layout:

| Requested | Where it is |
|---|---|
| `config/settings.py`, `languages.py`, `detection_rules.yaml` | `config.py`, `src/nlp/languages.py`, `data/rules/fraud_rules.json` (JSON instead of YAML to avoid a dependency) |
| `core/analysis_engine, risk_engine, prediction_service, result_schema` | `src/services/analysis_service.py`, `src/security/risk_assessment.py`, `src/models/predict.py`, `src/services/result_schema.py` |
| `nlp/*` | `src/nlp/{text_processing,language_detection,hindi_normalization,hinglish_normalization,contextual_analysis,languages}.py` |
| `models/{baseline,transformers,training,evaluation,registry}` | `models/baseline|advanced|registry/` (artifacts), `src/models/{train_model,evaluation,registry,model_loader,transformer_training}.py` |
| `detection/*` | `src/security/{fraud_rules,url_analysis,threat_intel,categories,risk_assessment}.py` |
| `multimodal/*` | `src/multimodal/{image_processing,ocr_service,speech_recognition,text_to_speech}.py` (+ `src/services/speech_service.py` gTTS fallback) |
| `explainability/*` | `src/explainability/`, explanation templates live in `data/rules/fraud_rules.json` and `src/locales/*.json` |
| `feedback/*` | `src/feedback/{feedback_service,review_service,dataset_export}.py` |
| `services/privacy_service` | `src/services/privacy_service.py` (+ `admin_auth.py`, `feature_status.py`) |
| `database/` | `src/database/{db,feedback}.py` (versioned migrations) |
| `ui/{home,results,education,admin}.py` | `src/ui/*.py`; thin entry scripts in `pages/` |

## Request flow

```
paste / screenshot (OCR, user edits) / voice (STT, user edits)
        -> validate_message -> detect_language (+ manual override)
        -> rules (original text, then normalised Hinglish/Hindi variant; negation + awareness aware)
        -> URL analysis (static, offline; optional opt-in threat intel)
        -> baseline model (raw score, optional calibrated probability)  [ignored if the language is not evaluated]
        -> assess_risk  (LOW / MEDIUM / HIGH / UNKNOWN; model alone never HIGH)
        -> message category, recommendations (traceable to a rule id / level / general advice)
        -> build_schema + validate_result  (inconsistent result => UNKNOWN, never shown)
        -> build_view (EN/HI text) -> UI
```
Nothing in this path writes to disk. Writes happen only in `src/feedback/*` after explicit consent.

## Taxonomy (kept consistent everywhere)
* Dataset labels: `legitimate, promotional, spam, suspicious, fraud` (V1 `ham`, `financial_fraud` accepted as synonyms). ML target: legitimate (0) vs flagged (1).
* Risk levels: `LOW, MEDIUM, HIGH, UNKNOWN` - code, locales, DB constraints, feedback, tests (V1 `CAUTION/UNCERTAIN` migrated by DB migration v2).
* Message categories: 15 requested scam types + `INVESTMENT_SCAM`, `SUSPICIOUS_UNSPECIFIED`, `NO_FRAUD_SIGNALS`, `UNDETERMINED` (`src/security/categories.py`).

## Fallback behaviour
Missing model -> rules only (note shown). Missing OCR/STT/TTS -> feature hidden or text fallback with explanation. Missing DB -> feedback hidden.
Failing subsystem never yields a silent classification: unsupported language or inconsistency => UNKNOWN.

## Extension points
`SpeechService`/`STTEngine` (speech), `ThreatIntelProvider` (link reputation), `LanguageConfig` (languages), `AdvancedPredictor` (transformers), `detect_language` (swap in a trained identifier).
