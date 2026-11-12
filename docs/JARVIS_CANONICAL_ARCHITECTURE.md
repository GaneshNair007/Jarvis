# JARVIS Canonical System Architecture Specification

**Document Version:** 2.0.0  
**Effective Date:** 2026-11-10  
**System Identity:** Private, Local-First Personal AI Operating System  
**Target Hardware Baseline:** Windows 11 64-bit, 24 GB System RAM, NVIDIA GeForce RTX 4050 Laptop GPU (6 GB VRAM)  
**Author:** Architecture and Vision Audit Worker (teamwork_worker)  
**Governing Documents:**
- `docs/constitution/JARVIS_MASTER_DIRECTIVE.md` (Version 1.2.0)
- `jarvis/constitution/*.yaml` (Machine-readable invariants)
- `docs/IRON_MAN_JARVIS_TARGET.md` & `docs/TARGET_ARCHITECTURE.md`
- `docs/JARVIS_VISION_VS_IMPLEMENTATION_AUDIT.md` (Preceding gap audit)

---

## 1. Architectural Paradigm & System Overview

JARVIS is designed not as a generic chatbot, an ephemeral web wrapper, or a collection of unlinked micro-agents, but as an **integrated, local-first Personal AI Operating System** built specifically for **Ganesh Nair**.

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 GANESH NAIR (OPERATOR)                                      │
└──────────────────────────────────────────────┬──────────────────────────────────────────────┘
                                               │ (Acoustic Voice / Screen / Hotkeys / CLI)
                                               ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                          JARVIS UNIFIED LOCAL RUNTIME (WINDOWS 11)                          │
│                                                                                             │
│  ┌───────────────────────┐  ┌──────────────────────┐  ┌──────────────────────────────────┐  │
│  │ 1. VOICE & SENSES     │  │ 2. COGNITIVE BRAIN   │  │ 3. TOOLS & HANDS                 │  │
│  │ - openWakeWord (Wake) │  │ - LangGraph 8-Node   │  │ - Win32 UIAutomation / SendInput │  │
│  │ - Faster-Whisper(STT) │  │   State Machine      │  │ - Local Process Execution        │  │
│  │ - Kokoro / SAPI (TTS) │  │ - Central CEO Router │  │ - Playwright Safe Navigator      │  │
│  │ - Screen Capture & OCR│  │ - Dynamic Workforce  │  │ - Cloned Capability Adapters     │  │
│  └───────────┬───────────┘  └──────────┬───────────┘  └────────────────┬─────────────────┘  │
│              │                         │                               │                    │
│              ▼                         ▼                               ▼                    │
│  ┌───────────────────────────────────────────────────────────────────────────────────────┐  │
│  │ 4. DETERMINISTIC SAFETY GATE & ZERO-LEAK SECURITY SHIELD                              │  │
│  │ - Deny-by-Default Policy (Levels 0–5)            - Presidio DLP & Regex Redactor      │  │
│  │ - Ephemeral HMAC-SHA256 Approval Tokens          - Hardware Emergency Kill Switch     │  │
│  └─────────────────────────────────────┬─────────────────────────────────────────────────┘  │
│                                        │                                                    │
│              ┌─────────────────────────┴────────────────────────┐                           │
│              ▼                                                  ▼                           │
│  ┌─────────────────────────────────────────┐  ┌──────────────────────────────────────────┐  │
│  │ 5. UNIFIED 8-LAYER MEMORY VAULT         │  │ 6. LOCAL HARDWARE MODEL ROUTER           │  │
│  │ - Single SQLite WAL Engine (`jarvis.db`)│  │ - Tier 0: Deterministic OS Bypass (0ms)  │  │
│  │ - Sub-ms FTS5 Lexical Search (BM25)     │  │ - Tier 1: Local Reflex SLM (3B, <=2.2GB) │  │
│  │ - Dense Vector Embeddings (nomic-embed) │  │ - Tier 2: Qwen 7B Q4 (Ollama Local)     │  │
│  │ - Relational Knowledge Graph (BFS)      │  │ - Tier 3: FreeLLMAPI (:3001 Cloud Proxy) │  │
│  │ - Linear 10-Reconciliation Alembic Chain│  │ - Hard Budget: <= 3.8 GB Active VRAM     │  │
│  └─────────────────────────────────────────┘  └──────────────────────────────────────────┘  │
│                                        │                                                    │
│                                        ▼                                                    │
│  ┌───────────────────────────────────────────────────────────────────────────────────────┐  │
│  │ 7. CRYPTOGRAPHIC AUDIT LEDGER (SHA-256 APPEND-ONLY CHAIN)                            │  │
│  │ - Immutable record of every tool execution, approval token, evidence, and reflection  │  │
│  └───────────────────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 1.1 Core Constitutional Invariants
1. **Local-First Autonomy**: The operating system must boot, reason, execute desktop tasks, retrieve memories, and speak without requiring paid third-party APIs or an active WAN connection.
2. **Strict Hardware Envelope**: Total active GPU VRAM usage across all models and buffers must remain strictly within **3.8 GB** (safely below the 6.0 GB hardware ceiling of the host NVIDIA GeForce RTX 4050, leaving >= 2.2 GB dedicated headroom to completely prevent WDDM PCIe spillover and the 110x slowdown). System RAM must not exceed 16 GB during peak workloads.
3. **The Four Sovereign Laws**:
   - **First Law (No Evidence = No Claim)**: Every external action must yield verifiable ground-truth receipts.
   - **Second Law (No Simulation = No Pretending)**: Zero mocks, fake sleep delays, or canned strings in production paths.
   - **Third Law (Capability Before Execution)**: Verify capability existence, authentication, connectivity, health, and authorization before dispatching tasks.
   - **Fourth Law (No Memory Without Reflection)**: No goal or task may transition to `COMPLETED` without writing a verified reflection record to persistent storage.
