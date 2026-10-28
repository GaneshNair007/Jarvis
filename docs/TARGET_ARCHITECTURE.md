# JARVIS Target Architecture: Iron Man-Grade Personal AI Operating System

- **Classification**: Single-User, Local-First, Screen-First, Voice-Driven
- **Target Deliverable**: Complete 12-System Architecture Blueprint

---

## 1. System Topology & Trust Boundaries

```text
[ UNTRUSTED ZONE: External Internet, Web Pages, Incoming Emails, OCR Scans ]
                                     │
                                     ▼ (Strictly passive untrusted data)
┌──────────────────────────────────────────────────────────────────────────────┐
│ ZONE 1: CENTRAL CONTROLLER & DETERMINISTIC GOVERNANCE ENGINE                 │
│                                                                              │
│   [ Client Interfaces: Voice Stream, Push-to-Talk, WebSocket HUD, CLI ]      │
│                                    │                                         │
│                                    ▼                                         │
│                    ┌───────────────────────────────┐                         │
│                    │     Master Orchestrator       │                         │
│                    │    (DAG Task Decomposition)   │                         │
│                    └───────┬───────────────┬───────┘                         │
│                            │               │                                 │
│             ┌──────────────┴────┐     ┌────┴───────────────┐                 │
│             │ 5-Layer Memory    │     │ Central Power      │                 │
│             │ Vault (SQLite)    │     │ Registry (355 Pwrs)│                 │
│             └───────────────────┘     └────┬───────────────┘                 │
│                                            │                                 │
│                            ┌───────────────┴───────────────┐                 │
│                            │   Deterministic Policy Gate   │                 │
│                            │   - Deny-by-Default (Tiers 0-5│                 │
│                            │   - Ephemeral HMAC-SHA256     │                 │
│                            │   - Emergency Kill Switch     │                 │
│                            └───────────────┬───────────────┘                 │
│                                            │                                 │
│                            ┌───────────────┴───────────────┐                 │
│                            │   LiteLLM Unified Model Router│                 │
│                            │   - Tier 0: OS Bypass (~1ms)  │                 │
│                            │   - Tier 1: Local Ollama Reflex│                │
│                            │   - Tier 2: Private GPU vLLM  │                 │
│                            │   - Tier 3: Frontier Cloud    │                 │
│                            │   - Cost Governor & Circuit Br│                 │
│                            └───────────────┬───────────────┘                 │
│                                            │                                 │
│                            ┌───────────────┴───────────────┐                 │
│                            │   Chained SHA-256 Audit Ledger│                 │
│                            │   (Append-Only Tamper Evident)│                 │
│                            └───────────────┬───────────────┘                 │
└────────────────────────────────────────────┼─────────────────────────────────┘
                                             │
                       ┌─────────────────────┼─────────────────────┐
                       ▼                     ▼                     ▼
┌─────────────────────────────┐ ┌─────────────────────────┐ ┌─────────────────────────┐
│ ZONE 2: DESKTOP WORKER      │ │ ZONE 3: BROWSER WORKER  │ │ ZONE 4: AGENT POOL      │
│ - OS UI Automation          │ │ - Playwright Research   │ │ - Coordinator           │
│ - Mouse/Keyboard Fallback   │ │ - DOM Accessibility Tree│ │ - Researcher / Coder    │
│ - Corner Failsafe & Overlay │ │ - SHA-256 Screenshots   │ │ - Reviewer / SysAdmin   │
└─────────────────────────────┘ └─────────────────────────┘ └─────────────────────────┘
```

---

## 2. The 12 Foundational Systems

1. **System 1: The Brain (Central Orchestrator & Task Engine)**:
   - Evaluates incoming language intents, consults memory, decomposes requests into dependency DAGs, dispatches actions, and monitors completion.
2. **System 2: The Router (LiteLLM-Backed Hybrid Model Router)**:
   - Unified OpenAI-compatible interface routing between OS bypass, local Ollama models (`llama3.2:3b`), private LAN vLLM servers, and cloud frontier models.
3. **System 3: The Gate (Deterministic Policy Gate & Safety Guard)**:
   - Privilege classification across Tiers 0 to 5. Irreversible actions require HMAC-SHA256 human approval tokens bound to frozen payload hashes.
4. **System 4: The Vault (5-Layer Cognitive Memory)**:
   - Multi-layer SQLite WAL database storing `RAW` chronological logs, `SEMANTIC` facts, `EPISODIC` summaries, `WORKING` scratchpads, and `DIRECTIVE` rules.
5. **System 5: The Ledger (Cryptographic Audit Subsystem)**:
   - Append-only chained transaction ledger where `entry_hash = SHA256(payload + previous_hash)`.
6. **System 6: The Voice (Full-Duplex Conversational Pipeline)**:
   - openWakeWord ("Hey Jarvis"), push-to-talk, faster-whisper STT, Windows SAPI / Piper neural TTS, and instant barge-in interruption.
7. **System 7: The Senses (Screen & Computer Awareness)**:
   - Multi-monitor screenshot capture, OCR text extraction, active window context detection, and automatic DLP visual masking.
8. **System 8: The Hands (See-Act-Verify Desktop Worker)**:
   - Windows UI Automation navigation, PyAutoGUI mouse/keyboard fallbacks, emergency mouse-corner abort, and user typing preemption.
9. **System 9: The Navigator (Safe Browser Automation Worker)**:
   - Ephemeral Playwright research context, DOM element selectors, SSRF private network isolation, screenshot checksum receipts, and prompt injection quarantine.
10. **System 10: The Researcher (Deep Research & Citation Engine)**:
    - Multi-hop web search, official documentation extraction, claim verification, and Markdown/PDF synthesis with cryptographic provenance.
11. **System 11: The Swarm (Multi-Agent Specialist Pool)**:
    - Independent subagents (Researcher, Coder, Reviewer, SysAdmin) executing isolated tasks concurrently with budget and timeout boundaries.
12. **System 12: The Interface (Mission-Control HUD & Telemetry Center)**:
    - Real-time dark-mode glassmorphic HUD served over WebSockets with live CPU/RAM telemetry, active powers counter, and audit trail verification.
