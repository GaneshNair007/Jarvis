# Fourth-Law Reflection — Google OAuth 2.0 + Gmail Integration

**Date:** 2026-11-09
**Branch:** `feature/jarvis-google-voice-multiagent`  \n**Constitution:** v1.2.0, Fourth Law — NO MEMORY WITHOUT REFLECTION

## What was claimed before

Previous work described email sending as a working capability:

- `email_powers.send_email` returned `"status": "SENT"` after moving a local
  `.eml` file into `sent/` — with **no provider delivery at all**.
- `scan_inbox_for_opportunities` attempted live Gmail via IMAP with an app
  password and defaulted to the owner's personal account
  `nairganesh134@gmail.com`, silently falling back to a local inbox store.
- `communication_powers.send_email` (PWR-206) reported `"status": "dispatched"`
  after a local file rename, with the note "SMTP delivery not configured."
- The shared Gmail password was treated as if it could safely be used by JARVIS
  (it is compromised; owner remediation is outstanding).

None of these claims had provider evidence. "SENT" was fabricated.

## What changed

**OAuth foundation** (`integrations/base/oauth_manager.py`, `credential_manager.py`):

- PKCE S256, cryptographically random `state`, TTL expiry, one-time state
  consumption.
- Refresh-token lifecycle; explicit revoke/disconnect.
- Encrypted persistence via Windows DPAPI (`DpapiFileStore` at
  `data/credentials/<provider>_oauth.bin`); ciphertext never logged.
- Redacted status: never returns access/refresh tokens or client secrets.

**Gmail integration** (`integrations/google/gmail_api.py`, `gmail_integration.py`,
`oauth_flow.py`):

- Official Gmail REST API only, stdlib `urllib` (no `google-api-python-client`).
- OAuth 2.0 only: no IMAP, no app passwords, no cookies, no browser sessions.
- Least-privilege scopes: `gmail.readonly`, `gmail.compose`, `gmail.send`.
- Loopback flow bound to `127.0.0.1`; dedicated assistant account
  (`jarvis33246146@gmail.com`) enforced — any other account is revoked and
  refused.
- Deterministic MIME with fixed boundary `=_JARVIS_APPROVAL_BOUNDARY_7f3c9a1e`;
  approval bound to SHA-256 of the exact RFC 822 bytes; content changes
  invalidate approval (409 `content_hash_mismatch`).
- `"SENT"` is returned **only** when Gmail confirms a real `message_id`;
  otherwise `"NOT_SENT"` and the draft is **not** archived.

**API layer** (`jarvis/api/routes_google.py`):

- `GET /api/v1/google/status` (redacted; UNCONFIGURED/DISCONNECTED/CONNECTED)
- `POST /api/v1/google/auth/start`, `GET /api/v1/google/auth/callback`,
  `POST /api/v1/google/auth/disconnect`
- `GET /api/v1/google/gmail/{profile,inbox,unread,important,sent,drafts,message,draft}`
- `POST /api/v1/google/gmail/drafts`, `POST /api/v1/google/gmail/send`
- `GET /api/v1/approvals/pending` (human approval queue)

**Dashboard** (`dashboard/index.html`): Communication Center tab — inbox,
unread/important/sent/drafts lists, message detail modal, approval queue with
approve/reject, connect/disconnect Google flows.

**Email powers audit** (`jarvis/powers/email_powers.py`,
`communication_powers.py`):

- Removed `imaplib`, `GMAIL_APP_PASSWORD`, `nairganesh134@gmail.com`.
- `scan_inbox_for_opportunities` uses Gmail OAuth API; local store is an
  explicitly labelled fallback; all email content marked
  `UNTRUSTED_EXTERNAL_DATA`.
- `send_email` (PWR-052) delegates to `gmail_client.send_raw_message`; returns
  `SENT` only with a provider message id.
- PWR-206 legacy send no longer claims delivery.

## Evidence ledger

| Claim | Evidence | Result |
| :--- | :--- | :--- |
| PKCE S256 binding | unit test recomputes challenge from verifier | 31/31 OAuth+email tests pass |
| State expiry + one-time use | unit test with mocked clock | PASS |
| Refresh preserves token | unit test; refresh token reused | PASS |
| Revoke deletes local token | unit test; store empty after revoke | PASS |
| DPAPI at rest | plaintext absent from `.bin` file | PASS (Windows) |
| Wrong account refused | integration revokes + health DEGRADED | PASS |
| Approval binds to content | changed body → `APPROVAL_INVALID` | PASS |
| No token → AWAITING_APPROVAL | integration execute_power returns pending | PASS |
| No message id → NOT_SENT | fake provider returns no id | PASS |
| SENT requires provider id | fake provider returns id → `SENT`, archived | PASS |
| Routes wired | TestClient + live uvicorn on port 8000 | 200 / UNCONFIGURED / 409 correct |
| Full regression | `pytest tests -q` | **739 passed** |

## What remains unproven / owner actions

1. **Live owner OAuth:** no Google Cloud project, OAuth Desktop client, or
   account consent exists yet. `python -m integrations.google.oauth_flow status`
   reports `UNCONFIGURED`. Owner must create the client, set
   `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET`, run `connect`, and verify
   `jarvis33246146@gmail.com`. See `docs/GOOGLE_OAUTH_SETUP.md`.
2. **Live Gmail tests:** require the owner's authorized account; not run.
3. **Full Windows sign-out/sign-in boot:** still UNVERIFIED (Sprint 1 evidence
   was direct `cscript` execution only). See `docs/WINDOWS_BOOT_CHECKLIST.md`.
4. **Owner security remediation:** change the compromised Gmail password,
   enable 2-Step Verification, review/revoke sessions and app passwords —
   owner action, never encoded in JARVIS.

## Lesson

"Sent" without a provider message id is not mail; it is a file rename. This
phase replaced the false-success outbox with approval-bound, provider-confirmed
delivery, and replaced password assumptions with OAuth 2.0 + DPAPI. Every
remaining claim about live Gmail waits on owner evidence — no configuration
name or HTTP 200 from a stub counts as implementation.