4. **Single Boss Rule**: Multi-agent tasks are centrally planned and assigned by the CEO Agent through Department Managers; uncontrolled peer-to-peer self-assignment is physically blocked.

---

## 2. Canonical Execution Pipeline

The canonical architecture eliminates the eight competing orchestration mechanisms identified in the audit (`JarvisOrchestrator`, `AutonomousWorkforceSwarm`, `RuFloConsensusSwarm`, `AgentSwarmCoordinator`, etc.) and unifies all execution into a single, deterministic nine-stage lifecycle:

```
[1. Acoustic Wake ("Hey Jarvis")]
               │
               ▼
   [2. Senses / Perception] ── (Audio transcription, active window context, screen capture)
               │
               ▼
    [3. Memory Recall] ────── (FTS5 lexical search, vector similarity, knowledge graph BFS)
               │
               ▼
   [4. LangGraph Brain] ───── (Central CEO planner: goal decomposition into atomic DAG nodes)
               │
               ▼
 [5. Policy / Safety Gate] ── (DLP scan, privilege level check, HMAC human approval token)
               │
               ▼
[6. Tools / Hands Execute] ── (Desktop Win32, Playwright, MCP tools, local subprocesses)
               │
               ▼
[7. Independent Verify] ───── (Ground-truth evidence inspection, test execution, UI diff)
               │
               ▼
[8. Continuous Reflect] ───── (Fourth Law retrospective: successes, failures, gaps logged)
               │
               ▼
[9. Memory Persistence] ───── (Commit episodic trace, reflections, and SHA-256 audit entry)
```

### 2.1 Stage-by-Stage Specifications

| Stage | Input | Primary Component | Output | Error Behavior |
| :--- | :--- | :--- | :--- | :--- |
| **1. Acoustic Wake** | Real-time 16 kHz microphone PCM audio stream | `jarvis.voice.wake.AcousticWakeDetector` (`openWakeWord`) | Wake trigger event + timestamp | Ignores background noise; falls back to push-to-talk / CLI hotkey. |
| **2. Perception** | Captured utterance buffer + active display buffer | `jarvis.voice.stt.SpeechToText` (`faster-whisper`) + `jarvis.powers.screen_powers` | Text command transcript + window metadata | Emits `VoiceRecognitionError`; fails closed without emitting canned text. |
| **3. Memory Recall** | User query + context metadata | `jarvis.memory.store.UnifiedMemoryStore` | Retrieved preferences, past task solutions, entity facts | If empty, proceeds with zero-shot context; never halts. |
| **4. LangGraph Brain** | Transcript + retrieved memories + state | `jarvis.brain.graph.JarvisStateGraph` | Formulated DAG execution plan with assigned worker roles | If cyclic or invalid, triggers graph replanner or queries user. |
| **5. Policy Gate** | Target tool + execution arguments | `jarvis.security.policy_gate.DeterministicPolicyGate` | Authorization grant OR approval challenge | Rejects unauthorized actions immediately; prompts operator for Level 3/4 tasks. |
| **6. Tool Execution** | Authorized execution payload | Validated Tool Registry (`PowerBinder`) | Direct tool execution outputs (stdout, file writes, Win32 events) | Captures stderr/exception; emits honest failure payload. |
| **7. Independent Verification** | Tool outputs + expected postconditions | `jarvis.brain.nodes.verify` + `jarvis.core.evidence` | Verified `TrustResult` + cryptographic `Evidence` receipt | If postcondition fails, routes back to `reflect` node for error diagnosis. |
| **8. Continuous Reflection** | Execution history + verification outcomes | `jarvis.brain.nodes.reflect` | Structured `ReflectionRecord` (Fourth Law artifact) | If reflection fails to persist, task status remains `INCOMPLETE`. |
| **9. Memory Persistence** | Reflection + execution trace + audit item | `jarvis.memory.repository.MemoryRepository` + `AuditLedger` | Commits SQLite transaction + SHA-256 chained audit hash | Transaction rolls back atomically on error. |

---

## 3. LangGraph Brain: Cognitive State Machine & Separation of Powers

The cognitive core of JARVIS is an **8-node Cyclic Finite-State Machine (FSM)** compiled using LangGraph with SQLite WAL checkpointing (`SqliteCheckpointSaver`). Directed cycles exist by design across error recovery loops (`reflect -> plan` and `reflect -> act`).

**State Machine Taxonomy & Loop Governance:**
- **FSM Topology**: Cyclic state machine with bounded loop guards (`reflection_count <= 3`).
- **Subtask DAG Governance**: The atomic subtask execution plan generated by the `plan` node is an acyclic Directed Acyclic Graph (DAG) strictly validated by Kahn's algorithm (`jarvis.core.task_graph.TaskGraph`). Circular subtask dependencies are rejected before execution begins.
- **Recursion Safety Limit**: All graph invocations must explicitly configure `recursion_limit=50` (e.g. `app.invoke(state, config={"recursion_limit": 50})`). This provides safe headroom above the 24-step sequence consumed during 3 recovery retries, eliminating unhandled `GraphRecursionError` exceptions.
- **Error History Preservation**: Error telemetry is accumulated across checkpoint turns rather than wiped in `perceive()`, enabling root-cause diagnosis in `reflect`.

