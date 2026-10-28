# JARVIS Test Plan & Verification Matrix

All capabilities, safety invariants, and APIs are validated against an automated `pytest` suite ensuring 100% deterministic test passes.

---

## 1. Test Architecture

The test suite covers both unit logic and end-to-end FastAPI client integrations across:
1. `tests/test_milestone1_core.py`: Milestone 1 Core Bootstrap Acceptance Suite
2. `tests/test_memory_vault.py`: 7-Layer Cognitive Memory, Directives, Document RAG, and Page Citations
3. `tests/test_model_router.py`: 3-Tier Model Router, DLP Redaction, Circuit Breakers, and LiteLLM Routing
4. `tests/test_policy_gate.py`: Deny-by-default, HMAC-SHA256 Token Expiry, and Kill Switch
5. `tests/test_tasks_and_litellm.py`: Task Engine Lifecycle, State Machine, and Logs
6. `tests/test_voice.py`: Full-Duplex Voice, Wake Word, Barge-In, Push-to-Talk, SAPI WAV Synthesis
7. `tests/test_desktop.py`: See-Act-Verify Desktop Automation, App Whitelisting, and Safety Buffer
8. `tests/test_browser.py`: Safe Playwright Worker, SSRF Protection, Prompt Injection Containment, Multi-Source Synthesis
9. `tests/test_dashboard.py`: Interactive Glassmorphic HUD, Telemetry Stream, and REST Endpoints

---

## 2. Milestone 1 Core Verification Matrix (12 Mandatory Tests)

| Test ID | Test Target | Verification Criteria | Status |
| :--- | :--- | :--- | :--- |
| `01` | Health Endpoint | `GET /health` returns status `healthy` and service name | **PASSED** |
| `02` | Chat Endpoint | `POST /chat` executes LangGraph StateGraph pipeline | **PASSED** |
| `03` | Memory Retrieval | Mem0 retrieves prior facts scoped to `user_id` | **PASSED** |
| `04` | Memory Update | Mem0 persists conversational turn to durable storage | **PASSED** |
| `05` | Policy Denial | Policy halts Tier 2 / Tier 3 actions lacking authorization | **PASSED** |
| `06` | Model Routing | LiteLLM routes local/private tasks to Ollama, complex to cloud | **PASSED** |
| `07` | Local Model Fallback | Offline / unreachable endpoints fall back gracefully | **PASSED** |
| `08` | Task Creation | `POST /tasks` triages and persists initial task state | **PASSED** |
| `09` | Task Cancellation | `POST /tasks/{id}/cancel` cleanly transitions task state | **PASSED** |
| `10` | Power Registry | `GET /powers` loads initial powers; enable/disable toggles | **PASSED** |
| `11` | Audit Logging | Cryptographic SHA-256 chained audit ledger records requests | **PASSED** |
| `12` | Kill Switch | `POST /kill-switch` halts active tasks and blocks execution | **PASSED** |

---

## 3. Execution Command

```bash
# Run Milestone 1 Suite
pytest tests/test_milestone1_core.py -v

# Run Complete Repository Suite
pytest -v
```
