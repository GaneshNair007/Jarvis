# JARVIS Google OAuth 2.0 Setup — Owner Instructions

**Applies to:** the Gmail integration in the current JARVIS repository
branch `feat/nus-inspired-personal-workspace`.

## Security prerequisites

Before connecting an account, make sure its Google password is unique, enable
2-Step Verification, and review active Google sessions. Never put a Google
password, app password, browser cookie, or copied Chrome session into JARVIS,
Antigravity, GitHub, or `.env`. JARVIS uses OAuth 2.0 authorization code flow
with PKCE; it does not use password login or Gmail IMAP.

## What JARVIS connects as

- Assistant identity: `jarvis33246146@gmail.com` (dedicated assistant account,
  configured in `jarvis/config.py` and `.env.example` as `ASSISTANT_EMAIL`).
- Owner destination: `OWNER_EMAIL` in `.env` — this is a destination for
  owner-directed messages, not the mailbox JARVIS reads.
- To connect a different mailbox, set `ASSISTANT_EMAIL` to that exact address
  in `.env`, restart JARVIS, and authorize that same Google account. The
  OAuth flow intentionally rejects a different signed-in account.
- Least-privilege scopes: `gmail.readonly`, `gmail.compose`, `gmail.send`.
- Tokens are encrypted at rest with Windows DPAPI under
  `data/credentials/google_oauth.bin` (never plaintext, never logged).

## Step 1 — Create the OAuth client (Google Cloud Console)

1. Go to https://console.cloud.google.com/
2. Create a new project (or select an existing one you own).
3. **Enable the Gmail API:** APIs & Services → Library → "Gmail API" → Enable.
4. **Credentials → Create credentials → OAuth client ID:**
   - Application type: **Desktop app**
   - Name: `JARVIS Assistant`
5. Copy the **Client ID** and **Client Secret**.

## Step 2 — Configure JARVIS

Add to your local `.env` (gitignored, never commit):

```ini
GOOGLE_CLIENT_ID=<your-client-id>.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=<your-client-secret>
# Must match the Google account you will select during the OAuth consent flow.
ASSISTANT_EMAIL=jarvis33246146@gmail.com
# Optional owner destination; does not grant inbox access.
OWNER_EMAIL=<your-personal-email@example.com>
OWNER_DISPLAY_NAME=<Your Name>
```

## Step 3 — Run the connection wizard

```powershell
cd D:\jarvis
python -m integrations.google.oauth_flow status
# → UNCONFIGURED until credentials exist

python -m integrations.google.oauth_flow connect
```

Run these commands from the JARVIS repository root, in the same Windows
account that will run the API. The project `.env` is read directly for the
OAuth client ID and secret. On Windows, install dependencies with
`python -m pip install -r requirements.txt`; this includes the `pywin32`
dependency used for DPAPI-encrypted token persistence.

The wizard:

1. Starts a loopback listener on `127.0.0.1` only (ephemeral port).
2. Prints and opens the Google authorization URL.
3. You sign in **as `jarvis33246146@gmail.com`** and grant
   `gmail.readonly`, `gmail.compose`, `gmail.send`.
4. Google redirects to the loopback callback; JARVIS exchanges the code
   (PKCE-bound), verifies the account matches the assistant identity, and
   stores the refresh token encrypted with Windows DPAPI.

**Wrong account protection:** if you sign in as an account other than the
configured `ASSISTANT_EMAIL`, the token is revoked immediately and the
connection is refused. A Gmail address in `OWNER_EMAIL` does not change this.

## Step 4 — Verify

```powershell
python -m integrations.google.oauth_flow status
Invoke-RestMethod http://127.0.0.1:8000/api/v1/google/status
```

Should report `status: CONNECTED`, `account_email: jarvis33246146@gmail.com`,
`has_refresh_token: true`, and the three Gmail scopes.

In the JARVIS dashboard (Communication Center tab), Google Status should show
`CONNECTED` and the inbox/unread/drafts/sent lists should populate from the
real Gmail account.

## Disconnecting

```powershell
python -m integrations.google.oauth_flow disconnect
```

Revokes the refresh token at Google and deletes the DPAPI-stored credentials
locally.

## Live Gmail tests

Live integration tests (`tests/test_google_oauth_gmail.py` against fakes; live
tests require owner authorization) run against the connected account only after
Step 3 is complete. The test suite never sends mail to real recipients without
a provider-confirmed message id.

## Files

- `integrations/base/oauth_manager.py` — PKCE/state/refresh/revoke/DPAPI lifecycle
- `integrations/base/credential_manager.py` — `DpapiFileStore`, redaction, setup guides
- `integrations/google/gmail_api.py` — Gmail REST client, deterministic MIME, content hashes
- `integrations/google/gmail_integration.py` — Gmail powers, approval previews, account check
- `integrations/google/oauth_flow.py` — loopback OAuth flow + CLI (`connect`/`status`/`disconnect`)
- `jarvis/api/routes_google.py` — `/api/v1/google/*` and `/api/v1/google/gmail/*`
- `jarvis/powers/email_powers.py` — `SENT` only with provider message id; no IMAP/password path
- `dashboard/index.html` — Communication Center tab