```
                    ┌─────────────────┐
                    │      START      │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │    perceive     │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │     recall      │
                    └────────┬────────┘
                             │
              ┌──────────────┴──────────────┐
              ▼ (fast-path bypass)          ▼ (complex multi-step)
       ┌─────────────┐               ┌─────────────┐
       │   policy    │               │    plan     │
       └──────┬──────┘               └──────┬──────┘
              │                             │
              │                             ▼
              │                      ┌─────────────┐
              │                      │   policy    │
              │                      └──────┬──────┘
              │                             │
              ├─────────────────────────────┘
              ▼
       ┌─────────────┐
       │     act     │
       └──────┬──────┘
              │
              ▼
       ┌─────────────┐
       │   verify    │
       └──────┬──────┘
              │
              ▼
       ┌─────────────┐
       │   reflect   │
       └──────┬──────┘
              │
       ┌──────┴─────────────────────────────┐
       ▼ (recoverable error <= 3 retries)   ▼ (verified complete / fatal)
 ┌───────────┐                       ┌─────────────┐
 │   plan    │                       │  remember   │
 └───────────┘                       └──────┬──────┘
                                            │
                                            ▼
                                     ┌─────────────┐
                                     │     END     │
                                     └─────────────┘
```

### 3.1 Separation of Powers Principle
To prevent catastrophic model hallucinations or privilege escalations, JARVIS strictly separates cognitive responsibilities:
- **Models Propose**: The LLM suggests plans, parses text, and formats parameters. It has zero direct access to system syscalls, databases, or outbound networks.
- **Controller Manages Transitions**: LangGraph deterministically manages state transitions, checkpointing, retry counters, and error recovery loops.
- **Deterministic Policy Authorizes**: The Policy Gate evaluates proposed actions against hardcoded privilege rules and HMAC tokens, entirely independent of model prompts.
- **Tools Execute**: Tools run in isolated worker functions with explicit input validation and strict subprocess timeouts.
- **Verifier Checks Evidence**: An independent verifier validates file diffs, exit codes, and process IDs against expected postconditions.
- **Memory Preserves Audited Facts**: Only verified execution traces and Fourth-Law reflection records are committed to persistent memory.

### 3.2 Canonical State Schema (`JarvisState`)
```python
class JarvisState(TypedDict):
    task_id: str                          # Unique task UUID
    session_id: str                       # Active conversation / voice session UUID
    user_id: str                          # Scoped tenant identifier ("ganesh")
    user_input: str                       # Raw user prompt or transcribed speech
    input_event: Optional[Dict[str, Any]] # Audio/screen/hotkey origin metadata
    retrieved_memories: List[Dict[str, Any]] # Injected long-term memories
    plan: List[Dict[str, Any]]            # Topological DAG of atomic work steps
    current_step_index: int               # Active execution pointer
    policy_clearance: Dict[str, Any]      # Privilege clearance & HMAC approval token
    tool_results: List[Dict[str, Any]]    # Outputs from executed tools
    evidence: List[Dict[str, Any]]        # Ground-truth evidence receipts
    verification_score: float             # Verifier confidence (0.0 to 1.0)
    retry_count: int                      # Step retry counter (max 3)
    reflection: Optional[Dict[str, Any]]  # Fourth Law retrospective record
    final_response: str                   # Synthesized spoken / text response
    status: str                           # "RUNNING", "COMPLETED", "FAILED", "BLOCKED"
```

### 3.3 Deterministic Zero-Token Reflection for Tier 0 Fast-Path Commands
The Fourth Law mandates: *"A task is not complete until it has produced and persisted a verifiable reflection record containing lessons, failures, successes, capability gaps."*

For deterministic Win32 OS syscalls and desktop hotkeys executed via Tier 0 (e.g., "mute volume", "open Notepad", "take screenshot", "lock screen"), invoking an LLM prompt to generate a retrospective reflection would introduce a 500–1200ms latency penalty, destroying real-time voice responsiveness.

**Deterministic Reflection Protocol:**
- For Tier 0 actions, `jarvis.brain.nodes.reflect` generates a **lightweight, deterministic reflection record without invoking an LLM**:
  ```python
  reflection = ReflectionRecord(
      task_id=state["task_id"],
      execution_tier="TIER_0_BYPASS",
      llm_tokens_consumed=0,
      success=state["verification_score"] == 1.0,
      duration_ms=execution_duration_ms,
      lessons_learned=[],
      capability_gaps=[],
      timestamp=time.time()
  )
  ```
- Written directly to SQLite WAL (`data/jarvis.db`, table `reflections`) in <1ms, upholding 100% Fourth Law constitutional compliance with zero user latency penalty.

---

## 4. Repository Structural Consolidation & Clean Packaging

To resolve the structural dualism identified in Audit Gap 1, the repository is consolidated into a single standard Python package (`jarvis/`). All root shadow trees are collapsed, and root wrappers are removed.

