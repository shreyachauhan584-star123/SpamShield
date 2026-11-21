# Deployment

**Status: none of these targets was exercised in the development sandbox (no network/Docker/Streamlit).** Treat as instructions to verify.

## Persistence - read this first
Feedback/contributions use SQLite at `GRAMSURAKSHA_DB_PATH`. Many hosts give an **ephemeral** disk (Streamlit Community Cloud, most free tiers): the file disappears on restart.
* Persistent volume (Docker/VM/Fly/Railway/Render disk/HF persistent storage): set `GRAMSURAKSHA_DB_PATH` to a path on the volume and `GRAMSURAKSHA_DB_PERSISTENT=1`.
* Ephemeral host: set `GRAMSURAKSHA_STORAGE=none` - the analysis app works fully and the feedback/contribution forms are hidden. (A network database backend can be added behind `src/database/db.py`; not implemented.)
* Backups: `python scripts/backup_db.py --dest backups --keep 14` (SQLite online backup API) on a schedule; copy backups off the host.

## Streamlit Community Cloud
Repo root contains `requirements.txt` and `packages.txt` (installs `tesseract-ocr`, English and Hindi packs). Main file `app.py`. Secrets (App settings -> Secrets): `GRAMSURAKSHA_ADMIN_PASSWORD_HASH`, optional threat-intel keys. Use `GRAMSURAKSHA_STORAGE=none` (ephemeral disk).

## Docker (VM / any container host)
```
docker build -t gramsuraksha .
docker run -p 8501:8501 -v gramsuraksha-data:/data -e GRAMSURAKSHA_ADMIN_PASSWORD_HASH='...' gramsuraksha
```
## Hugging Face Spaces (Docker SDK)
Use the Dockerfile; enable persistent storage and point `GRAMSURAKSHA_DB_PATH` at `/data`.

## Production checklist
TLS via reverse proxy · staff pages behind host auth · `pip-audit` · generated admin hash (never default) · model folder read-only · backups scheduled · retention job (`purge_expired`) scheduled · `docs/MODEL_CARD.md` regenerated after retraining · Hindi text reviewed by native speakers.

## Release package
`python scripts/make_release.py` -> `dist/GramSurakshaAI-v2.zip` (excludes `.git`, virtualenvs, caches, databases/backups, `.env`, generated splits, experiment logs, checkpoints; includes the active model in `models/baseline/` and version history in `models/registry/`).
