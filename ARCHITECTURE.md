# JARVIS System Architecture & Component Specification

## 1. High-Level Cognitive Architecture

JARVIS is engineered as a local-first, private AI operating system. The cognitive core is built on a 4-node LangGraph StateGraph coupled with LiteLLM for hybrid model routing, Mem0 for long-term episodic/semantic memory, PostgreSQL for relational state checkpoints, and Redis for streaming queues.

```text
User Request (REST / WebSocket / Dashboard / Voice)
                      │
                      ▼
               FastAPI Server (:8000)
                      │
                      ▼
     LangGraph Cognitive StateGraph Flow
  ┌───────────────────────────────────────────────┐
  │ 1. memory_retrieval Node                      │
  │    Queries Mem0 with user_id filter           │
  │    Injects prior memories into graph state    │
  └───────────────────────┬───────────────────────┘
                          │
                          ▼
  ┌───────────────────────────────────────────────┐
  │ 2. policy_check Node                          │
  │    Deterministic 4-Tier Risk Assessment       │
  │    Evaluates permissions.json                 │
  │    Halts Tier 2/3 operations without token    │
  └───────────────────────┬───────────────────────┘
                          │
                          ▼
  ┌───────────────────────────────────────────────┐
  │ 3. model_router Node                          │
  │    LiteLLM Unified Model Gateway (:4000)      │
  │    Routes: Local Ollama (Tier 1) / vLLM /     │
  │            Claude 3.7 / GPT-4o / Gemini 2.0   │
  │    Injects core_agent.md system prompt        │
  └───────────────────────┬───────────────────────┘
                          │
                          ▼
  ┌───────────────────────────────────────────────┐
  │ 4. memory_update Node                         │
  │    Stores turn provenance back into Mem0      │
  │    Records fact / hypothesis / preference     │
  └───────────────────────┬───────────────────────┘
                          │
                          ▼
                    End of Turn /
                 Response Dispatch
```

---

## 2. Core Subsystems

### A. LangGraph Cognitive State Machine
- **State Schema (`core/state.py`)**: `JarvisState` TypedDict maintaining `task_id`, `user_id`, `messages`, `retrieved_memories`, `task_type`, `risk_level`, `approval_required`, `approval_id`, `selected_tools`, `model_route`, `final_response`, and `evidence`.
- **Node Pipeline (`graph/nodes.py`)**: Sequential deterministic pipeline ensuring memory recall precedes reasoning, and policy screening prevents unapproved execution.

### B. LiteLLM Unified Gateway (`config/litellm/config.yaml`)
- Provides an OpenAI-compatible interface to local Ollama (`ollama/llama3.1`), private vLLM, and cloud frontiers (Claude Sonnet 4.5, GPT-5, Gemini 2.5 Pro).
- Enforces cloud-to-local automatic fallback (`claude-sonnet -> local-jarvis`).

### C. Mem0 Long-Term Memory Layer (`jarvis/memory/mem0_client.py`)
- User-scoped semantic memory indexing with SQLite 7-layer fallback adapter (`CAPTURE`, `RAW`, `EPISODIC`, `SEMANTIC`, `PROCEDURAL`, `WORKING`, `DIRECTIVE`).
- Tokenized salient search with bonus weighting for stated user preferences.

### D. Policy Engine & Safety Gate (`core/policy_engine.py`, `jarvis/core/policy_gate.py`)
- Tier 0: Autonomous read-only observations.
- Tier 1: Local reversible actions (drafts, local writes).
- Tier 2: Irreversible operations requiring explicit cryptographic approval.
- Tier 3: Critical system operations requiring step-up authentication.

### E. Append-Only Audit Ledger (`jarvis/core/audit.py`)
- SHA-256 hash-chained immutable audit ledger recording every user request, model inference call, policy evaluation, and tool execution.
