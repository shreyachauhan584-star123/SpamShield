# ML pipeline

## 1. Data -> versioned splits (`python -m src.data.prepare`)
validate columns/labels -> drop empty/unknown -> drop contradictory duplicates -> drop exact duplicates -> tag language -> dataset version (`dsv-...`, content hash)
-> cluster **near-duplicates** (character 3-5-gram cosine >= 0.90, no IDF, punctuation-insensitive) -> stratified **group** split 60/20/20 (a cluster never spans splits).
Provenance policy: if >= 60 real/manually-verified rows exist (>= 15 per class) validation/test contain only those and synthetic/augmented rows go to train; otherwise the run is
labelled `preliminary_synthetic_only`. Manifests: `data/metadata/{datasets,versions,splits}.json`; split files in `data/{train,validation,test}/` (git-ignored).

## 2. Training (`python -m src.models.train_model`)
Candidates = 5 feature sets (`word_1`, `word_1_2` = V1, `word_1_3`, `char_2_5`, `word+char`) x 3 algorithms (Naive Bayes, Logistic Regression, Linear SVM; class-weighted where supported).
Hyper-parameters by grid search with group-aware stratified CV on **train** (scoring F2; also F1, PR-AUC, ROC-AUC). Evaluation on **validation**; every run is appended to `models/experiments/log.jsonl`.
**Selection** (never accuracy alone, never the test set): FNR <= 0.15 first, then PR-AUC (differences < 0.01 are ties), then F2, then CV-F2, then lowest FNR.

## 3. Calibration
`CalibratedClassifierCV` (sigmoid below 1000 train rows, isotonic above) fitted by group CV on train; Brier, ECE (5 bins when n < 200) and reliability curves computed on validation and test.
Status: `validated` (>= 200 validation rows and better Brier than raw), `preliminary_small_sample`, or `rejected_worse_than_raw`. The app uses calibrated values for decisions only when `validated`;
raw scores are never labelled probabilities; `confidence` in the result schema is `null` unless calibration is validated.

## 4. Versioning
`models/registry/<model_id>/` archives model, calibrator, checksums, metrics, metadata; `models/baseline/` holds the **active** version (what the app loads, SHA-256 verified).
Roll back: `python -c "from src.models.registry import activate_model; activate_model('m-...')"`. `docs/MODEL_CARD.md` is generated from the active `metrics.json`.

## 5. NLP
Normalisation (`normalize_for_model`): NFKC -> script normalisers -> lower-case -> placeholders for URL/phone/number/currency. Hinglish: spelling variants (apka, acct, kro, nhi...), SMS shorthand
(k.y.c), repeated letters, run-together words (accountband) - **tokens are renamed or split, never dropped**. Hindi: nukta/chandrabindu/nasal variants, loan-word spellings, Devanagari digits.
The tokenizer keeps the one-letter Hindi negator "न" (found and fixed during V2 testing). Negation scope and fraud-awareness context: `src/nlp/contextual_analysis.py`.
Language detection is still a heuristic (script ratios + normalised Hinglish lexicon + orthographic cues); a trained identifier (fastText/langid) is the recommended upgrade and fits behind `detect_language`.

## 6. Transformers (optional, untested here)
```
pip install -r requirements-advanced.txt
python -m src.models.transformer_training --model-name google/muril-base-cased --allow-download --epochs 3
```
Model ids to verify on huggingface.co: `google/muril-base-cased`, `ai4bharat/indic-bert`, `bert-base-multilingual-cased`. Downloading is an explicit admin action; the app never downloads at startup.
It trains on the **same splits** and reports the same metrics into `models/advanced/metrics.json` for comparison. The user interface does not offer transformers; they are reported in the staff status panel only.
Until the training script has been run and its metrics reviewed, the transformer path must be treated as unverified.

## 7. OCR / speech
OCR: Tesseract via `pytesseract` (free, CPU-only, English + Hindi pack, simple install on Windows/Linux). PaddleOCR would likely read Hindi better but needs a heavy deep-learning stack; it can be added behind `extract_text`.
Variants (contrast, inverted for dark mode, adaptive threshold) are tried and the one with the best mean word confidence wins; the text is always shown for the user to edit. Speech-to-text: pluggable offline engines
(faster-whisper, Vosk) - none is installed by default; browser dictation is offered otherwise. Read-aloud uses the browser's own voices and says so when no Hindi voice exists.
