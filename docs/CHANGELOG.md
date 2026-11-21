# Changelog

## 2.0.0
**Added** dataset registry with provenance/licence/checksums, 5-label taxonomy, duplicate-aware group splits, provenance-aware evaluation policy, dataset/model versioning, experiment log; 15 feature/algorithm candidates, calibration (Brier/ECE/reliability), PR-AUC/ROC-AUC/FPR/FNR;
Hinglish and Hindi normalisers, contextual negation/awareness analysis, language registry; 4 new rule families (loan, authority impersonation, job fee, investment) and wider OTP/KYC/blocking variants; 15-category message taxonomy; look-alike/encoding/malformed/multi-link URL checks; opt-in threat-intel interface;
validated structured result schema with traceable explanations and a fail-safe; screenshot OCR, voice input engines, browser read-aloud/dictation; redesigned mobile-first UI (paste/screenshot/voice, Learn & Protect with 14 lessons); typed feedback, separate-consent contributions, admin review, audit log, retention, admin auth, DB backup;
optional transformer fine-tuning script; Dockerfile, `packages.txt`, release packaging, generated model card.
**Changed** risk levels `LOW/CAUTION/HIGH/UNCERTAIN` -> `LOW/MEDIUM/HIGH/UNKNOWN` (DB migrated automatically); `ham`->`legitimate`, `financial_fraud`->`fraud` (old names still accepted); metrics schema v2; developer controls (model chooser, dev checkbox) removed from the public UI.
**Fixed** the Hindi negator "न" was dropped by the tokenizer; `to_binary("ham")` compatibility; near-duplicate similarity depended on corpus IDF; category precedence (scam theme beats the link used to deliver it).
**Removed** `seaborn` (one heat-map, replaced by matplotlib); `train_all`; V1 lowercase docs (superseded); `GRAMSURAKSHA_DEV_MODE`.
**Known gaps** see `docs/IMPLEMENTATION_STATUS.md`.

## 1.0.0
Initial prototype: baseline models, rules, URL analysis, bilingual UI, opt-in feedback.
