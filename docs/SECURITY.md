# Security review (V2)

Scope audited: all of `src/`, `pages/`, `app.py`, scripts, configuration. Each row lists the control and the test that exercises it.

| Area | Finding / control | Test |
|---|---|---|
| Input validation | Empty / non-text / > 2000 chars rejected (not truncated); control chars stripped | `test_app_validation` |
| Output encoding | All user text HTML-escaped before `unsafe_allow_html`; browser-speech snippets JSON-escape text and neutralise `</script>` | `test_highlight_escapes_html`, `test_tts_html_cannot_be_broken_out_of...` |
| Image uploads | Real format checked (PNG/JPEG/WEBP), 5 MB, 25 MP, min size, decompression-bomb guard, EXIF dropped, processed in memory, no temp files left | `test_multimodal` |
| Audio uploads | WAV only (no untrusted decoders), 5 MB, 60 s, silence check | `test_multimodal` |
| CSV uploads | extension, size, rows, UTF-8, columns, labels, provenance | `test_preprocessing` |
| URLs / SSRF | No URL is ever opened, fetched, resolved or followed; shortened links stay unresolved; the only outbound call is the optional Safe Browsing endpoint (constant host, URLs only in the JSON body, 4 s timeout, off by default, opt-in per analysis) | `test_security_v2` (socket blocked during analysis; provider mocked) |
| Model files | joblib can execute code on load: loaded only from `models/`, only after SHA-256 verification; tamper -> refused | `test_tampered_or_missing_model_is_refused` |
| Database | parameterised SQL only; CHECK constraints; owner-only file mode (POSIX); versioned migrations; injection strings inert | `test_feedback_privacy` |
| Admin | disabled unless a PBKDF2-SHA256 hash is configured (no default password); constant-time compare; process-wide lockout (5 fails / 5 min); 30-minute session; staff pages guard themselves and are not in the menu for others; every action audited | `test_feedback_privacy`, `tests/stubs` smoke |
| Secrets | none in code (static test); `.env` git-ignored; `.env.example` has empty values | `test_no_secrets_are_hardcoded` |
| Logging | no message content logged; redacting filter | `test_analysis_path_never_prints_or_logs...` |
| Result integrity | schema validator; inconsistent result is downgraded to UNKNOWN and never displayed | `test_inconsistent_results_are_downgraded...` |

## Residual risks / not done
* Streamlit session state is per-process; the admin session is not hardened for multi-replica deployments. Put staff pages behind your host's authentication for production.
* The SHA-256 sidecar proves integrity, not authenticity (an attacker who can write the models folder can replace both). Protect the folder / sign artifacts in CI.
* `pip-audit` / dependency CVE scanning could not run offline: run `pip install pip-audit && pip-audit -r requirements.txt` before release.
* TLS and rate limiting are the host's job (reverse proxy). The login lockout is global, so an attacker can lock out staff temporarily.
* The unverified Dockerfile runs as non-root but has not been built in this environment.
