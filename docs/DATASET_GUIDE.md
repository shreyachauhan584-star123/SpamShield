# Dataset guide

## Layout
`data/raw` (manual downloads, git-ignored) · `external` (third-party sets you vetted) · `synthetic` (author-written, bundled) · `validated` (human-verified exports) ·
`processed` · `train|validation|test` (generated) · `metadata` (registry, versions, split manifest).

## Provenance (never mix silently)
`real` - collected from real messages · `manually_verified` - labels reviewed by a human · `synthetic` - written for coverage/illustration · `augmented` - automatically derived.
Only `real` and `manually_verified` may form validation/test once enough exist. Bundled data is **synthetic** (205 messages: `demo_sms_dataset.csv`, `hindi_hinglish_synthetic_v2.csv`).

## Labels
`legitimate` (personal/transactional/service/awareness) · `promotional` · `spam` (unsolicited bulk, e.g. UCI "spam") · `suspicious` (possible scam, weak evidence) · `fraud` (clear attempt to defraud).
V1 names `ham`, `financial_fraud` still load. `spam` is never assumed to be fraud.

## Importing data
```
python -m src.data.prepare --extra-csv my.csv --extra-provenance manually_verified     # validate, version, split
python -m src.models.train_model --extra-csv my.csv --extra-provenance manually_verified
```
CSV: UTF-8, columns `message,label` (+ optional `provenance`, `language`), <= 5 MB / 100k rows. Register licence/source in `data/metadata/datasets.json` via `src/data/registry.py`
(`DatasetRecord`); checksums detect silent edits. **Do not download datasets from unvetted sites**; verify source, licence and suitability first.

## UCI SMS Spam Collection (manual)
Download from https://archive.ics.uci.edu/dataset/228/sms+spam+collection, place `SMSSpamCollection` (or the zip) in `data/raw/`. English only; recorded as `real`, licence "CC BY 4.0 as listed on the UCI page - verify". Its "spam" is mostly promotional.

## Real Indian-fraud data
The biggest gap. Collect consented, de-identified, human-labelled Hindi/Hinglish messages (the in-app optional contribution flow + admin review produces such a file: *Staff area -> Contributions -> export*).
Need >= 30 held-out messages per language and class for a language to count as `evaluated`.

## Garhwali and other low-resource languages
No data, OCR, speech or evaluation exist. Do not fabricate examples or claim detection. Path: community-sourced messages -> native-speaker labelling -> a `LanguageConfig`, normaliser, reviewed explanations and a held-out human-evaluated test set.
