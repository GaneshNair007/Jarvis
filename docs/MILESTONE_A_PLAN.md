# Milestone A Plan & Verification Gate: Brain, Tasks & Foundation

- **Milestone**: Milestone A - Brain, Tasks, Foundation
- **Target System**: JARVIS Personal AI Operating System (Private Single-User)
- **Status**: IMPLEMENTED & TESTED (37/37 Automated Tests Passing)
- **Pass/Fail Gate**: Assistant replies, manages tasks, restarts without state loss, records tamper-evident audit logs, and reports honest status.

---

## 1. Scope & Deliverables

1. **Repository Scaffold & Configuration System**:
   - `jarvis/config.py`: Typed Pydantic BaseSettings loading environment configurations (`.env`), LLM endpoints, cost caps, and storage directories.
   - Zero hardcoded credentials or third-party cloud lock-in.

2. **Deterministic Security & Governance Subsystem**:
   - `jarvis/core/policy_gate.py`: Deny-by-default execution policy across Tiers 0 to 5.
   - Ephemeral HMAC-SHA256 human approval tokens bound to action payloads and frozen content hashes.
   - Emergency Kill Switch (`kill_switch_active`) with instantaneous halting.
   - `jarvis/core/privacy_gate.py`: Data Loss Prevention (DLP) regex and entropy scanner redacting passwords, API keys (`sk-...`, GitHub, AWS), and PII.
   - `jarvis/core/cost_governor.py`: $0.50 task, $5.00 daily, and $50.00 monthly spending limits with circuit breakers.

3. **Cryptographic Audit Ledger**:
   - `jarvis/core/audit.py`: Append-only, SHA-256 chained transaction log.
   - Every entry is cryptographically linked: `entry_hash = SHA-256(payload + previous_hash)`.
   - Full chain verification method (`verify_integrity()`) detecting any post-hoc log tampering.

4. **Task Lifecycle & Finite State Machine (FSM)**:
   - `jarvis/core/state_machine.py`: 8-state deterministic task lifecycle:
     `NEW -> TRIAGED -> POLICY_CHECK -> QUEUED -> RUNNING -> VERIFYING -> COMPLETED`.
   - Error classification: `TRANSIENT_NETWORK`, `SESSION_EXPIRED`, `CAPTCHA_USER_NEEDED`, `POLICY_DENIED`, `AI_USAGE_LIMIT`, `TARGET_CHANGED`, `INSUFFICIENT_EVIDENCE`, `PERMANENT_FAILURE`.

5. **Central Power Registry**:
   - `jarvis/core/power_registry.py` & `data/powers_catalog.json`: Registry tracking all 355 powers across 22 categories in the 31-field template.
   - Powers can be dynamically enabled, disabled, queried, and verified without modifying core orchestration logic.

6. **Central Orchestrator & Multi-Tier Model Router**:
   - `jarvis/core/orchestrator.py`: Master coordinator receiving natural language or structured requests, interpreting intent, applying the policy gate, dispatching execution, and persisting memory.
   - `jarvis/core/model_router.py`: 3-tier hybrid routing:
     - *Deterministic OS Bypass (~1ms)*: Instant telemetry, lock screen, clipboard without LLM tokens.
     - *Tier 1 Local Reflex*: Ollama `llama3.2:3b` for fast summarization and parsing.
     - *Tier 2 Private GPU Reasoning*: vLLM deep-reasoning on LAN.
     - *Tier 3 Frontier Cloud*: Claude 3.7 / GPT-4o / Gemini 2.0 Pro gated strictly behind DLP redaction and cost governor approval.

7. **5-Layer Cognitive Memory Store**:
   - `jarvis/memory/store.py` & `jarvis/memory/layers.py`: SQLite WAL-mode database (`data/jarvis.db`) managing:
     - `RAW`: Timestamped verbatim interaction transcripts.
     - `SEMANTIC`: Verified user facts and explicit preferences.
     - `EPISODIC`: Structured summaries of historical tasks and outcomes.
     - `WORKING`: Active task scratchpad and immediate context.
     - `DIRECTIVE`: System invariants and operational rules.

8. **Conversational Voice Pipeline**:
   - `jarvis/voice/wake.py`: Local keyword detection ("Hey Jarvis") and Push-to-Talk activation (`PWR-001`, `PWR-002`).
   - `jarvis/voice/stt.py`: Speech-to-text with faster-whisper adapter (`PWR-003`).
   - `jarvis/voice/tts.py`: Speech synthesis using Windows SAPI (`SpVoice` & `SpFileStream` for WAV bytes) with barge-in cancellation (`PWR-004`).
   - `jarvis/voice/pipeline.py`: Full-duplex conversational turn coordinator (`PWR-005`).

