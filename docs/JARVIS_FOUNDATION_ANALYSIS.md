# Jarvis.foundation Product Architecture Analysis & Open-Source Clone Blueprint

- **Product Reference**: [https://jarvis.foundation/](https://jarvis.foundation/)
- **Target System**: Private, Single-User JARVIS Personal AI Operating System
- **Architectural Principle**: Rebuild the functional product contract using auditable, self-hostable open-source components with zero closed-source dependency or proprietary lock-in.

---

## 1. Core Product Contract

The Jarvis.foundation product model translates plain-language goals into verifiable computer work:

```text
[ Plain-Language Request ]
            │
            ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. UNDERSTAND: Natural-language intent extraction           │
│ 2. REMEMBER: Retrieve user preferences & historical context │
│ 3. PLAN: Decompose goal into a DAG of execution steps       │
│ 4. SELECT: Allocate specialized agents and MCP tools        │
│ 5. GATE: Deterministic policy evaluation & human approvals  │
│ 6. EXECUTE: Safe browser, desktop, coding, or IT operation  │
│ 7. VERIFY: Confirm objective outcome with visual/text proof │
│ 8. LOG: Append immutable SHA-256 audit entry                │
│ 9. ARTIFACT: Persist report, diff, receipt, or file         │
│ 10. REPORT: Explain exact results with citations            │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Capability Mapping: Closed Reference vs. Open-Source Rebuild

| Jarvis.foundation Capability | Open-Source / Self-Hostable Engine | JARVIS Implementation Module |
| :--- | :--- | :--- |
| **Natural-Language Task Engine** | FastAPI Async Engine + Pydantic | [jarvis/core/state_machine.py](file:///C:/Users/Ganesh%20Nair/.gemini/antigravity-ide/scratch/jarvis/jarvis/core/state_machine.py) |
| **Agent & Tool Selector** | Central Power Registry (MCP-compliant) | [jarvis/core/power_registry.py](file:///C:/Users/Ganesh%20Nair/.gemini/antigravity-ide/scratch/jarvis/jarvis/core/power_registry.py) |
| **Workflow Planner** | DAG Step Decomposer + State Machine | [jarvis/core/orchestrator.py](file:///C:/Users/Ganesh%20Nair/.gemini/antigravity-ide/scratch/jarvis/jarvis/core/orchestrator.py) |
| **Model Router / Multi-LLM** | **LiteLLM** (Unified Gateway) | [jarvis/core/model_router.py](file:///C:/Users/Ganesh%20Nair/.gemini/antigravity-ide/scratch/jarvis/jarvis/core/model_router.py) (LiteLLM-backed) |
| **Pay-As-You-Go Cost Governor** | Token & Dollar Tracker + Circuit Breakers | [jarvis/core/cost_governor.py](file:///C:/Users/Ganesh%20Nair/.gemini/antigravity-ide/scratch/jarvis/jarvis/core/cost_governor.py) |
| **Browser Automation** | Playwright (Sync/Async) & Browser Use | [jarvis/browser/](file:///C:/Users/Ganesh%20Nair/.gemini/antigravity-ide/scratch/jarvis/jarvis/browser/) (`context_manager`, `url_reader`, `evidence`) |
| **Desktop Computer Use** | Windows UI Automation + PyAutoGUI fallback | `jarvis/desktop/desktop_worker.py` (See-Act-Verify loop) |
| **Private Memory Vault** | 5-Layer SQLite WAL + Local Embeddings | [jarvis/memory/layers.py](file:///C:/Users/Ganesh%20Nair/.gemini/antigravity-ide/scratch/jarvis/jarvis/memory/layers.py) (`store.py`) |
| **Document Intelligence / RAG** | LlamaIndex / Local Semantic Chunking | `jarvis/memory/document_rag.py` (PDF Q&A with page citations) |
| **Conversational Voice Engine** | openWakeWord + faster-whisper + SAPI/Piper | [jarvis/voice/](file:///C:/Users/Ganesh%20Nair/.gemini/antigravity-ide/scratch/jarvis/jarvis/voice/) (`wake`, `stt`, `tts`, `pipeline`) |
| **Deep Research Engine** | Ephemeral Browser + Citation Harvester | [jarvis/browser/research_worker.py](file:///C:/Users/Ganesh%20Nair/.gemini/antigravity-ide/scratch/jarvis/jarvis/browser/research_worker.py) |
| **IT & Developer Powers** | psutil + Git CLI + Docker socket | [jarvis/powers/it_admin_powers.py](file:///C:/Users/Ganesh%20Nair/.gemini/antigravity-ide/scratch/jarvis/jarvis/powers/it_admin_powers.py) |
| **Approval Gate & Policy** | Deny-by-default Policy Gate + HMAC-SHA256 | [jarvis/core/policy_gate.py](file:///C:/Users/Ganesh%20Nair/.gemini/antigravity-ide/scratch/jarvis/jarvis/core/policy_gate.py) |
| **Audit Ledger** | SHA-256 Chained Append-Only Log | [jarvis/core/audit.py](file:///C:/Users/Ganesh%20Nair/.gemini/antigravity-ide/scratch/jarvis/jarvis/core/audit.py) |
| **Mission-Control HUD** | Vanilla Glassmorphic WebSockets Dashboard | [jarvis/dashboard/index.html](file:///C:/Users/Ganesh%20Nair/.gemini/antigravity-ide/scratch/jarvis/jarvis/dashboard/index.html) |

---

## 3. Product Contract Invariants

1. **Evidence-First Guarantee**: No task is marked complete without a verifiable artifact (saved file, URL confirmation, diff, screenshot checksum, or test exit code).
2. **Deterministic Security Boundary**: AI prompts can propose plans; only deterministic code in the `PolicyGate` can evaluate permissions and dispatch tool executions.
3. **At-Most-Once Irreversible Actions**: High-privilege tasks (email transmission, financial operations, application submissions) are gated behind HMAC tokens bound to frozen content hashes and idempotency keys.
4. **Data Isolation**: Untrusted inputs (web pages, PDFs, incoming emails) are encoded as passive JSON strings and sanitized against prompt injections.