### 4.1 Canonical Target Directory Layout
```
jarvis/
├── __init__.py
├── main.py                       # Unified CLI entry point (`jarvis serve`, `chat`, `voice`)
├── config.py                     # Hardware-budgeted Pydantic settings
│
├── api/                          # FastAPI REST & WebSocket Server
│   ├── __init__.py
│   ├── server.py                 # Single unified server mounting canonical routes
│   └── routes/                   # Clean modular sub-routers
│       ├── chat.py               # Unified POST /api/v1/chat -> LangGraph
│       ├── voice.py              # Audio streaming & microphone triggers
│       ├── memory.py             # Memory query & reflection inspection
│       ├── audit.py              # Tamper-evident ledger inspection
│       └── tools.py              # Tool catalog & status
│
├── brain/                        # LangGraph Reasoning & Cognitive Core
│   ├── __init__.py
│   ├── graph.py                  # Authoritative 8-node LangGraph StateGraph
│   ├── state.py                  # JarvisState TypedDict schema
│   ├── planner.py                # DAG task decomposition & Kahn's topological sort
│   └── nodes/                    # Atomic node implementations
│       ├── perceive.py           # Ingests multimodal perception events
│       ├── recall.py             # FTS5 + vector + graph context retrieval
│       ├── plan.py               # Formulates execution DAG
│       ├── policy.py             # Enforces privilege checks & HMAC gates
│       ├── act.py                # Dispatches validated tools to dynamic workers
│       ├── verify.py             # Validates physical postconditions & evidence
│       ├── reflect.py            # Generates Fourth Law reflection records
│       └── remember.py           # Persists state to SQLite WAL
│
├── core/                         # Fundamental OS Primitives
│   ├── __init__.py
│   ├── model_router.py           # 4-tier model router (T0 OS, T1 Ollama 3B, T2 Ollama 7B, T3 FreeLLM)
│   ├── freellm_client.py         # FreeLLMAPI cloud proxy client (:3001 with Presidio DLP)
│   ├── audit.py                  # Cryptographic SHA-256 chained transaction log
│   ├── evidence.py               # Evidence and TrustResult data structures
│   ├── policy_gate.py            # Privilege levels 0-5 and emergency kill switch
│   └── scheduler.py              # Single background task loop
│
├── security/                     # Defense-in-Depth Shield
│   ├── __init__.py
│   ├── ten_layer_shield.py       # Presidio DLP, entropy secret scanner, AES-256 vault
│   └── hmac_gate.py              # Ephemeral cryptographic single-use approvals
│
├── voice/                        # Local Voice Perception & Speech Synthesis
│   ├── __init__.py
│   ├── daemon.py                 # Continuous microphone streaming & VAD loop
│   ├── wake.py                   # openWakeWord acoustic detection ("Hey Jarvis")
│   ├── stt.py                    # faster-whisper local CUDA/CPU transcription
│   └── tts.py                    # kokoro-onnx CPU neural TTS + Windows SAPI baseline
│
├── memory/                       # Unified 8-Layer Memory Vault
│   ├── __init__.py
│   ├── store.py                  # SQLite WAL repository with FTS5 lexical search
│   ├── models.py                 # SQLAlchemy 2.0 relational models (10 domains)
│   ├── embeddings.py             # Local dense vector generation (nomic-embed-text)
│   └── graph_repo.py             # Relational knowledge graph with BFS traversal
│
├── tools/                        # Verified Tools & Cloned Capability Adapters
│   ├── __init__.py
│   ├── registry.py               # Validated tool registry (`PowerBinder`)
│   ├── desktop.py                # Win32 UIAutomation, mouse, keyboard, Notepad P0
│   ├── browser.py                # Safe Playwright navigator (anti-SSRF isolated)
│   └── adapters/                 # Adapters for cloned repositories
│       ├── firecrawl_adapter.py  # Local web extraction adapter
│       ├── freellm_adapter.py    # FreeLLMAPI cloud proxy adapter (with Presidio DLP)
│       └── claude_style_adapter.py # Coding discipline guidelines adapter
│
├── agents/                       # Autonomous Workforce Dynamic Lifecycle
│   ├── __init__.py
│   ├── lifecycle.py              # Worker pool supervisor (spawn, pause, retire)
│   └── templates/                # Specialized role prompts and tool sets
│       ├── engineering.py        # Code, test, and repo workers
│       ├── research.py           # Web research & citation synthesis workers
│       └── career.py             # Resume & opportunity scouting workers
│
└── dashboard/                    # Real-Time Glassmorphic Mission-Control HUD
    └── index.html                # Single canonical frontend served over WebSocket
```

### 4.2 Packaging Manifest (`pyproject.toml`)
```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "jarvis"
version = "2.0.0"
description = "Personal AI Operating System - Local-first, private multi-agent operator."
readme = "README.md"
requires-python = ">=3.10"
authors = [{ name = "Ganesh Nair" }]

dependencies = [
    "fastapi>=0.110.0",
    "uvicorn[standard]>=0.29.0",
    "pydantic>=2.7.0",
    "pydantic-settings>=2.2.0",
    "langgraph>=0.2.0",
    "langchain-core>=0.3.0",
    "sqlalchemy>=2.0.0",
    "alembic>=1.13.0",
    "httpx>=0.27.0",
    "websockets>=12.0",
    "cryptography>=42.0.0",
    "numpy>=1.26.0",
    "psutil>=5.9.0",
    "python-dotenv>=1.0.0",
    "sounddevice>=0.4.6",
    "openwakeword>=0.6.0",
    "faster-whisper>=1.0.0",
    "kokoro-onnx>=0.3.0",
    "pywin32>=306; sys_platform == 'win32'",
    "pyautogui>=0.9.54",
    "pillow>=10.0.0",
    "reportlab>=4.0.0",
    "pypdf>=4.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.1.0",
    "pytest-asyncio>=0.23.0",
    "ruff>=0.4.0",
]

[project.scripts]
jarvis = "jarvis.main:cli_entrypoint"

[tool.setuptools.packages.find]
where = ["."]
include = ["jarvis*"]
```

