# JARVIS Repository Discovery & Architectural Analysis

> **Analysis Date**: 29 October 2026  
> **Repository Target**: `https://github.com/GaneshNair007/Jarvis.git`  
> **Local Workspace**: `C:\Users\Ganesh Nair\.gemini\antigravity-ide\scratch\jarvis`  
> **Branch**: `main` (Clean, commit `21f12bb`)

---

## 1. Executive Summary & Tech Stack

The repository is **not** an empty scratchpad or documentation-only placeholder. It is an actively functioning, local-first Personal AI Operating System engineered in Python 3.12 with FastAPI, LangGraph, Mem0, LiteLLM, Playwright, SQLite FTS5, Meilisearch, Qdrant, and Docker Compose.

### Active Technology Stack
- **Core API & Daemon**: Python 3.12, FastAPI, Pydantic v2, Uvicorn, AnyIO.
- **Cognitive Orchestration**: LangGraph `StateGraph`, Checkpoint persistence (PostgreSQL/SQLite), interruptible approval transitions.
- **Model Routing**: LiteLLM Gateway (`:4000`) routing across:
  - Local Reflexes: Ollama (`llama3.1:8b`, `qwen2.5:7b`, `nomic-embed-text`)
  - Mid-Tier Private Reasoning: Local vLLM / Mistral
  - Frontier Cloud Escalation: Claude 3.5 Sonnet, GPT-4o, Gemini 1.5 Pro (behind DLP & Policy Gate).
- **Memory & Knowledge**: 
  - Mem0 episodic/semantic user preferences.
  - SQLite `documents` archive with SHA-256 deduplication and soft deletion.
  - SQLite FTS5 (`porter unicode61`) BM25 full-text keyword search.
  - Meilisearch instant search-as-you-type (`:7700`).
  - Qdrant semantic vector storage (`:6333`).
  - Redis hot cache (`:6379`) with sub-5ms latency.
- **Automation Surfaces**:
  - Browser Worker: Playwright with isolated ephemeral contexts, SSRF protection, DOM role/label selectors, and screenshot evidence hashing.
  - Desktop Worker: See-Act-Verify cycle, OS window focusing, PyAutoGUI fallback, physical emergency hotkey, corner failsafe, and app allowlisting.
- **Voice & Mobile**:
  - Wake-word detection, push-to-talk, barge-in, SAPI WAV synthesis.
  - Mobile/iPhone companion pairing and push notification alerts.
- **Safety & Policy**:
  - 4-Tier Policy Engine (Tier 0: Observe, Tier 1: Reversible, Tier 2: Explicit Approval, Tier 3: Step-Up Auth).
  - HMAC-SHA256 frozen-hash approval tokens with strict expiration.
  - Cryptographic append-only audit ledger (`audit.log` & SQLite `audit_events`).
  - Emergency software & physical kill switches.
- **User Interface**:
  - High-performance glassmorphic Iron Man HUD (`dashboard/index.html` and `jarvis/dashboard/index.html`) featuring search-as-you-type, voice interaction, task status stream, memory inspection, and kill switch.

---

## 2. Directory Structure & Codebase Map

