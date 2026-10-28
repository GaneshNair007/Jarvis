# JARVIS — Personal AI Operating System

[![CI Pipeline](https://github.com/GaneshNair007/Jarvis/actions/workflows/ci.yml/badge.svg)](https://github.com/GaneshNair007/Jarvis/actions/workflows/ci.yml)
[![Docker & Deployment Readiness](https://github.com/GaneshNair007/Jarvis/actions/workflows/docker.yml/badge.svg)](https://github.com/GaneshNair007/Jarvis/actions/workflows/docker.yml)
[![Security & DLP Audit](https://github.com/GaneshNair007/Jarvis/actions/workflows/security.yml/badge.svg)](https://github.com/GaneshNair007/Jarvis/actions/workflows/security.yml)
![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-3776AB?logo=python&logoColor=white)
![Tests](https://img.shields.io/badge/tests-100%20passed-brightgreen?logo=pytest&logoColor=white)
![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)
![Architecture](https://img.shields.io/badge/architecture-LangGraph%20%7C%20LiteLLM%20%7C%20Mem0-blueviolet)
![Local Search](https://img.shields.io/badge/search-sub--50ms%20local-00C7B7)
![License](https://img.shields.io/badge/license-MIT-green)

> **A private, local-first personal AI operating system for technical IT professionals, developers, researchers, and creators.**  
> *Engineered with LangGraph cognitive StateGraph, LiteLLM hybrid model gateway, Mem0 long-term memory, PostgreSQL persistence, Redis real-time streaming, Ollama private local models, and Docker Compose orchestration.*

---

## ⚡ Core Architecture

```
User (Voice / Chat / Glassmorphic HUD / curl)
                      │
                      ▼
               FastAPI Server (:8000)
                      │
                      ▼
        LangGraph Cognitive StateGraph
  ┌───────────────────────────────────────────────┐
  │ 1. memory_retrieval (Mem0 / SQLite Vault)     │
  │    Queries long-term user memory              │
  └───────────────────────┬───────────────────────┘
                          ▼
  ┌───────────────────────────────────────────────┐
  │ 2. policy_check (Tier 0 to Tier 3)            │
  │    Evaluates permissions & DLP rules          │
  └───────────────────────┬───────────────────────┘
                          ▼
  ┌───────────────────────────────────────────────┐
  │ 3. model_router (LiteLLM Gateway :4000)       │
  │    Routes: Ollama local / Claude / GPT / Gemini│
  └───────────────────────┬───────────────────────┘
                          ▼
  ┌───────────────────────────────────────────────┐
  │ 4. memory_update (Mem0 Provenance Writeback)  │
  │    Saves turn & user preferences to memory   │
  └───────────────────────────────────────────────┘
```

---

## 📦 Docker Compose Stack

The complete stack is configured in `docker-compose.yml`:
1. **`postgres:16-alpine`**: Relational checkpointing & state store (port `5432`).
2. **`redis:7-alpine`**: Task queue & event streaming (port `6379`).
3. **`ollama/ollama:latest`**: Local offline LLM & embeddings (port `11434`).
4. **`ghcr.io/berriai/litellm:main-stable`**: Unified OpenAI-compatible gateway with fallbacks (port `4000`).
5. **`jarvis-api`**: FastAPI core daemon with LangGraph & Mem0 (port `8000`).
6. **`jarvis-dashboard`**: Iron Man glassmorphic HUD dashboard (port `3000`).

---

## 🚀 Quickstart

### 1. Launch with Docker Compose
```bash
cp .env.example .env
docker compose up -d --build
docker compose ps
docker compose logs -f jarvis-api
```

### 2. Verify Health
```bash
curl http://localhost:8000/health
```

### 3. Test Mem0 Memory & Recall
```bash
# 1. Store preference
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":"ganesh","message":"Remember that my preferred stack is Python FastAPI."}'

# 2. Recall preference
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":"ganesh","message":"What is my preferred stack?"}'
```
JARVIS will recall the preference via Mem0 and respond:
`"Your preferred stack is Python FastAPI."`

---

## 🛡️ Safety & Policy Engine

Enforces four approval tiers:
- **Tier 0 (Observe)**: Autonomously allowed read-only actions (web search, memory search, system telemetry).
- **Tier 1 (Reversible Action)**: Local drafts, scratch files, local document ingest.
- **Tier 2 (Explicit Approval)**: File deletion, emails, deployments, computer mouse/keyboard action.
- **Tier 3 (Step-Up Authentication)**: Formatting disks, wiping systems, financial/crypto transactions.

Emergency kill switch:
```bash
curl -X POST http://localhost:8000/kill-switch -H "Content-Type: application/json" -d '{"active": true}'
```

---

## 🧪 Automated Test Suite & CI/CD

```bash
# Run Milestone 1 Core Acceptance Suite (12 tests)
pytest tests/test_milestone1_core.py -v

# Run Full Repository Suite (100 tests across 16 suites)
pytest -v
```

All **100 tests** pass with 100% deterministic reliability.

### 🔄 CI/CD Automation & Resilient Retries
All pull requests and commits to `main` trigger automated GitHub Actions workflows:
- **CI Pipeline (`ci.yml`)**: Multi-Python matrix (`3.11`, `3.12`), bytecode compilation verification, flake8 quality checks, and full pytest suite execution with automatic retry on transient failure (`nick-fields/retry@v3`).
- **Docker Readiness (`docker.yml`)**: Validates `docker-compose.yml`, builds `jarvis-api` and `jarvis-dashboard` container images, and inspects image health with automatic retries.
- **Security & DLP Audit (`security.yml`)**: Scans for credential leaks, verifies permission tier schemas, and enforces zero-trust DLP safety policies.