---

## 5. Verifiable Autonomous AI Workforce & Dynamic Agent Lifecycle

The canonical architecture completely discards the static 105-dataclass loop (`AutonomousWorkforceSwarm`) and implements the **Dynamic Agent Lifecycle Model** governed by the Central CEO Router.

```
                    ┌────────────────────────┐
                    │      CENTRAL CEO       │
                    │ (LangGraph Brain Node) │
                    └───────────┬────────────┘
                                │
                                ▼
                    ┌────────────────────────┐
                    │   WORKFORCE MANAGER    │
                    │ (Max 2-3 Active Concurrency)
                    └───────────┬────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌───────────────┐       ┌───────────────┐       ┌───────────────┐
│ SPAWNED STATE │       │ ACTIVE STATE  │       │ RETIRED STATE │
│ - Allocates   │──────▶│ - Holds Permit│──────▶│ - Persists    │
│   Worker Role │       │ - Executes DAG│       │   Trace &     │
│ - Injects MCP │       │   Atomic Step │       │   Evidence    │
│   Tool subset │       │ - Employs     │       │ - Frees Memory│
└───────────────┘       └───────┬───────┘       └───────────────┘
                                │ (Human Approval / External IO)
                                ▼
                        ┌───────────────┐
                        │ PAUSED STATE  │
                        │ - RELEASES    │
                        │   Semaphore   │
                        │   Permit      │
                        │ - Yields CPU  │
                        └───────────────┘
```

### 5.1 Workforce Governance Rules
1. **Bounded Concurrency & Deadlock Prevention**:
   - To strictly preserve the 6 GB VRAM and 24 GB RAM envelopes, no more than **2 to 3 workers** may execute concurrently (`asyncio.Semaphore(3)`).
   - **Deadlock Prevention Invariant**: When a worker transitions from `ACTIVE` to `PAUSED` (awaiting human HMAC authorization or slow external I/O), it **MUST immediately release its semaphore permit** (`semaphore.release()`) and await an `asyncio.Event`. This guarantees that long approval waits do not exhaust the permit pool and will never block Level 0 read-only queries or fast-path commands. Upon approval receipt, the worker re-acquires a permit before resuming execution.
2. **On-Demand Lifecycle**:
   - `SPAWN`: A worker agent is instantiated only when a specific DAG node requires its capability. It receives a scoped prompt and a minimal, whitelisted subset of tools.
   - `ACTIVE`: The worker holds a concurrency permit and executes its task using Tier 1 or Tier 2 local inference.
   - `PAUSE`: The worker releases its semaphore permit, yields CPU execution, and registers an approval listener. Model weights remain pinned in Ollama (no dynamic disk unloading).
   - `RETIRE`: Upon task completion or unrecoverable error, the worker transitions to `RETIRED`. Its execution transcript, tool receipts, and evidence items are written to episodic memory, and its memory footprint is garbage collected.
3. **Verifiable Execution**: Workers never self-certify completion. Output artifacts must be inspected and verified by the independent `verify` node.

---

## 6. Unified 8-Layer Memory Persistence & Database Architecture

All memory fragmentation is resolved by consolidating storage into a single SQLite database (`data/jarvis.db`) configured with Write-Ahead Logging (`PRAGMA journal_mode = WAL`), synchronized durability, and atomic transactions via the Unit of Work pattern.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       SINGLE SQLITE WAL DATABASE (`data/jarvis.db`)         │
├─────────────────────────────────────────────────────────────────────────────┤
│ 1. Working Memory     : Active LangGraph state checkpoints (durable resume) │
│ 2. Conversation Memory: Multi-turn chat utterances & user interaction logs │
│ 3. Episodic Memory    : Historical task execution traces & tool diff receipts│
│ 4. Semantic Memory    : Dense vector embeddings (nomic-embed) + Cosine Sim  │
│ 5. Procedural Memory  : DAG workflow templates & validated runbooks        │
│ 6. Knowledge Memory   : Relational knowledge graph (`nodes` & `edges` BFS)  │
│ 7. Identity Memory    : System constitution, values, and user preferences   │
│ 8. Correction Memory  : User corrections, heuristics, and avoidance rules   │
│                                                                             │
│ ── INTEGRATED RETRIEVAL ENGINES ─────────────────────────────────────────── │
│ • FTS5 Virtual Table (`memories_fts`): Sub-millisecond BM25 keyword search  │
│ • Embedded Vector Table (`memory_vectors`): 768-dim semantic similarity     │
│ • Relational Tables: 16 normalized tables reconciled across 10 Alembic revs │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.1 Database Schema & Reconciliation of 10 Domain Migrations
The orphaned migrations in `db/migrations/` are consolidated into a linear Alembic version chain under `alembic/versions/`:
- `0001_core_system`: `system_config`, `process_registry`, `sessions`.
- `0002_goals_and_dag`: `goals`, `task_graphs`, `tasks`, `task_dependencies`.
- `0003_departments_and_agents`: `departments`, `agents`, `agent_assignments`, `agent_lifecycle`.
- `0004_tool_executions`: `executions`, `evidence_records`, `approvals`.
- `0005_unified_memories`: `canonical_memories`, `memories_fts` (FTS5 table), `memory_vectors`.
- `0006_reflections_and_learning`: `reflections` (Fourth Law storage), `lessons_learned`, `gaps`.
- `0007_capabilities_and_radar`: `capabilities`, `opportunities` (hackathons, careers).
- `0008_governed_pr_workflow`: `improvement_requests`, `pr_workflows`.
- `0009_knowledge_graph`: `knowledge_nodes`, `knowledge_edges`.
- `0010_cryptographic_audit`: `audit_events` (SHA-256 chained transaction log).