9. **FastAPI Server, WebSocket Stream & Iron-Man Glassmorphic HUD**:
   - `jarvis/api/server.py` & `jarvis/api/routes_voice.py`: REST and WebSocket API endpoints.
   - `jarvis/dashboard/index.html`: Iron-Man dark-mode HUD served at `/` and `/dashboard` with live CPU/RAM telemetry, active powers counter, voice turn controls, and audit verification.

---

## 2. Verification Test Evidence

All 37 unit and integration tests execute and pass:
```text
tests/test_api.py::test_api_model_status PASSED                          [  2%]
tests/test_api.py::test_api_model_route_bypass PASSED                    [  5%]
tests/test_api.py::test_api_model_route_sensitive PASSED                 [  8%]
tests/test_api.py::test_api_system_health PASSED                         [ 10%]
tests/test_api.py::test_api_chat PASSED                                  [ 13%]
tests/test_api.py::test_api_powers PASSED                                [ 16%]
tests/test_api.py::test_api_audit PASSED                                 [ 18%]
tests/test_api.py::test_api_kill_switch PASSED                           [ 21%]
tests/test_audit.py::test_audit_logging_and_chain_integrity PASSED       [ 24%]
tests/test_dashboard.py::test_serve_dashboard_root PASSED                [ 27%]
tests/test_dashboard.py::test_serve_dashboard_explicit_route PASSED      [ 29%]
tests/test_dashboard.py::test_voice_push_to_talk_api PASSED              [ 32%]
tests/test_dashboard.py::test_voice_barge_in_api PASSED                  [ 35%]
tests/test_dashboard.py::test_voice_synthesize_api PASSED                [ 37%]
tests/test_model_router.py::test_instant_command_bypasses_llm PASSED     [ 40%]
tests/test_model_router.py::test_private_document_stays_local PASSED     [ 43%]
tests/test_model_router.py::test_screen_understanding_stays_local PASSED [ 45%]
tests/test_model_router.py::test_sensitive_data_redacted_before_routing PASSED [ 48%]
tests/test_model_router.py::test_cost_limit_stops_expensive_call PASSED  [ 51%]
tests/test_model_router.py::test_provider_failure_trips_circuit_breaker PASSED [ 54%]
tests/test_model_router.py::test_audit_trail_recorded PASSED             [ 56%]
tests/test_orchestrator.py::test_orchestrator_instant_command PASSED     [ 59%]
tests/test_orchestrator.py::test_orchestrator_chat_query PASSED          [ 62%]
tests/test_orchestrator.py::test_five_layer_memory PASSED                [ 64%]
tests/test_policy_gate.py::test_deny_by_default_on_dangerous_powers PASSED [ 67%]
tests/test_policy_gate.py::test_approval_token_verification_and_expiry PASSED [ 70%]
tests/test_policy_gate.py::test_emergency_kill_switch_blocks_execution PASSED [ 72%]
tests/test_power_registry.py::test_powers_catalog_loaded PASSED          [ 75%]
tests/test_power_registry.py::test_search_powers PASSED                  [ 78%]
tests/test_privacy_gate.py::test_secret_redaction_patterns PASSED        [ 81%]
tests/test_privacy_gate.py::test_context_minimization PASSED             [ 83%]
tests/test_voice.py::test_wake_word_phrase_detection PASSED              [ 86%]
tests/test_voice.py::test_push_to_talk_activation PASSED                 [ 89%]
tests/test_voice.py::test_tts_synthesis_to_wav PASSED                    [ 91%]
tests/test_voice.py::test_barge_in_cancellation PASSED                   [ 94%]
tests/test_voice.py::test_stt_transcription_pipeline PASSED              [ 97%]
tests/test_voice.py::test_full_duplex_conversational_turn PASSED         [100%]
======================== 37 passed in 3.68s ========================
```

---

## 3. Milestone A Pass/Fail Gate Verification Checklist

| Gate Requirement | Status | Verification Evidence |
| :--- | :--- | :--- |
| **Assistant replies to text & voice** | PASS | `tests/test_orchestrator.py` & `tests/test_voice.py` |
| **Keeps tasks & state across restarts** | PASS | SQLite WAL database (`data/jarvis.db`) persists tasks & memory |
| **Restarts without state loss** | PASS | Tested in `test_five_layer_memory` |
| **Reports honest telemetry status** | PASS | `python -m jarvis.main health` returns real CPU/RAM/Disk stats |
| **Deny-by-default on dangerous powers** | PASS | `tests/test_policy_gate.py` rejects unapproved Level 3-5 actions |
| **Tamper-evident audit trail** | PASS | `tests/test_audit.py` validates SHA-256 chain integrity |
| **Kill switch halts execution** | PASS | `tests/test_policy_gate.py` verifies zero execution when engaged |

---

## 4. Next Step
Upon user review and sign-off, proceed to **Milestone B: Safe Browser (Read-Only) Worker** (`PWR-063` through `PWR-067`) implementing Playwright DOM locators, isolated research context, URL reader, screenshot evidence capture, and citation tracking.
