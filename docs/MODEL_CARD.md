# Model card - m-20261107-c9c546ec

_Generated from `models/baseline/metrics.json` on 2026-11-07T05:54:19+00:00 (do not edit by hand; run `python scripts/generate_model_card.py`)._

> **PRELIMINARY EVALUATION.** PRELIMINARY: not enough real/verified data, so validation/test are drawn from the same (synthetic-dominated) pool. Treat metrics as a pipeline check, not as evidence of real-world accuracy.

## Intended use
A decision *aid* that helps people judge whether an SMS may be a scam and what to do next. It never blocks or reports anything automatically, never says a message is safe, and returns UNKNOWN when it cannot assess.

## Data
* Dataset version `dsv-fc8d33ce99`, 205 messages; provenance counts: `{'synthetic': 205}`.
* Split (near-duplicate-grouped, stratified): train 123 / validation 41 / test 41.
* Language mix: `{'en': 110, 'hinglish': 50, 'hi': 43, 'mixed': 2}`. Class balance (legitimate/flagged): `{'legitimate': 78, 'flagged': 127}`.
* Sources: `{'synthetic-demo-v1': 'synthetic-demo-v1@65f77172', 'synthetic-hi-hinglish-v2': 'synthetic-hi-hinglish-v2@0964008d'}`. Seed 42.

## Selection
Rule: validation split; candidates with FNR <= 0.15 first, then highest PR-AUC (differences < 0.01 are treated as ties), then F2, then CV-F2, then lowest FNR. Accuracy is reported but never used to choose.
Selected: **logistic_regression / word_1_3** (algorithm / feature set).

## Candidates (validation split; the test split was not used for selection)

| candidate | V1 baseline | PR-AUC | ROC-AUC | precision | recall | F2 | FPR | FNR | accuracy |
|---|---|---|---|---|---|---|---|---|---|
| logistic_regression / word+char |  | 0.989 | 0.982 | 0.889 | 0.960 | 0.945 | 0.188 | 0.040 | 0.902 |
| linear_svm / word+char |  | 0.989 | 0.982 | 0.889 | 0.960 | 0.945 | 0.188 | 0.040 | 0.902 |
| logistic_regression / word_1_2 | yes | 0.989 | 0.982 | 0.889 | 0.960 | 0.945 | 0.188 | 0.040 | 0.902 |
| linear_svm / word_1_2 | yes | 0.989 | 0.982 | 0.889 | 0.960 | 0.945 | 0.188 | 0.040 | 0.902 |
| linear_svm / word_1_3 |  | 0.989 | 0.982 | 0.893 | 1.000 | 0.977 | 0.188 | 0.000 | 0.927 |
| logistic_regression / word_1 |  | 0.988 | 0.980 | 0.889 | 0.960 | 0.945 | 0.188 | 0.040 | 0.902 |
| **logistic_regression / word_1_3** |  | 0.988 | 0.980 | 0.893 | 1.000 | 0.977 | 0.188 | 0.000 | 0.927 |
| linear_svm / word_1 |  | 0.986 | 0.978 | 0.889 | 0.960 | 0.945 | 0.188 | 0.040 | 0.902 |
| logistic_regression / char_2_5 |  | 0.985 | 0.975 | 0.857 | 0.960 | 0.938 | 0.250 | 0.040 | 0.878 |
| linear_svm / char_2_5 |  | 0.984 | 0.972 | 0.857 | 0.960 | 0.938 | 0.250 | 0.040 | 0.878 |
| naive_bayes / word_1_2 | yes | 0.980 | 0.970 | 0.833 | 1.000 | 0.962 | 0.312 | 0.000 | 0.878 |
| naive_bayes / word_1_3 |  | 0.979 | 0.970 | 0.833 | 1.000 | 0.962 | 0.312 | 0.000 | 0.878 |
| naive_bayes / word_1 |  | 0.972 | 0.958 | 0.862 | 1.000 | 0.969 | 0.250 | 0.000 | 0.902 |
| naive_bayes / word+char |  | 0.968 | 0.955 | 0.714 | 1.000 | 0.926 | 0.625 | 0.000 | 0.756 |
| naive_bayes / char_2_5 |  | 0.964 | 0.945 | 0.758 | 1.000 | 0.940 | 0.500 | 0.000 | 0.805 |

Selected model on the held-out **test** split (n=41): precision 0.889, recall 0.960, F2 0.945, FPR 0.188, FNR 0.040, PR-AUC 0.982. With this few messages one error moves recall by several points.

### False positives vs false negatives
* **False negative** (a scam called harmless) can cost the user money: the costliest error, so a recall floor (FNR) is part of model selection and the rule engine works independently of the model.
* **False positive** (a genuine message flagged) costs time and trust; too many teach users to ignore warnings, so rules are conservative and understand negation and awareness messages.

## Calibration
Method `sigmoid` fitted by cross-validation on train; status **preliminary_small_sample**. Calibrated probabilities are shown only in technical views. Decisions use them only when status == 'validated'; 'preliminary_small_sample' means fewer than 200 validation messages.

| split | Brier raw | Brier calibrated | ECE raw | ECE calibrated | n |
|---|---|---|---|---|---|
| validation | 0.219 | 0.068 | 0.093 | 0.125 | 41 |
| test | 0.222 | 0.086 | 0.093 | 0.142 | 41 |

Raw scores are **not** probabilities and are never shown to users as such.

## Language evaluation (held-out validation + test messages)

| language | n | status | precision | recall |
|---|---|---|---|---|
| en | 42 | limited | 0.833 | 0.952 |
| hi | 19 | limited | 0.923 | 1.000 |
| hinglish | 21 | limited | 0.944 | 1.000 |
| mixed | 0 | none | - | - |

`evaluated` needs >= 30 held-out messages from non-synthetic data; `limited` = used cautiously; `none` = the model is ignored and only rules apply.

## Risk levels (`config.RiskThresholds`)
LOW / MEDIUM / HIGH / UNKNOWN. HIGH needs rule/URL evidence (>= 5 evidence points, or >= 6 including a limited model contribution, or two strong indicators, or one strong indicator with support); the model alone can never produce HIGH. LOW means *no obvious fraud patterns*, never *safe*. UNKNOWN: too short, unsupported language, ambiguous or lightly-tested model signal, or internal inconsistency.

## Known limitations
* Training data is small and (unless you added real data) synthetic; every number above is a pipeline check, not real-world accuracy.
* Hindi/Hinglish are the least tested; Devanagari text is assumed Hindi (Marathi/Garhwali cannot be told apart).
* Rules are heuristics and can miss new wording; URL checks are structural only.
* Library versions: `{'python': '3.12.3', 'scikit-learn': '1.8.0', 'git_commit': '34f7689'}`. Joblib files are version-sensitive and only loaded after SHA-256 verification.
