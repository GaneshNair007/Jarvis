# JARVIS Google OAuth 2.0 Setup — Owner Instructions

**Applies to:** Gmail integration (`integrations/google/`) on branch
`feature/jarvis-google-voice-multiagent`.

## Security prerequisites (owner, do this first)

The shared Gmail password (`nairganesh134@gmail.com`) is treated as
**compromised**. Before connecting JARVIS to Google:

1. **Change the Gmail password** immediately at
   https://myaccount.google.com/
2. **Enable 2-Step Verification** on the Google account.
3. **Review active sessions** at
   https://myaccount.google.com/device-activity and sign out anything you
   do not recognize.
4. **Revoke unnecessary app passwords / third-party access** at
   https://myaccount.google.com/u/3/security?linkedapps=.
5. **Never** put the Google password, an app password, browser cookies, or a
   copied browser session into JARVIS, Antigravity, GitHub, `.env`, or the
   master prompt. JARVIS uses OAuth 2.0 authorization code flow + PKCE only.

## What JARVIS connects as

- Assistant identity: `jarvis33246146@gmail.com` (dedicated assistant account,
  configured in `jarvis/config.py` and `.env.example` as `ASSISTANT_EMAIL`).
- Owner destination: `OWNER_EMAIL` in `.env` — set this explicitly; it is
  never assumed from old docs.
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
ASSISTANT_EMAIL=jarvis33246146@gmail.com
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

The wizard:

1. Starts a loopback listener on `127.0.0.1` only (ephemeral port).
2. Prints and opens the Google authorization URL.
3. You sign in **as `jarvis33246146@gmail.com`** and grant
   `gmail.readonly`, `gmail.compose`, `gmail.send`.
4. Google redirects to the loopback callback; JARVIS exchanges the code
   (PKCE-bound), verifies the account matches the assistant identity, and
   stores the refresh token encrypted with Windows DPAPI.

**Wrong account protection:** if you sign in as any other Google account, the
token is revoked immediately and the connection is refused.

## Step 4 — Verify

```powershell
python -m integrations.google.oauth_flow status
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
