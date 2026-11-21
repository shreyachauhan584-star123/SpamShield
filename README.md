# 🛡️ GramSuraksha AI V2 — SMS fraud protection for ordinary people

A privacy-first, bilingual (Hindi / English, plus Hinglish input) web app that helps people in rural India judge whether an SMS may be a scam, **explains why in simple language**,
tells them what to do, and can read the result aloud. Messages can be pasted, taken from a **screenshot (OCR)**, or spoken.

> **Read this first.** The code paths below were run and tested, but the bundled data is *synthetic* (205 hand-written messages), so every accuracy figure is a **pipeline check, not evidence of real-world accuracy**.
> The Streamlit interface could not be launched in the development sandbox (no Streamlit/browser); its page logic was exercised with a stub. See [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md) for exactly what is verified.

## 1. Overview and 2. Problem
SMS fraud (fake KYC, OTP theft, UPI "refund", electricity-cut threats, fake subsidies, lottery, fake jobs/loans, fake police, parcel fees) costs real money and targets first-time smartphone users.
Typical filters say only "spam". GramSuraksha gives a cautious risk level (**LOW / MEDIUM / HIGH / UNKNOWN** — LOW never means "safe"), the type of scam, the evidence, and concrete safe actions.

## 3. Features
Paste / screenshot / voice input · EN/HI/Hinglish rules with negation and awareness-message handling ("OTP share karo" vs "OTP share mat karo") · 21 JSON rules across 15 scam categories · offline URL analysis (look-alikes, shorteners, IP/Unicode/encoded hosts, never opened) ·
baseline ML (TF-IDF NB/LR/SVM, 15 candidates) with calibration and honest per-language status · validated, traceable result schema · browser read-aloud · Learn & Protect (14 lessons + quiz) ·
consent-based feedback (6 types) · optional message contribution with admin review, audit log, retention and deletion · staff-only model insights/operations · V1→V2 migration.

## 4. Architecture · 5. Stack · 6. Folders
See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Python 3.11+, Streamlit, scikit-learn, pandas/NumPy/SciPy, Matplotlib, Pillow + Tesseract (OCR), SQLite, pytest. Optional: faster-whisper/Vosk (voice), OpenCV, torch/transformers.
```
app.py  config.py  requirements*.txt  packages.txt  Dockerfile  .env.example
pages/   thin entry scripts          src/ui/ home, results, education, about, admin, guard, styles
src/     data/ nlp/ models/ security/ explainability/ multimodal/ feedback/ services/ database/ content/ locales/ utils/
data/    raw external synthetic validated processed train validation test metadata rules/fraud_rules.json
models/  baseline (ACTIVE model)  registry (versions)  advanced (optional)        scripts/  docs/  tests/  notebooks/
```

## 7–9. Installation

