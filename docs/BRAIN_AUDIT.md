# Project JARVIS — Phase 0 Brain Audit Report

**Date**: 31 October 2026  
**Auditor**: Lead Cognitive Core Engineer  
**Repository**: `https://github.com/GaneshNair007/Jarvis` (MIT License)  
**Host Environment**: Windows 11, NVIDIA GeForce RTX 4050 Laptop GPU (6GB VRAM), 24GB System RAM  
**Active Server**: `http://127.0.0.1:8000` (FastAPI + Glassmorphic HUD Dashboard)

---

## 1. Executive Summary

This audit establishes the baseline for upgrading Project JARVIS from an operational prototype with a 4-node linear LangGraph pipeline into a full, reliable cognitive brain architecture as specified in `JARVIS_Master_Edition.pdf`.

The repository possesses a strong, clean foundation: an append-only cryptographic audit ledger, deterministic policy gates (Tiers 0–3), a LiteLLM/Ollama model router, a durable canonical memory core (SQLite/SQLAlchemy), and an extensive power catalog. 

---

## 2. Codebase Inventory: What Exists vs. What is Mocked

| Subsystem / Directory | Physical Files & Capabilities | Reality Status | Notes & Upstream References |
| :--- | :--- | :--- | :--- |
| **`core/` & `jarvis/core/`** | `orchestrator.py`, `model_router.py`, `policy_gate.py`, `power_binder.py`, `action_decorator.py`, `step_telemetry.py`, `audit.py`, `cost_governor.py` | **Real & Operational** | Deterministic HMAC-SHA256 policy tokens, kill switch, active tool budgeting (max 12 tools). |
| **`graph/` & `jarvis/graph/`** | `nodes.py`, `jarvis_graph.py` | **Partially Operational** | 4-node linear graph (`memory_retrieval -> policy_check -> model_router -> memory_update`). Missing planner, verifier, and reflection loop. |
| **`jarvis/brain/`** | `memory/service.py`, `memory/repository.py`, `memory/models.py`, `schemas.py` | **Real & Operational** | Milestone M1 Durable Memory Core: Canonical records, DLP credential refusal regex, cryptographic metadata audit, scoped retrieval. |
| **`search/`** | `search_orchestrator.py`, `hybrid_ranker.py`, `hybrid_reranker.py`, `searxng_client.py`, 10 domain ingestors | **Real & Operational** | Local SQLite FTS5 BM25 search + Reciprocal Rank Fusion (RRF, $k=60$) adapted from `llm-search`. |
| **`powers/` & `jarvis/powers/`** | `browser_powers.py`, `calendar_powers.py`, `email_powers.py`, `homeassistant_powers.py`, `desktop_powers.py`, `career_powers.py` | **Real & Operational** | RFC 5545 keyless calendar, RFC 822 email drafting with Tier-3 sending gate, Home Assistant REST with state readback, Playwright DOM reader. |
| **`api/` & `jarvis/api/`** | `server.py`, `routes_assistants.py`, `routes_tasks.py`, `routes_memory.py`, `routes_browser.py`, `routes_voice.py`, `routes_career.py` | **Real & Operational** | Live FastAPI server serving HUD dashboard, WebSocket telemetry stream, and drop-in OpenAI Assistants API (`/v1/threads`, `/v1/runs`). |
| **`voice/` & `jarvis/voice/`** | `wake.py`, `stt.py`, `tts.py`, `pipeline.py` | **Partially Mocked / Fallback** | Native Windows SAPI TTS fallback active; `faster-whisper` and `openWakeWord` run simulated audio buffers when CUDA models are absent. |
| **`integrations/`** | `github_integration.py`, `openrouter_integration.py`, `system_diagnostics.py` | **Simulated in CI** | Uses mocked fixtures in automated tests to prevent unbudgeted external network traffic and credential leakage. |

---

## 3. What is Broken / Architectural Deficiencies

1. **Missing Cognitive Loop Nodes**:
   - The LangGraph implementation is strictly linear (4 nodes).
   - Missing **Planner Node**: No multi-step goal decomposition before policy evaluation.
   - Missing **Critic / Verifier Node**: Model responses are not cross-checked against retrieved evidence before returning to the user.
   - Missing **Reflection / Correction Node**: Model failures do not trigger structured self-correction or user clarification loops.
2. **Untyped Error Handling**:
   - Failures currently bubble up as general exceptions rather than typed error classes (`TRANSIENT_NETWORK`, `SESSION_EXPIRED`, `POLICY_DENIED`, `AI_USAGE_LIMIT`, `INSUFFICIENT_EVIDENCE`, `PERMANENT_FAILURE`).
