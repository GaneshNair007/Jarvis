# JARVIS Core — Local Setup & Deployment Guide

This guide details how to launch and operate the local-first JARVIS core using Docker Compose or standalone local Python environments.

---

## 1. Architecture Overview

```
User (Chat / Voice / Dashboard / curl)
            │
            ▼
     FastAPI (:8000)
            │
            ▼
LangGraph Cognitive StateGraph
  1. memory_retrieval (Mem0 / SQLite Vault)
  2. policy_check (Tier 0 to Tier 3 Gate)
  3. model_router (LiteLLM Gateway -> Ollama/Claude/GPT)
  4. memory_update (Mem0 Provenance Writeback)
            │
     PostgreSQL (:5432) + Redis (:6379)
```

---

## 2. Quickstart with Docker Compose

### Step 1: Copy Environment Configuration
```bash
cp .env.example .env
```

Ensure secrets and keys are populated if cloud models are desired. For 100% offline local operation, default parameters will automatically use Ollama and the local SQLite memory vault.

### Step 2: Build and Launch Services
```bash
docker compose up -d --build
```

### Step 3: Verify Running Services
```bash
docker compose ps
```

Expected healthy services:
- `jarvis-postgres` (PostgreSQL 16) — port `5432`
- `jarvis-redis` (Redis 7) — port `6379`
- `jarvis-ollama` (Ollama local inference) — port `11434`
- `jarvis-litellm` (LiteLLM model gateway) — port `4000`
- `jarvis-api` (JARVIS Core FastAPI) — port `8000`
- `jarvis-dashboard` (Glassmorphic Iron Man HUD) — port `3000`

### Step 4: Stream Container Logs
```bash
docker compose logs -f jarvis-api
```

---

## 3. Service Endpoints

| Service | URL | Purpose |
| :--- | :--- | :--- |
| **Jarvis API** | `http://localhost:8000` | REST API, LangGraph, WebSockets |
| **Dashboard** | `http://localhost:3000` | Glassmorphic Iron Man HUD UI |
| **LiteLLM Gateway** | `http://localhost:4000` | Unified OpenAI-compatible router |
| **Ollama Local** | `http://localhost:11434` | Offline local LLM engine |
| **PostgreSQL** | `localhost:5432` | Relational state & checkpointer |
| **Redis** | `localhost:6379` | Real-time queue & event streaming |

---

## 4. Verification & Testing

### 1. Health Telemetry Check
```bash
curl http://localhost:8000/health
```
Response:
```json
{
  "status": "healthy",
  "service": "jarvis-core",
  "version": "1.0.0",
  "timestamp": 1793223000.0
}
```

### 2. Store Preference via Mem0
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":"ganesh","message":"Remember that my preferred stack is Python FastAPI."}'
```

### 3. Recall Preference in New Turn
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":"ganesh","message":"What is my preferred stack?"}'
```
JARVIS will recall through Mem0 and respond:
`"Your preferred stack is Python FastAPI."`

### 4. Emergency Kill Switch
```bash
# Trip kill switch
curl -X POST http://localhost:8000/kill-switch \
  -H "Content-Type: application/json" \
  -d '{"active": true, "reason": "Operator command"}'

# Reset kill switch
curl -X POST http://localhost:8000/kill-switch \
  -H "Content-Type: application/json" \
  -d '{"active": false, "reason": "Operator resumed"}'
```

---

## 5. Connect your signed-in Ollama installation

JARVIS talks to Ollama through its local HTTP API. The Ollama desktop/CLI
installation owns the sign-in session; **do not copy your Ollama password,
private key, or browser session into JARVIS**.

### Native Windows / local Python run

1. Open Ollama and sign in. For CLI sign-in, run `ollama signin` in the
   Windows account that runs the Ollama service.
2. Confirm the server and model are available:

```powershell
ollama list
ollama run llama3.1 "Reply with exactly JARVIS_OLLAMA_OK."
```

