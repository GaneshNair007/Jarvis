---
name: jarvis-architecture
description: Preserves JARVIS modular architectural boundaries, orchestrator patterns, and multi-tier state machine flow. Use when designing, modifying, or refactoring core system components, adding new layers, or extending orchestrator routing.
---

# JARVIS Architecture Guidelines

## Overview
JARVIS is a local-first, screen-first, privacy-guarded Personal AI Operating System.
All system modifications must preserve strict architectural boundaries and adhere to the single-orchestrator model.

## Core Architectural Invariants
1. **Single Orchestrator Authority**:
   - The primary entry point for user intent execution is `JarvisOrchestrator` in `jarvis/core/orchestrator.py`.
   - Never introduce an competing second orchestrator.
   - Deterministic instant slash commands execute via `_execute_instant_command()` without cloud LLM inference.
2. **State & Pipeline Machine**:
   - Complex workflows execute as a state graph (`jarvis/graph/jarvis_graph.py` and `jarvis/core/state_machine.py`).
   - Transitions must respect atomic task statuses: `NEW` -> `ROUTED` -> `EXECUTING` -> `AWAITING_APPROVAL` -> `COMPLETED` / `FAILED` / `CANCELLED`.
3. **Data Isolation & Local-First Invariants**:
   - User profile data (`data/profile.yml`, `data/cv.md`) and sqlite database (`data/jarvis_search.db`, `data/jarvis.db`) must remain strictly local.
   - Transcripts, memory embeddings, and audit ledgers must never be transmitted to external cloud providers without explicit approval.
4. **Subsystem Separation**:
   - `jarvis/core`: System governance, policy, audit, routing.
   - `jarvis/career`: ATS scanning, tailored resumes, STAR interview prep.
   - `jarvis/agents`: Multi-agent swarm coordination (`AgentSwarmCoordinator`).
   - `jarvis/powers`: Executable tool implementations (PWR-001 through PWR-355).
   - `search`: Sub-5ms hybrid local search (SQLite FTS5 + Qdrant + SearXNG).
   - `dashboard`: Glassmorphic single-page frontend.

## Verification
Whenever modifying architectural components:
1. Verify system startup and routes: `python -m pytest tests/test_milestone1_core.py tests/test_api.py -v`
2. Verify orchestrator intent routing: `python -m pytest tests/test_orchestrator.py -v`