3. **Memory Consolidation Gap**:
   - Memory records persist indefinitely without a nightly consolidation ("sleep") cycle to deduplicate facts, reconcile contradictions, or decay unused inferred hypotheses.
4. **Ollama Offline Liveness**:
   - If the local Ollama service is unstarted on `127.0.0.1:11434`, calls fall back to offline simulation rather than exposing explicit readiness telemetry.

---

## 4. Analysis of CI Failure History (`CI_FAILURE_REPORT.md`)

Historical triage records identify 10 resolved failure modes:
1. **Lint/Syntax (`F821`)**: Missing `Optional` and `logger` imports in browser modules (Resolved).
2. **Missing Dependencies**: `playwright`, `scikit-learn`, and `pyyaml` omitted from manifests (Resolved).
3. **Network Lookups in CI**: Acceptance tests timing out on DNS lookups (Resolved via offline cached snapshots).
4. **Action Schema Mismatch**: NoneType iteration in power registry lookup (Resolved).
5. **Event Loop Collisions**: `asyncio.run()` called inside already running FastAPI event loops (Resolved via `ThreadPoolExecutor`).
6. **Linux Headless Display**: Missing `python3-tk` and `scrot` for PyAutoGUI (Resolved in `.github/workflows/ci.yml`).
7. **Supply-Chain Dependency Flags**: 13 CVEs in upstream `filelock` constrained by LiteLLM (Triage documented and excepted in CI audit).

---

## 5. Top 10 Technical Risks & Mitigations

| # | Risk Description | Severity | Impact | Mitigation Strategy |
|---|---|---|---|---|
| 1 | **VRAM Saturation on RTX 4050 (6GB)** | High | Out-of-memory crash during concurrent inference + browser automation | Bound active tool schemas to $\le 12$; prioritize quantized 4B local models (`qwen2.5:4b`, `llama3.1:8b-q4_K_M`). |
| 2 | **Untrusted Memory Policy Bypass** | Critical | Prompt injection via stored memories hijacking agent directives | Strict `<untrusted_memory_context>` delimiters; retrieved memories never grant authorization. |
| 3 | **Unintended Paid API Billing** | High | Accidental credit drain on managed cloud gateways | Hard zero-budget default in `CostGovernor`; cloud inference requires explicit opt-in flag. |
| 4 | **Outbound Action Escalation** | Critical | Agent sending unauthorized emails or executing destructive commands | Tier-2/3 cryptographic approval tokens bound to SHA-256 payload hashes with 15-minute expiration. |
| 5 | **Memory Loss on Container Rebuild** | High | User history wiped on container restart | Volume-mount SQLite (`PROJECT_ROOT/data/jarvis.db`) and PostgreSQL to persistent host storage. |
| 6 | **Embedding Drift Across Upgrades** | Medium | Old vector memories become unsearchable after model change | Version vector indexes; decoupling chat inference model from embedding model. |
| 7 | **Multiple Orchestrator Thrashing** | High | Deadlocks and state corruption from competing agent loops | LangGraph remains the single authoritative orchestrator. Zero secondary agent runtimes. |
| 8 | **Ambient Audio Eavesdropping** | High | Privacy violation from continuous microphone streaming | Local Silero VAD without raw buffer retention; recording activates ONLY on verified wake word or PTT. |
| 9 | **SSRF & DOM Poisoning via Browser** | High | Malicious external webpages probing local network or injecting instructions | Playwright restricted to public scheme URLs; private subnets blocked; DOM text sanitized before ingestion. |
| 10 | **Mid-Task Crash Inconsistency** | Medium | Interrupted multi-step tasks left in corrupt half-executed state | LangGraph state checkpointing with idempotent replay and resume capabilities. |

---

## 6. Baseline Performance Benchmarks (from `docs/BASELINE_BENCHMARK.json`)

- **Fast-path Instant Command Latency**: **28.83 ms** (Zero LLM cost, $0.00).
- **Memory Retrieval Precision**: **100.0%** (5/5 ground truth facts recalled).
- **Cross-User Data Isolation**: **0 leaks** (User B strictly isolated from User A).
- **Honest "Unknown" Response Rate**: **100.0%** (Zero fabricated memories for unlearned queries).
- **Mean Memory Search Latency**: **5.86 ms** (Local SQLite indexed search).
- **Hybrid RRF Reranker Latency**: **43.6 µs** (In-memory Reciprocal Rank Fusion).