---

## 7. Always-Available Voice & Multimodal Perception Architecture

Voice activation is the primary human interface for JARVIS and operates with zero dependency on cloud services.

```
 [Microphone Stream (16kHz 16-bit PCM)]
                  │
                  ▼
┌───────────────────────────────────────────────────────────────┐
│ STAGE 1: ACOUSTIC DETECTION (openWakeWord)                    │
│ - Continuous low-power ring buffer (<1% CPU, 0 MB VRAM)       │
│ - Trigger keyword: "Hey Jarvis" (confidence threshold >= 0.65)│
└───────────────────────────────┬───────────────────────────────┘
                                │ Wake Detected
                                ▼
┌───────────────────────────────────────────────────────────────┐
│ STAGE 2: ADAPTIVE SPEECH CAPTURE (Silero VAD)                 │
│ - Dynamic silence detection (500ms trailing pause cutoff)     │
│ - Buffers exact utterance into memory                         │
└───────────────────────────────┬───────────────────────────────┘
                                │ Utterance Buffer
                                ▼
┌───────────────────────────────────────────────────────────────┐
│ STAGE 3: LOCAL STREAMING TRANSCRIPTION (Faster-Whisper)       │
│ - Model: `faster-whisper-base.en` (CUDA int8, ~650 MB VRAM)   │
│ - Latency: 120–220ms on RTX 4050                              │
│ - Fail-safe: Emits VoiceRecognitionError on failure (no canned)│
└───────────────────────────────┬───────────────────────────────┘
                                │ Text Transcript
                                ▼
┌───────────────────────────────────────────────────────────────┐
│ STAGE 4: COGNITIVE PROCESSING (LangGraph Brain)               │
│ - Executes task, controls tools, verifies postconditions      │
└───────────────────────────────┬───────────────────────────────┘
                                │ Synthesized Text Response
                                ▼
┌───────────────────────────────────────────────────────────────┐
│ STAGE 5: NEURAL & NATIVE SPEECH SYNTHESIS (CPU OFFLOADED)     │
│ - Primary: `kokoro-onnx` (82M params, CPUExecutionProvider)   │
│   * VRAM Consumption: 0 MB (100% Host CPU execution)          │
│   * Synthesis Latency: sub-100ms on multi-core x64 CPU        │
│ - Instant Baseline Fallback: Windows Native SAPI SpVoice      │
│   (`win32com.client.Dispatch("SAPI.SpVoice")`)                │
│   * Zero-dependency native speech; active immediately        │
│ - Total Ban: 440 Hz sine waves mathematically eradicated      │
│ - Barge-in: Immediate audio cutoff on new microphone wake     │
└───────────────────────────────────────────────────────────────┘
```

### 7.1 Windows 11 Audio Capture & Resampling Pipeline
Windows 11 Realtek Microphone Arrays typically stream audio natively at 44.1 kHz or 48.0 kHz 24-bit/16-bit PCM. Feeding non-16 kHz streams directly into `openWakeWord` or `faster-whisper` causes sample misinterpretation, buffer overruns, or complete detection failure.

**Audio Resampling Architecture:**
- `jarvis.voice.daemon.MicrophoneStream`: Opens native WASAPI input stream via `sounddevice.InputStream(samplerate=None, channels=1, dtype='int16')`.
- In-memory Polyphase Resampler: Uses `scipy.signal.resample_poly` (or `numpy` decimation) to resample native input frames (48,000 Hz -> 16,000 Hz with ratio 1:3; or 44,100 Hz -> 16,000 Hz with ratio 160:441).
- Normalization: Converts resampled audio into 16 kHz 16-bit mono PCM ring buffer for acoustic wake detection.

### 7.2 Multimodal Screen Perception & See-Act-Verify
For computer automation, JARVIS enforces a 3-tier visual perception hierarchy:
1. **Tier 1 (Win32 UIAutomation)**: Query native Windows OS accessibility tree via `pywinauto` to locate interactive controls by `AutomationId` or name.
2. **Tier 2 (Local OCR)**: When accessibility trees are unexposed, capture active window region via `mss` and run local OCR (`pytesseract` or Windows Native Media OCR) to resolve text click coordinates.
3. **Tier 3 (Local VLM Grounding)**: For arbitrary icons, crop the target region and query a lightweight vision model (e.g. MiniCPM-V 2.6 via FreeLLMAPI router) to determine bounding box coordinates.
4. **Post-Action Verification**: Every UI action captures a post-click window diff to verify that focus shifted, dialogs appeared, or text was written.

