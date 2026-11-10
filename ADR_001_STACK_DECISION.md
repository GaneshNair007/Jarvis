# Architecture Decision Record (ADR) 001: Core Technology Stack & Controller Architecture

- **Status**: Accepted
- **Date**: 2026-10-29
- **Decision Makers**: Principal Architect, Security Engineer, DevOps/SRE Lead
- **Scope**: Controller, Memory Store, Tool Gateway, Desktop Worker, Browser Runtime

---

## 1. Context & Problem Statement
JARVIS is designed as a private, single-user, local-first Personal AI Operating System. The system must operate reliably 24/7, control real desktop applications, execute browser automation, remember multi-session context with strict provenance, protect credentials via deterministic policy gates, and provide full-duplex voice interaction.

A critical design challenge is whether to adopt a heavy monolithic third-party agent framework (such as unconstrained OpenClaw, AutoGPT, or CrewAI) or construct a thin, custom, modular controller with standard interfaces.

---

## 2. Decision: Thin Custom Controller with Pluggable Worker Topology

We decided to build a **thin, custom, deterministic controller** using **Python 3.12 + FastAPI + SQLite (WAL mode)**, exposing standardized tool interfaces (Model Context Protocol - MCP) and strict deterministic policy boundaries.

### Stack Breakdown

| Component | Technology | Rationale | Alternatives Evaluated |
| :--- | :--- | :--- | :--- |
| **API Gateway / Controller** | **Python 3.12 / FastAPI / Uvicorn / WebSockets** | Native asynchronous concurrency, high throughput, typed Pydantic models, rapid integration with AI/ML tooling. | Node.js/Express (less native AI library support), Go (slower AI iteration). |
| **Database & Memory Store** | **SQLite with WAL mode (Write-Ahead Logging)** | Zero external operational overhead, local-first persistence, sub-millisecond read latency, single-user isolation. Upgradable to PostgreSQL when multi-node sync is introduced. | PostgreSQL (operational overhead for single-user MVP), MongoDB (loose schema guarantees). |
| **Tool Layer** | **Model Context Protocol (MCP)** | Open standard reference servers for Filesystem, Git, Fetch, Time, Memory. Tool isolation behind a deterministic policy gate. | Direct arbitrary Python execution (high risk of prompt injection and credential leaks). |
| **Desktop Worker** | **Python `pywin32` / Windows UI Automation + PyAutoGUI fallback** | Accessibility tree navigation provides deterministic element targeting; coordinate mouse/keyboard is isolated as a secondary fallback with physical failsafes. | Pure coordinate PyAutoGUI (fragile to resolution/DPI scaling), AppleScript (macOS only). |
| **Browser Worker** | **Playwright (Python sync/async)** | DOM locators (`get_by_role`, `get_by_label`), isolated browser contexts (`research_context` vs `private_context`), deterministic screenshot verification. | Selenium (slower, fragile DOM locators), Puppeteer (Node.js only). |
| **Speech Pipeline** | **Local Faster-Whisper + Windows SAPI / Piper TTS + openWakeWord** | Zero-latency local wake-word, zero audio transmission to cloud before activation, genuine audio streaming. | Cloud Speech APIs (privacy violation, recurring cost, internet dependency). |
| **Frontend HUD & Mobile Companion** | **Vanilla HTML5 / Modern CSS / Vanilla JavaScript + WebSockets** | Zero build step, instant hot-reloading, ultra-lightweight footprint, glassmorphic Iron-Man dark aesthetic. | React/Next.js (heavy build pipeline and excessive node_modules bloat for single-user local dashboard). |

---

## 3. Trust Boundary Architecture

```text
[ UNTRUSTED ZONE: External Internet / Web Pages / Incoming Emails / Raw OCR Text ]
                                 │
                                 ▼ (Treated purely as passive data, never instructions)
┌─────────────────────────────────────────────────────────────────────────────────┐
│ ZONE 1: CORE CONTROLLER (Always-On Engine)                                      │
│  - FastAPI Gateway & WebSocket Event Stream                                     │
│  - Deterministic Policy Gate (Deny-by-Default, Levels 0-5)                     │
│  - Privacy Gate (DLP Regex/Entropy Secret Redaction)                            │
│  - Cost Governor ($0.50 Task, $5.00 Day, $50.00 Month Circuit Breakers)         │
│  - SHA-256 Chained Append-Only Audit Ledger                                     │
│  - 5-Layer Cognitive Memory (Raw, Semantic, Episodic, Working, Directive)      │
└───────────────────────┬─────────────────────────────────┬───────────────────────┘
                        │                                 │
                        ▼                                 ▼
┌───────────────────────────────────────┐ ┌───────────────────────────────────────┐
│ ZONE 2: DESKTOP WORKER (Paired Laptop)│ │ ZONE 3: ISOLATED BROWSER CONTEXTS     │
│  - Windows UI Automation / PyAutoGUI  │ │  - Playwright Research (Ephemeral)    │
│  - Physical Mouse-Corner Failsafe     │ │  - Playwright Private (Authorized)    │
│  - User Typing Preemption             │ │  - DOM Locators + Screenshot Verifier │
└───────────────────────────────────────┘ └───────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ ZONE 4: CRYPTOGRAPHIC MEMORY VAULT & ARTIFACT REPOSITORY                        │
│  - Encrypted SQLite WAL (`data/jarvis.db`)                                      │
│  - Checksummed Artifacts (`data/artifacts/`) with SHA-256 Receipts             │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Consequences & Trade-offs
- **Positive**:
  - Deterministic security: No language model can bypass the policy gate or self-approve actions.
  - Zero cloud leakage: Secrets, credentials, and private files remain local.
  - Resilience: System survives reboots and network disconnections without losing task state.
- **Negative / Mitigations**:
  - SQLite concurrency is limited to one writer at a time. *Mitigation*: WAL mode enabled, write transactions are kept under 5ms.
  - Windows SAPI audio quality varies across OS editions. *Mitigation*: Piper neural TTS adapter is configured as a pluggable alternative.
