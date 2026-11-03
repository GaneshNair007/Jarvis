---
description: "Universal Architectural Invariants for Project JARVIS: First Law Evidence, Zero Simulation, Hardened Policy Gates, and Event-Loop Concurrency."
globs: ["**/*.py"]
always_on: true
---

# JARVIS Core Architectural Invariants

All agents and contributors must uphold these four non-negotiable architectural laws:

### 1. The First Law of JARVIS ("No Evidence, No Claim")
- JARVIS must never report an action occurred without verifiable evidence.
- Every external capability (Gmail, Browser, GitHub, Scheduler, File Operations, Integrations) must return a `TrustResult` containing concrete `Evidence` objects with real sources, timestamps, and verifiable checksums.
- When an integration is disconnected or credentials are missing, return an honest failure state (`TrustResult.disconnected(...)`) with empty payloads. Never fabricate responses or return simulated mock dictionaries.

### 2. Zero Simulation Invariant
- Under no circumstances shall an agent use `await asyncio.sleep(...)` or static mock returns to simulate task progress.
- Tasks must execute real tools via `power_registry`, invoke live inference via `model_router`, or explicitly return an honest failure.
- Any pull request or modification introducing sleep stubs in execution handlers is considered a critical security and integrity violation.

### 3. Cryptographic Approval Gate Invariants
- High-privilege and destructive actions (Tier 2/3) require explicit human approval via `policy_gate`.
- **Zero Token Leakage**: Pending approval payloads returned to unauthenticated clients must never include secret HMAC approval tokens.
- **Single-Use Replay Prevention**: Tokens must be consumed and revoked immediately upon execution. Replay attempts must fail closed.
- **Fail-Closed Resolution**: Resolving approvals via API requires administrative bearer token authentication (`verify_admin_user`).

### 4. Event-Loop Concurrency Guardrail (P0 Runtime Invariant)
- Never call synchronous, blocking network I/O or heavy model inference inside `async def` FastAPI routes or event-loop callbacks.
- All synchronous inference calls (LiteLLM, urllib, subprocesses) must be offloaded to worker threads via `await asyncio.to_thread(...)` or handled by native asynchronous clients (`httpx.AsyncClient`).
- The event loop must remain free to process WebSockets, voice barge-in, and HUD streaming at all times.