---

## 8. Hardware-Budgeted Model Inference Topology

The inference topology is strictly budgeted to honor the **24 GB RAM / 6 GB VRAM** baseline of Windows 11 and the NVIDIA GeForce RTX 4050.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│         NVIDIA RTX 4050 (6.0 GB) CONSERVATIVE VRAM BUDGET ALLOCATION        │
├─────────────────────────────────────────────────────────────────────────────┤
│ Windows 11 DWM & Desktop Compositor (Empirical Idle): ~ 0.90 GB             │
│ Streaming STT (`faster-whisper-base.en` int8 CUDA)  : ~ 0.65 GB             │
│ Neural TTS (`kokoro-onnx` CPU runtime)              :   0.00 GB (CPU-only)  │
│ Local Active SLM (`Qwen2.5:3B-Instruct` Q4_K_M)     : ~ 2.10 GB             │
│ TOTAL CONCURRENT ACTIVE GPU ALLOCATION              : ~ 3.65 GB (<= 3.8 GB) │
├─────────────────────────────────────────────────────────────────────────────┤
│ DEDICATED GDDR6 HEADROOM (Prevents WDDM Spillover)  : >= 2.35 GB (Safe)     │
└─────────────────────────────────────────────────────────────────────────────┘
*Critical Invariant*: Total active GPU allocation MUST remain <= 3.8 GB. Allocating
beyond 5.2 GB triggers Windows WDDM PCIe paging to shared system RAM, causing a 
110x latency explosion (bandwidth collapses from 116.9 GB/s to 1.06 GB/s).
Heavy reasoning (7B/14B) must run via Ollama with sequential STT unloading or 
Tier 3 FreeLLMAPI (0 MB VRAM) with Presidio DLP sanitization.
```

### 8.1 The Four-Tier Model Routing Topology

```
                                  [ INCOMING REQUEST ]
                                            │
                                            ▼
                             ┌─────────────────────────────┐
                             │    Intent & Sensitivity     │
                             │       Classification        │
                             └──────────────┬──────────────┘
                                            │
         ┌────────────────────────┬─────────┴──────────────┬────────────────────────┐
         ▼                        ▼                        ▼                        ▼
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│     TIER 0       │     │      TIER 1      │     │      TIER 2      │     │      TIER 3      │
│  DETERMINISTIC   │     │   LOCAL REFLEX   │     │ LOCAL REASONING  │     │ FREE CLOUD PROXY │
│    OS BYPASS     │     │   (OLLAMA SLM)   │     │  (OLLAMA LOCAL)  │     │ (FREELLM ROUTER) │
├──────────────────┤     ├──────────────────┤     ├──────────────────┤     ├──────────────────┤
│ - Exact commands │     │ - Qwen2.5:3B Q4  │     │ - Qwen2.5:7B Q4  │     │ - FreeLLMAPI     │
│   (open, close,  │     │ - Latency: 200ms │     │ - Latency: 600ms │     │   (:3001 router) │
│   volume, lock)  │     │ - VRAM: ~2.1 GB  │     │ - VRAM: ~4.4 GB  │     │ - Proxies WAN to │
│ - Latency: 1-5ms │     │ - Zero WAN Egress│     │ - Zero WAN Egress│     │   Groq Cloud API │
│ - VRAM: 0 MB     │     │ - Task: intent,  │     │ - Task: DAG plan,│     │ - Mandatory DLP  │
│ - Tokens: 0      │     │   triage, reflex │     │   private RAG    │     │ - VRAM: 0 MB     │
└──────────────────┘     └──────────────────┘     └──────────────────┘     └──────────────────┘
```

### 8.2 FreeLLMAPI External Cloud Proxy Router Integration (`http://localhost:3001`)
While the FreeLLMAPI service process (`node.exe`, PID 37816) executes locally on Windows loopback port 3001, **empirical SQLite network inspection confirms that FreeLLMAPI is an external cloud proxy router forwarding requests across the WAN to Groq's cloud API (`https://api.groq.com/openai/v1`)**. It does not perform local GPU inference and does not provide an air-gapped zero-egress boundary.

**Operational Constraints & Privacy Guardrails:**
- **Tier Classification**: Formally designated as **Tier 3 (External Free-Tier Cloud Fallback)**.
- **Endpoint & Wire Format**: `http://localhost:3001/v1/chat/completions` (OpenAI wire format).
- **Mandatory Authorization Header**: Requires header `Authorization: Bearer <FREELLMAPI_API_KEY>` (provisioned via `FREELLMAPI_KEY` environment variable or Windows DPAPI vault; no plaintext credentials stored in repo).
- **Data Loss Prevention (DLP) Invariant**: All prompt content dispatched to port 3001 must pass through `jarvis.security.ten_layer_shield.PresidioDLPFilter` to scrub API keys, credentials, PII, and sensitive entities (`[REDACTED_SECRET]`).
- **Strict Memory Vault Exclusion**: Prompts containing private user memories, financial/medical data, or credentials from `data/jarvis.db` are strictly forbidden from routing to FreeLLMAPI and must fail over to local Ollama.
- **Health Probing**: Real-time probe to `http://localhost:3001/readyz` (timeout 1.5s).
- **Failover Priority Chain**: Local Ollama (Tier 1 / Tier 2) -> FreeLLMAPI (Tier 3 with Presidio DLP) -> Tier 0 Deterministic OS Fallback.