```text
C:\Users\Ganesh Nair\.gemini\antigravity-ide\scratch\jarvis\
├── alembic/                      # Database migrations
├── app/                          # Core application lifecycle
├── config/                       # Environment configuration
├── core/                         # Core execution primitives
├── dashboard/                    # Glassmorphic HUD frontend (HTML/CSS/JS)
│   └── index.html
├── data/                         # Local SQLite databases & vector storage
├── docs/                         # Architecture & workflow documentation
├── graph/                        # LangGraph cognitive StateGraph
├── integrations/                 # Phase 1 integration gateway & MCP plugins
│   ├── base.py                   # BaseIntegration contract
│   ├── registry.py               # Dynamic integration registry
│   ├── credential_manager.py     # AES-encrypted credential vault
│   ├── rate_limiter.py           # Token bucket rate limiting
│   ├── retry_policy.py           # Exponential backoff jitter retries
│   ├── github_integration.py     # GitHub MCP & REST integration
│   └── system_diagnostics.py     # Host OS diagnostics & hardware monitoring
├── jarvis/                       # Core python package
│   ├── api/                      # FastAPI REST routers
│   │   ├── routes_chat.py        # /chat endpoint
│   │   ├── routes_tasks.py       # /tasks lifecycle
│   │   ├── routes_search.py      # /search endpoints (16 routes)
│   │   ├── routes_integrations.py# /integrations endpoints (11 routes)
│   │   ├── routes_voice.py       # /voice endpoints
│   │   ├── routes_desktop.py     # /desktop endpoints
│   │   ├── routes_browser.py     # /browser endpoints
│   │   └── server.py             # Root FastAPI application
│   ├── browser/                  # Playwright browser automation
│   ├── computer/                 # Desktop See-Act-Verify worker
│   ├── core/                     # Policy gate, audit ledger, kill switch
│   ├── memory/                   # Mem0 & SQLite cognitive memory vault
│   ├── powers/                   # PowerRegistry & 355 catalog
│   └── voice/                    # SAPI/Whisper voice engine
├── search/                       # Zero-API Millisecond Local Search Brain
│   ├── local_search_engine.py    # SQLite FTS5 BM25 engine & documents archive
│   ├── search_cache.py           # Redis + Memory TTL hot cache (< 5ms)
│   ├── meili_search.py           # Meilisearch instant search client
│   ├── semantic_search.py        # Qdrant + Ollama vector semantic search
│   ├── hybrid_ranker.py          # Reciprocal Rank Fusion & citations
│   ├── searxng_client.py         # Self-hosted SearXNG fallback client
│   ├── search_orchestrator.py    # Multi-engine search orchestrator
│   └── ingestors/                # 10 Multi-format document ingestors
│       ├── base_ingestor.py      # Redaction, deduplication & chunking
│       ├── file_ingestor.py      # TXT, CSV, JSON, YAML
│       ├── pdf_ingestor.py       # PDF document parser
│       ├── markdown_ingestor.py  # Markdown heading section parser
│       ├── code_repo_ingestor.py # Code repository parser (.gitignore aware)
│       ├── browser_page_ingestor.py # Clean web/HTML parser
│       ├── email_ingestor.py     # Email header & body parser
│       ├── chat_history_ingestor.py # Chat transcript chunker
│       ├── notes_ingestor.py     # Obsidian / Notion notes parser
│       └── web_cache_ingestor.py # Web research cache ingestor
└── tests/                        # Automated Pytest suite
    ├── test_api.py
    ├── test_audit.py
    ├── test_browser.py
    ├── test_dashboard.py
    ├── test_desktop.py
    ├── test_integrations_foundation.py
    ├── test_local_search.py
    ├── test_memory_vault.py
    ├── test_milestone1_core.py
    ├── test_model_router.py
    ├── test_orchestrator.py
    ├── test_policy_gate.py
    ├── test_power_registry.py
    ├── test_privacy_gate.py
    ├── test_tasks_and_litellm.py
    └── test_voice.py
```

---

## 3. Subsystem Health & Existing Feature Audit

| Subsystem | File / Module | Implementation Status | Test Coverage |
| :--- | :--- | :--- | :--- |
| **Cognitive Orchestrator** | `jarvis/core/orchestrator.py` | Complete (LangGraph StateGraph) | `test_milestone1_core.py`, `test_orchestrator.py` |
| **Power Registry** | `jarvis/powers/registry.py` | Complete (355 Catalog + Dynamic Integration Powers) | `test_power_registry.py`, `test_milestone1_core.py` |
| **Policy Engine** | `jarvis/core/policy.py` | Complete (4 Tiers, Deny-by-default, HMAC-SHA256) | `test_policy_gate.py` |
| **Audit Ledger** | `jarvis/core/audit.py` | Complete (Cryptographic append-only chain) | `test_audit.py` |
| **Kill Switch** | `jarvis/core/kill_switch.py` | Complete (API, CLI, UI, and Task cancel) | `test_milestone1_core.py` |
| **Task Queue** | `jarvis/core/tasks.py` | Complete (State machine, steps, cancellation) | `test_tasks_and_litellm.py` |
| **Memory Vault** | `jarvis/memory/` | Complete (Mem0, SQLite vault, 7 layers) | `test_memory_vault.py` |
| **Model Router** | `jarvis/core/model_router.py`| Complete (LiteLLM, DLP, 3-tier routing) | `test_model_router.py` |
| **Browser Worker** | `jarvis/browser/` | Complete (Playwright, DOM locators, SSRF guard) | `test_browser.py` |
| **Desktop Worker** | `jarvis/computer/` | Complete (See-Act-Verify, failsafe, allowlist) | `test_desktop.py` |
| **Voice Pipeline** | `jarvis/voice/` | Complete (Wake word, push-to-talk, barge-in, SAPI)| `test_voice.py` |
| **Local Search Brain**| `search/` | Complete (FTS5, Meili, Qdrant, Redis, Ingestors) | `test_local_search.py` |
| **Integration Gateway**| `integrations/` | Complete (BaseIntegration, RateLimit, Retry) | `test_integrations_foundation.py` |
| **Glassmorphic HUD** | `dashboard/index.html` | Complete (Interactive UI, Search HUD, Voice) | `test_dashboard.py` |

---

## 4. Code Quality & Security Baseline

- **Zero Hard-Coded Secrets**: Configuration is managed exclusively via Pydantic Settings and `.env`.
- **Pre-Indexing Redaction**: All API keys, JWTs, AWS credentials, passwords, and payment card numbers are redacted before disk or index writes.
- **Fail-Closed Security**: Unclassified operations are blocked by default.
- **Audit Verification**: Every executed power, browser action, desktop step, and search query logs an immutable audit event with hashes.
