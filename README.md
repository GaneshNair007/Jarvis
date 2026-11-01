# JARVIS — Personal AI Operating System

[![CI Pipeline](https://github.com/GaneshNair007/Jarvis/actions/workflows/ci.yml/badge.svg)](https://github.com/GaneshNair007/Jarvis/actions/workflows/ci.yml)
[![Docker & Deployment Readiness](https://github.com/GaneshNair007/Jarvis/actions/workflows/docker.yml/badge.svg)](https://github.com/GaneshNair007/Jarvis/actions/workflows/docker.yml)
[![Security & DLP Audit](https://github.com/GaneshNair007/Jarvis/actions/workflows/security.yml/badge.svg)](https://github.com/GaneshNair007/Jarvis/actions/workflows/security.yml)
[![Performance & Latency](https://github.com/GaneshNair007/Jarvis/actions/workflows/performance.yml/badge.svg)](https://github.com/GaneshNair007/Jarvis/actions/workflows/performance.yml)
[![Repository Activity](https://github.com/GaneshNair007/Jarvis/actions/workflows/activity.yml/badge.svg)](https://github.com/GaneshNair007/Jarvis/actions/workflows/activity.yml)
![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-3776AB?logo=python&logoColor=white)
![Tests](https://img.shields.io/badge/tests-195%20passed-brightgreen?logo=pytest&logoColor=white)
![Powers](https://img.shields.io/badge/powers-355%20operational-e50914)
![Architecture](https://img.shields.io/badge/architecture-LangGraph%20%7C%20LiteLLM%20%7C%20Mem0-blueviolet)
![Local Search](https://img.shields.io/badge/search-sub--5ms%20RRF-00C7B7)
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

# Run OpenRouter Reasoning & Free Tier Suite (5 tests)
pytest tests/test_openrouter.py -v

# Run Full Repository Suite (186 tests across 31 test files)
pytest -v
```

All **186 tests** pass with 100% deterministic reliability across 31 test files (expanded from the original 105 base tests):
- **105 base tests** (commit `8fd41eb`): Core API, browser worker, desktop worker, voice, search, career-ops, and Milestone 1 basics across 17 suites.
- **140 tracked tests** (commit `117e84a`): Addition of multi-agent swarm (`test_multiagent.py`), career-ops (`test_career_ops.py`), and skills & plugins (`test_skills_and_plugins.py`).
- **177 tests**: Milestone M1 durable memory core (`test_brain_memory_core.py`), coverage hardening (`test_coverage_core.py`), dynamic power binder (`test_power_binder.py`), memory-aware controller, and daily power extensions (Calendar, Email, Home Assistant).
- **186 tests (current)**: Architectural adoption tests for `@action` decorator (`test_action_decorator.py`), reciprocal rank fusion reranker (`test_hybrid_reranker.py`), assistants API endpoints (`test_routes_assistants.py`), and step telemetry (`test_step_telemetry.py`).

### 🌐 OpenRouter Zero-Cost & Reasoning Models Integration
JARVIS includes native, zero-cost LLM routing to OpenRouter's free router (`openrouter/free`) and 19+ free tier models (Gemma 4, Nemotron 3.5, LFM 2.5, Laguna, Cohere):
- **Deep Reasoning Traces**: Captures step-by-step reasoning tokens (`completionTokensDetails.reasoningTokens`) for complex logic and math tasks.
- **Automatic Fallback Chain**: If an upstream free model is throttled or rate-limited (HTTP 429), automatically fails over across alternate zero-cost models.
- **Zero Cost Guarantee**: Verified by CostGovernor with $0.00 usage estimation and budget gate compliance.

### 🔄 CI/CD Automation & Resilient Retries
All pull requests and commits to `main` trigger automated GitHub Actions workflows:
- **CI Pipeline (`ci.yml`)**: Multi-Python matrix (`3.11`, `3.12`), bytecode compilation verification, flake8 quality checks, and full pytest suite execution with automatic retry on transient failure (`nick-fields/retry@v3`).
- **Docker Readiness (`docker.yml`)**: Validates `docker-compose.yml`, builds `jarvis-api` and `jarvis-dashboard` container images, and inspects image health with automatic retries.
- **Security & DLP Audit (`security.yml`)**: Scans for credential leaks, verifies permission tier schemas, and enforces zero-trust DLP safety policies.