---

## 9. Zero-Trust Security, DLP Shield, Policy Gate & Cryptographic Audit Ledger

Security is governed by a **deny-by-default deterministic gate** and a 10-layer Data Loss Prevention shield.

### 9.1 Privilege Clearance Hierarchy (Levels 0–5)
- **Level 0 (Public Read & Perception)**: Reading public files, active window inspection, time checks. -> *Autonomous execution.*
- **Level 1 (Local Workspace Writes)**: Writing to `data/scratchpad/`, saving temporary notes. -> *Autonomous execution; logged to audit ledger.*
- **Level 2 (Outbound Communication)**: Sending emails, WhatsApp notifications, external webhooks. -> *Mandatory Operator Confirmation.*
- **Level 3 (System & Shell Execution)**: Spawning subprocesses, running PowerShell commands, killing processes. -> *Mandatory Ephemeral HMAC-SHA256 Token.*
- **Level 4 (Destructive OS Operations)**: Deleting files, modifying system registry, formatting drives. -> *Mandatory Ephemeral HMAC Token + Password Prompt.*
- **Level 5 (Direct Production Git Push)**: Pushing code to `main` or `master`. -> **PHYSICALLY BLOCKED**. Autonomous PR creation only.

### 9.2 Ephemeral HMAC-SHA256 Single-Use Approvals
For Level 3 and 4 actions:
1. The Policy Gate serializes the exact execution payload (`tool_name`, `args`, `target_path`) and generates a SHA-256 digest:
   $$\text{payload\_hash} = \text{SHA256}(\text{canonical\_json}(\text{payload}))$$
2. The user confirms via HUD button or voice phrase, generating an HMAC-SHA256 signature bound to an ephemeral secret and timestamp with a 60-second expiration.
3. Any alteration to the payload parameters invalidates the cryptographic signature, preventing prompt injection or parameter hijacking.

### 9.3 Cryptographic Chained Audit Ledger
Every system transaction is committed to an append-only cryptographic ledger (`jarvis.core.audit.AuditLedger`):
$$\text{entry\_hash}_i = \text{SHA256}(\text{payload}_i \,\|\, \text{evidence\_hash}_i \,\|\, \text{entry\_hash}_{i-1})$$
Any attempt to tamper with historical execution logs or falsify test outcomes alters the hash chain, alerting the security monitor.

---

## 10. Architectural Invariants & Failure-Mode Truth Table

The canonical architecture enforces deterministic, verifiable failure behaviors across all boundary conditions:

| Trigger Condition | Forbidden Behavior (Violations) | Required Canonical Behavior | Enforcing Component |
| :--- | :--- | :--- | :--- |
| **No Microphone Detected** | Fake transcription strings (`"Jarvis, report system health"`). | Raise `AudioDeviceUnavailableError`; fall back to CLI push-to-talk. | `jarvis.voice.daemon` |
| **TTS Synthesis Failure** | Synthesize 440 Hz mathematical sine wave beep. | Fall back to Windows SAPI; if SAPI unavailable, emit honest text alert. | `jarvis.voice.tts` |
| **Disconnected Tool / Connector** | Return mock success payload (e.g. mock PDF resume). | Return explicit `TrustResult.failure` detailing missing credentials or network. | `jarvis.core.evidence` |
| **Fourth Law Reflection Missing** | Mark task `COMPLETED` based solely on exit code 0. | Mark task `INCOMPLETE` with `fourth_law_compliant=False`. | `jarvis.brain.nodes.reflect` |
| **LLM Inference Failure / Offline** | Return hardcoded mock text (e.g. "Your preferred stack is FastAPI"). | Execute strict failover order: Tier 1 Ollama -> Tier 2 Ollama -> Tier 3 FreeLLMAPI (DLP sanitized) -> Tier 0 OS Bypass. If all offline, emit honest failure receipt. | `jarvis.core.model_router` |
| **Circular DAG Dependency** | Infinite execution loop; stack overflow. | Kahn's algorithm detects cycle; aborts DAG before executing any node. | `jarvis.brain.planner` |
| **DLP Credential Detection** | Transmit unredacted API key or password to LLM. | Presidio / Regex masks secret with `[REDACTED_SECRET]`; logs security alert. | `jarvis.security.ten_layer_shield` |
| **Autonomous Git Push to Main** | Merge improvement branch directly into `main`. | Raise `SecurityViolationError`; enforce isolated feature branch and human PR. | `jarvis.workflows.pr_workflow` |
| **VRAM Exceeds 3.8 GB Threshold** | Crash GPU driver or trigger WDDM PCIe spillover (110x slowdown). | Throttle concurrency; keep active GPU VRAM <= 3.8 GB; route heavy reasoning to Ollama or DLP Tier 3. | `jarvis.agents.lifecycle` |

---

## 11. Implementation Readiness & Transition Strategy

The canonical architecture defined in this document provides the singular, authoritative blueprint for Project JARVIS. By eliminating structural dualism, collapsing root shadow folders, replacing simulated swarms with verifiable dynamic workers, unifying memory in SQLite WAL, and honoring the 6 GB VRAM hardware boundary, Project JARVIS fulfills its constitutional destiny:

**A private, local-first Personal AI Operating System that independently wakes when Ganesh says "Hey Jarvis", listens to instructions, executes real desktop tasks, verifies outcomes, and persists learned reflections into permanent memory.**