**Linux / macOS**
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```
**Windows (PowerShell)**
```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```
(If PowerShell blocks activation: `Set-ExecutionPolicy -Scope Process RemoteSigned`.) The app starts without OCR, speech engines, transformers or a database; unavailable features say so.

## 10. Environment configuration
`copy .env.example .env` (Windows) / `cp .env.example .env` (Linux) and edit. All values optional; see comments inside. Streamlit does not read `.env` by itself: export the variables in your shell, or use your host's secrets feature.

## 11–13. Dataset, training, evaluation
```bash
python -m src.data.prepare                         # validate, version, duplicate-aware split, manifests
python -m src.models.train_model                   # train 15 candidates, calibrate, version, activate
python -m src.models.train_model --no-uci          # ignore data/raw/SMSSpamCollection
python scripts/generate_model_card.py              # docs/MODEL_CARD.md from the real metrics
```
(Windows: same commands with `python`.) Real data: [docs/DATASET_GUIDE.md](docs/DATASET_GUIDE.md) (UCI manual download, `--extra-csv file.csv --extra-provenance manually_verified`). Pipeline details: [docs/ML_PIPELINE.md](docs/ML_PIPELINE.md). Notebooks in `notebooks/`.

## 14. Transformer setup (optional, unverified)
`pip install -r requirements-advanced.txt` then `python -m src.models.transformer_training --model-name google/muril-base-cased --allow-download`. Not offered to users; see ML_PIPELINE §6.

## 15. OCR setup
Install the **Tesseract program** plus language packs, then `pip install -r requirements.txt` (adds `pytesseract`).
* Linux: `sudo apt install tesseract-ocr tesseract-ocr-eng tesseract-ocr-hin`
* macOS: `brew install tesseract tesseract-lang`
* Windows: install the UB Mannheim build (https://github.com/UB-Mannheim/tesseract/wiki), tick *Hindi* under additional language data, and add `C:\Program Files\Tesseract-OCR` to `PATH`.
Check: `tesseract --list-langs` must list `eng` (and `hin` for Hindi screenshots). Without the Hindi pack the app warns that Hindi words may be misread. Optional: `pip install opencv-python-headless` for better pre-processing.

## 16. Voice setup
* **Read aloud** works in the browser with the device's own voices (a Hindi voice must be installed on the device; the app says so if not). `GRAMSURAKSHA_TTS=gtts` adds an optional internet-based fallback.
* **Voice input**: install one offline engine — `pip install faster-whisper` (model downloaded once with `GRAMSURAKSHA_HF_ALLOW_DOWNLOAD=1`) or `pip install vosk` and set `VOSK_MODEL_EN` / `VOSK_MODEL_HI`. With none installed, the Voice tab offers browser dictation (copy → paste into the Paste tab).

## 17. Database
SQLite at `GRAMSURAKSHA_DB_PATH` (default `data/feedback.db`), versioned migrations run automatically (V1 databases are upgraded). **Persistence depends on the host** — see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md). Backup: `python scripts/backup_db.py`.
Staff login: `python scripts/make_admin_hash.py`, put the printed `GRAMSURAKSHA_ADMIN_PASSWORD_HASH=...` in the environment, open the app with `?admin=1`.

## 18. Running
```bash
streamlit run app.py          # http://localhost:8501
```
## 19. Testing
```bash
pytest                         # see docs/TESTING.md (258 tests passed in the sandbox with a pytest stand-in; 1 module needs real Streamlit)
```
## 20. Deployment
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) (Streamlit Cloud, Docker, Hugging Face Spaces; Dockerfile unverified). Release ZIP: `python scripts/make_release.py`.

## 21. Privacy
[docs/PRIVACY.md](docs/PRIVACY.md): nothing is stored by default; feedback never contains the message; contributions are a separate redacted opt-in with deletion codes; retention and audit documented. Security review: [docs/SECURITY.md](docs/SECURITY.md).

## 22. Limitations
Synthetic training data → preliminary metrics only; Hindi/Hinglish least tested; language detection is heuristic; Devanagari text is assumed Hindi; rules can miss new wording; URL checks are structural; OCR needs user review; transformers/voice engines not exercised here;
regional languages (Bengali, Marathi, Tamil, Telugu, Gujarati) and **Garhwali are planned, not supported** — no data or evaluation exist and none is fabricated.

## 23. Future development
Real consented Hindi/Hinglish dataset and `evaluated` language status · trained language identifier · fine-tuned MuRIL/IndicBERT · PaddleOCR option · network database backend · regional languages with native-speaker review · mobile client via the `analyze_sms` boundary.

## 24. Troubleshooting
| Symptom | Fix |
|---|---|
| "Model file not found" / checksum mismatch | `python -m src.models.train_model` (artifacts depend on library versions) |
| OCR says unavailable | install Tesseract and make sure `tesseract --version` works in the same shell |
| Hindi screenshot text is garbage | install the `hin` pack (`tesseract --list-langs`) |
| No Hindi read-aloud | install a Hindi voice in the OS/browser; the app will not use an English voice for Hindi |
| Feedback forms missing | storage disabled/unwritable: check `GRAMSURAKSHA_STORAGE` and the DB folder permissions |
| Staff login says "not set up" | set `GRAMSURAKSHA_ADMIN_PASSWORD_HASH` (see §17) |
| `ModuleNotFoundError: src` | run commands from the project root |
