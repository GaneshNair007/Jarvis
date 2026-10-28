# JARVIS System Architecture

## Overview
JARVIS (Just A Rather Very Intelligent System) is a local-first, screen-first, voice-driven, proactive AI operating system. It bridges conversational intelligence with real physical computer agency through a deterministic safety gate.

## System Topology
```text
           [ Voice Stream / Web UI / Mobile Companion / HUD ]
                                   │
                                   ▼
                   ┌───────────────────────────────┐
                   │      JARVIS Orchestrator      │
                   └───────┬───────────────┬───────┘
                           │               │
            ┌──────────────┴────┐     ┌────┴───────────────┐
            │ Persistent Memory │     │  MCP Tool Gateway  │
            │  (SQLite/Vector)  │     │ (Files, Git, Web)  │
            └───────────────────┘     └────┬───────────────┘
                                           │
                           ┌───────────────┴───────────────┐
                           │   Deterministic Policy Gate   │
                           │   (Approvals, Hash Check,     │
                           │    Kill Switch, Audit Log)    │
                           └───────────────┬───────────────┘
                                           │
            ┌────────────────┬─────────────┴──┬──────────────┐
            ▼                ▼                ▼              ▼
     [Desktop Worker] [Browser Worker] [Server Worker] [Agent Pool]
```

## Core Modules
1. **Model Router (`jarvis/core/model_router.py`)**: 3-tier hybrid routing engine (Tier 1 Local Reflex, Tier 2 Private GPU vLLM, Tier 3 Frontier Cloud, and Deterministic Bypass).
2. **Policy Gate (`jarvis/core/policy_gate.py`)**: Deny-by-default deterministic authorization with HMAC-SHA256 approval tokens and physical/software kill switch.
3. **Privacy Gate (`jarvis/core/privacy_gate.py`)**: Data Loss Prevention (DLP) scanning regex and entropy patterns to redact credentials, tokens, and PII.
4. **Cost Governor (`jarvis/core/cost_governor.py`)**: Strict budget caps (per-task, daily, monthly) with per-provider circuit breakers.
5. **Audit Ledger (`jarvis/core/audit.py`)**: SHA-256 chained append-only audit trail for tamper-evident receipts.
6. **Power Registry (`jarvis/core/power_registry.py`)**: Dynamic catalog of 355 capabilities indexed by domain.
7. **Persistent Memory (`jarvis/memory/layers.py`)**: 5-layer cognitive persistence (Raw, Semantic, Episodic, Working, Directive) in SQLite WAL.
