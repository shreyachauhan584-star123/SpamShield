# Privacy

| | |
|---|---|
| **Processed (in memory only)** | the SMS text you paste, speak or read from a screenshot. Screenshots and audio are validated and processed in memory and never written to disk. |
| **Stored by default** | nothing. No SMS history, no accounts, no analytics (Streamlit usage stats are off). |
| **Stored with feedback consent** | feedback type (6 kinds: correct fraud / false alarm / missed suspicious / correct legitimate / explanation helpful / not helpful), risk level, message category, language, model + rules version, optional comment (<= 500 chars, numbers/phones/e-mails redacted), review status. **Never the message.** |
| **Stored with the separate contribution consent** | the message with OTP-like numbers, phone numbers, Aadhaar-style numbers and e-mails removed; the exact stored text is shown before you agree. A one-time deletion code is shown; only its hash is stored. |
| **Never collected** | OTPs, PINs, bank/Aadhaar/phone numbers (redacted before any storage), screenshots, audio, identity. |

## Retention (`src/services/privacy_service.RETENTION_DAYS`, applied by *Staff -> Privacy -> Apply retention policy* or `purge_expired()`)
feedback 365 days · pending contributions 90 days · rejected/duplicate contributions 30 days · audit log 730 days. Accepted contributions remain until deleted by the contributor (code) or an administrator.
Feedback is anonymous by design, so an individual's feedback cannot be looked up for deletion - which is why it contains no message and no identifier.

## Deletion procedure
* Contributor: About page -> "Delete a message you shared" -> enter the code. Writes an audit entry (no content).
* Administrator: Staff -> Contributions -> Delete. Also audited.
* Whole database: delete the file at `GRAMSURAKSHA_DB_PATH` (and `backups/`).

## Review and training
Feedback and contributions are **never** used for training automatically. A human accepts a contribution and assigns a verified label; an administrator exports it (`data/validated/`) and must pass the file
explicitly to training (`--extra-csv ... --extra-provenance manually_verified`). Near-duplicates of accepted items are flagged. All admin actions are audit-logged.

## Third parties (only when you use them)
* *Browser read-aloud / dictation*: runs in your browser/device; Chrome-based dictation may send audio to the browser vendor's service (browser dependent).
* *gTTS fallback audio*: the explanation text is sent to Google.
* *Link reputation (opt-in checkbox, off by default)*: the link addresses (not the message) are sent to the configured provider.
* *Google Fonts*: loaded by your browser; remove the `@import` in `src/ui/styles.py` for offline/no-third-party use.
* *Hosting provider*: sees traffic as any host does.

## Logging
The application never logs message content; a redacting filter (`src/utils/logging_utils.py`) masks URLs, e-mails and numbers anyway; a test statically checks that user-facing modules contain no `print`/`logging` calls.
