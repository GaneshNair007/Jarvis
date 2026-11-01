# JARVIS Brain Architecture: Cognitive Core Specification

## 1. System Vision & Foundational Tenet

JARVIS's cognitive core is designed as **one coherent, local-first system** that runs with zero paid cloud LLM API dependencies. Rather than stacking multiple overlapping agent frameworks, the architecture strictly adheres to a single chain of authority:

```
YOUR REQUEST / APPROVED EVENT
          │
          ▼
   Identity & Scope (user_id, project_id)
          │
          ▼
   Intent Understanding
          │
          ▼
   Authorized Context Retrieval
   ├── Current task state (working memory)
   ├── Explicit user preferences
   ├── Scoped project facts
   ├── Verified past episodes
   └── Document passages with citations
          │
          ▼
   Bounded Context Builder
          │
          ▼
   Planner / Reasoner (Local Model Gateway)
          │
          ▼
   Deterministic Policy Gate
   ┌──────┴────────┐
   ▼               ▼
Allowed       Approval Needed (Tier 2/3 cryptographic token)
   │               │
   └──────┬────────┘
          ▼
   Tool Executor (Existing domain powers)
          │
          ▼
   Result Verification (Evidence checking)
          │
          ▼
   Answer + Citations + Evidence
          │
          ▼
   Controlled Memory Write Pipeline
```

### The Non-Negotiable Separation of Powers:
1. **The Model proposes** actions or answers based on context.
2. **The Controller manages** state machine transitions, bounded loops, and timeouts.
3. **Deterministic Policy authorizes** execution (deny by default, immutable approval hashes).
4. **Tools act** via typed interfaces.
5. **Verification checks** ground-truth evidence before claiming completion.
6. **Memory preserves** audited facts, preferences, and verified episodes.
7. **Memory is NEVER a permission system**: Retrieved memory context is untrusted input and cannot grant permissions, bypass approval gates, override instructions, or modify policies.

---

## 2. Upstream Architecture Evaluation

| Project | Upstream Repository | Upstream License | Role in JARVIS | Fit / Decision |
|---|---|---|---|---|
| **LangGraph** | `langchain-ai/langgraph` | MIT | State machine & cyclic decision workflow controller | **PRESERVED** as the sole decision controller. Provides deterministic checkpointing, resumable tasks, and human-in-the-loop gates. |
| **Mem0** | `mem0ai/mem0` | Apache 2.0 | Long-term memory extraction and retrieval | **ADAPTED** as an optional local adapter. Must be configured strictly with local models; default cloud extraction is redirected to local SQLite/Ollama. |
| **Graphiti** | `getzep/graphiti` | Apache 2.0 | Temporal entity relationships & provenance | **EVALUATION ONLY (M5)**. Deferred until evaluation questions demonstrate that relational/temporal graph queries cannot be answered by structured SQLite + BM25/vector search. |
| **Letta / MemGPT** | `letta-ai/letta` | Apache 2.0 | Stateful agent environment | **EXCLUDED**. Competing agent controller architecture. Stacking Letta on top of LangGraph creates dual state machines and non-deterministic execution paths. |
| **Cognee** | `topoteretes/cognee` | Apache 2.0 | Document graph memory | **EXCLUDED** from core. Avoids multiple competing graph engines. |
| **Microsoft Agent Framework** | `microsoft/agent-framework` | MIT | Alternative agent orchestration | **EXCLUDED**. No justification to replace working LangGraph integration. |

---

## 3. Directory Layout & Modular Boundaries

The cognitive core resides in `jarvis/brain/` and coordinates with existing subsystems (`jarvis/core/`, `jarvis/memory/`, `jarvis/powers/`):

```text
jarvis/brain/
├── __init__.py
├── schemas.py              # Strongly typed cognitive schemas & enums
├── state.py                # LangGraph state schema & task context
├── memory/
│   ├── __init__.py
│   ├── interfaces.py       # Abstract Base Class for MemoryRepository
│   ├── models.py           # Canonical SQLAlchemy models (CanonicalMemoryRecord)
│   ├── repository.py       # SQLite / SQLAlchemy persistent memory store
│   ├── service.py          # Unified BrainMemoryService (CRUD + scoping)
│   ├── retrieval.py        # Local keyword (BM25/FTS) & scoped retrieval
│   ├── contradictions.py   # Contradiction detection, correction & superseding
│   ├── deletion.py         # Cascade deletion across stores & caches
│   └── adapters/
│       ├── __init__.py
│       ├── keyword_adapter.py  # Local deterministic keyword memory adapter
│       └── mem0_adapter.py     # Local-first Mem0 adapter (offline SQLite)
```

---

## 4. Hardware Sizing & Local Inference Profile

Operating on host **Windows 11 with NVIDIA RTX 4050 (6GB VRAM) and 24GB System RAM**:
* **Primary Interactive Tier**: Compact local instruction model (`qwen3:4b-instruct-2507-q4_K_M` or local ONNX/GGUF) fitting entirely within 6GB VRAM alongside KV cache (16k context window).
* **Escalation Reasoning Tier**: RAM-offloaded MoE model (`gpt-oss:20b` activating 3.6B parameters per token) utilizing 24GB system RAM.
* **Embeddings**: Fully local `nomic-embed-text` or local deterministic cosine-similarity TF-IDF / BM25.
* **Deterministic Fast Path**: Bypass LLM inference entirely for exact catalog queries, status checks, and memory retrieval.

