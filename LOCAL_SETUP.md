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

## 5. Running Tests Locally

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