Replace `llama3.1` with the exact model tag shown by `ollama list`.
For an Ollama cloud model, use its cloud tag (for example, a tag ending in
`:cloud`) and first verify it with `ollama run <model-tag>`. The local
Ollama service forwards signed-in cloud requests; JARVIS does not need an
Ollama API key for this local-server path.

3. In the repository `.env`, set the same endpoint and exact model tag:

```dotenv
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_DEFAULT_MODEL=llama3.1
```

4. Run the actual request smoke test:

```powershell
python scripts/verify_ollama_connection.py
```

The script checks `/api/tags` and then sends a real, short
`/api/generate` request. It exits non-zero if the endpoint, model, sign-in,
or inference fails. It does not treat an open TCP port as proof of a working
model.

5. With JARVIS running, inspect `http://localhost:8000/model/status`.
Tier 1 should show `status: "ready"`, `model_available: true`, and the
configured model in `available_models`. `model_missing`, `unverified`,
or `unavailable` are not success states.

### Docker Compose

The Compose setup now points JARVIS and the LiteLLM gateway at the host
Ollama server by default using
`http://host.docker.internal:11434`, so it can use the Ollama installation
where you signed in. If your Docker host cannot reach the desktop service,
run JARVIS natively or configure Ollama's host binding/firewall deliberately;
do not expose the Ollama port to an untrusted network.

The separate Ollama container is opt-in because it has its own model store
and does **not** automatically share the desktop account's sign-in session.
To use that isolated container instead, set
`OLLAMA_BASE_URL_DOCKER=http://ollama:11434` in `.env` and start it with:

```powershell
docker compose --profile bundled-ollama up -d --build
```

---

## 6. Running Tests Locally

```bash
pytest tests/test_milestone1_core.py -v
```
Validates all 12 core requirements:
1. Health endpoint
2. Chat endpoint
3. Memory retrieval
4. Memory update
5. Policy denial
6. Model routing
7. Local model fallback
8. Task creation
9. Task cancellation
10. Power registry
11. Audit logging
12. Kill switch


## 7. Windows standalone browser and Gmail setup

Run these steps from the repository root in PowerShell after activating the
virtual environment.

### Browser search and page reading

Install the Python dependencies and the Playwright Chromium browser:

```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
```

Start the API, then test public-web search:

```powershell
$body = @{ query = "latest Python documentation"; max_results = 5 } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/browser/search -ContentType "application/json" -Body $body
```

Test reading a public page:

```powershell
$body = @{ url = "https://www.python.org/" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/browser/read -ContentType "application/json" -Body $body
```

JARVIS uses an isolated, temporary Playwright browser context for web research.
It does not automatically inherit your normal Chrome profile, logged-in website
sessions, or Gmail cookies. Use the official Gmail integration below for email.

### Gmail authorization

1. Create a Google Cloud OAuth client of type **Desktop app**, enable the Gmail
   API, and put `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in the local
   `.env` file.
2. Ensure `ASSISTANT_EMAIL` is the exact mailbox you want JARVIS to access.
   `OWNER_EMAIL` is a separate destination setting and does not grant inbox
   access.
3. Run the connection wizard:

```powershell
python -m integrations.google.oauth_flow status
python -m integrations.google.oauth_flow connect
python -m integrations.google.oauth_flow status
```

4. Sign in to Google as the configured `ASSISTANT_EMAIL` and grant the
   requested Gmail scopes. Keep the wizard running until it reports
   `CONNECTED`.
5. With the API running, verify the same connection:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/google/status
Invoke-RestMethod http://127.0.0.1:8000/api/v1/google/gmail/profile
Invoke-RestMethod http://127.0.0.1:8000/api/v1/google/gmail/inbox
```

A `CONNECTED` OAuth result and a successful Gmail profile/inbox response are
the evidence that inbox access is live. A configured email address, a local
`.eml` file, or a successful browser search is not proof of Gmail access.
