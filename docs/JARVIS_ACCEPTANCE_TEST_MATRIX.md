# JARVIS Personal AI Operating System: Acceptance Test Matrix & Verification Rubric

**Document Version:** 2.0.0  
**Date:** 2026-11-10  
**Status:** Approved Technical Blueprint  
**Target Environment:** Windows 11 (64-bit), 24 GB RAM, NVIDIA GeForce RTX 4050 Laptop GPU (6 GB VRAM)  
**Governing Documents:** `docs/constitution/JARVIS_MASTER_DIRECTIVE.md` (v1.2.0), `jarvis/constitution/*.yaml`, `ORIGINAL_REQUEST.md` (Corrective Priority Update)  
**Supersedes:** `docs/TEST_PLAN.md` (v1.0.0)

---

## 1. Executive Summary & Verification Philosophy

This Acceptance Test Matrix establishes the objective, verifiable, and empirical criteria required to validate Project JARVIS as a private, local-first Personal AI Operating System for **Ganesh Nair**. 

In strict adherence to the **First Law** (*"No Evidence = No Claim"*) and the **Second Law** (*"No Simulation = No Pretending"*), this document outlaws all synthetic pass rates, hardcoded test strings, fake sleep delays, and unverified wrapper claims. Every test scenario defined herein must produce a concrete, inspectable **Evidence Receipt**.

### 1.1 The Golden Standard: Independent Execution Outside Antigravity

A foundational integrity requirement of this system is:
> **The final measure of this project is whether Jarvis works independently when Antigravity is closed.**

Under no circumstances may a test result produced by a subagent inside Antigravity be accepted as proof of Jarvis runtime capability. Every acceptance test must execute through native Windows PowerShell (`pwsh`) or command prompt (`cmd.exe`) using the native Python runtime (`python -m ...` or `pytest`), interacting directly with physical hardware, the local operating system, and local inference engines.

---

## 2. Standard Specification of an "Evidence Receipt"

An **Evidence Receipt** is an immutable, machine-verifiable JSON artifact generated upon the completion of any tool invocation, task node, or test scenario. It captures ground-truth physical state, cryptographic hashes, and operating system telemetry.

### 2.1 Evidence Receipt Schema (`EvidenceReceipt`)

```json
{
  "$schema": "https://jarvis.internal/schemas/evidence_receipt.v2.json",
  "receipt_id": "urn:uuid:f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "timestamp_utc": "2026-11-10T12:00:00.000Z",
  "test_case_id": "TC-VOICE-05",
  "subsystem": "VOICE_DESKTOP",
  "execution_context": {
    "runner": "native_powershell",
    "antigravity_active": false,
    "os_version": "Microsoft Windows 11 Home 10.0.22631",
    "python_version": "3.11.8",
    "host_pid": 14208
  },
  "target_process": {
    "name": "notepad.exe",
    "pid": 18944,
    "hwnd": 65824,
    "path": "C:\\Windows\\System32\\notepad.exe",
    "command_line": "notepad.exe"
  },
  "stimulus": {
    "action": "desktop_open_notepad_and_type",
    "parameters": {
      "target_text": "Jarvis is awake",
      "verify_readback": true
    },
    "input_sha256": "8a3e7...b49f"
  },
  "observed_output": {
    "window_title": "*Untitled - Notepad",
    "readback_buffer": "Jarvis is awake",
    "buffer_length_chars": 15,
    "content_sha256": "4b5d8...e12a",
    "screenshot_path": "data/receipts/screenshots/notepad_verified_18944.png",
    "screenshot_sha256": "9f1c2...77a0"
  },
  "hardware_telemetry": {
    "gpu_vram_used_mb": 4210.5,
    "gpu_vram_total_mb": 6144.0,
    "gpu_utilization_pct": 14.0,
    "system_ram_used_mb": 11450.0,
    "execution_duration_ms": 782.4
  },
  "verification_method": {
    "type": "win32_wm_gettext",
    "assertion": "readback_buffer == parameters.target_text",
    "result": "MATCH"
  },
  "audit_chain": {
    "previous_entry_hash": "c78f1...90ab",
    "current_entry_hash": "e12d3...56ef"
  },
  "trust_status": "VERIFIED_SUCCESS"
}
```

### 2.2 Rejection Criteria for Receipts
A receipt is automatically marked `REJECTED_FABRICATION` and the corresponding test marked `FAIL` if:
1. `antigravity_active` is `true` during an independent runtime acceptance test.
2. `pid` does not correspond to an actual running OS process recorded in `EnumProcesses`.
3. `content_sha256` does not match the actual SHA-256 hash of the extracted file, text, or audio buffer.
4. `readback_buffer` contains canned fallback phrases (e.g., `"Understood. I will remember that"`, `"Mock ATS Resume"`, `"Jarvis, report system health"`).
5. `execution_duration_ms` is suspiciously instantaneous (< 1ms) for physical I/O operations requiring network or OS roundtrips.

---

## 3. Subsystem Test Matrices

### Subsystem 1: Voice Pipeline & Acoustic Wake (P0 Runtime Suite)

*Objective:* Validate physical microphone capture, acoustic wake detection, speech transcription, core dispatch, real Win32 Notepad automation, buffer readback verification, and neural TTS synthesis without mock fallbacks.

| Test Case ID | Test Scenario | Preconditions / Setup | Stimulus / Execution Command | Expected Output & Acceptance Criteria | Required Evidence Receipt | Verdict Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-VOICE-01** | Physical Windows Microphone Audio Capture | Physical mic connected; default Windows recording device enabled. | `python -m jarvis.voice.capture --probe-devices --record-test --duration 2.0 --out data/test_mic.wav` | Detects default input device; records 2.0s PCM audio at 16 kHz, 16-bit mono. Non-zero RMS amplitude (> 0.005). Valid RIFF header. | Device Name, Windows Device ID, WAV file path, file size in bytes, calculated RMS energy, SHA-256. | **PASS** if WAV is non-empty with real sound; **BLOCKED** if physical mic absent. |
| **TC-VOICE-02** | Acoustic Wake Word Latency & Sensitivity (`openWakeWord`) | TC-VOICE-01 passing; local ONNX wake weights in `jarvis/voice/models/`. | `python -m jarvis.voice.wake --test-live --threshold 0.5` (Speak "Hey Jarvis" into mic). | Wake detector triggers within < 500ms of utterance completion. Confidence score >= 0.5. Ambient speech/noise produces score < 0.2. | Trigger timestamp, audio chunk sequence number, confidence float, latency ms, model path. | **PASS** if wake triggers on "Hey Jarvis" and ignores background noise. |
| **TC-VOICE-03** | Local Speech Transcription Accuracy (`faster-whisper`) | `faster-whisper` installed on CUDA (compute_type=float16); `base.en` loaded. | `python -m jarvis.voice.stt --input-audio data/test_mic.wav` (Audio saying "Open Notepad and type Jarvis is awake"). | Transcribes utterance with Word Error Rate (WER) < 10%. Processing latency < 400ms on RTX 4050. Zero hardcoded mock fallback strings. | Audio duration sec, transcript text, word timestamps, inference latency ms, CUDA VRAM MB. | **PASS** if transcription matches audio; **FAIL** if canned string emitted. |
| **TC-VOICE-04** | Two-Stage Conversational State Machine | Mic stream active; conversation coordinator running. | Speak "Hey Jarvis", pause 1s, hear chime/voice "Yes, Ganesh?", speak command. | Transitions: `LISTENING_FOR_WAKE -> ACKNOWLEDGING (<250ms) -> CAPTURING_INTENT -> DISPATCHING`. Zero state deadlocks. | State transition logs with monotonic microsecond timestamps, audio event IDs. | **PASS** if acknowledgment triggers before accepting command. |
| **TC-VOICE-05** | Win32 Notepad Launch, Typing & Buffer Verification | Windows 11 desktop; no active Notepad instances. | `python -m jarvis.tools.desktop.notepad --text "Jarvis is awake" --verify` | Launches `notepad.exe`; captures PID; sets foreground focus; types "Jarvis is awake"; reads buffer via Win32 `WM_GETTEXT`; asserts exact match. | Target PID, HWND, extracted text buffer, `content_sha256`, window screenshot SHA-256. | **PASS** if readback buffer exactly matches "Jarvis is awake". |
| **TC-VOICE-06** | Local Neural TTS Spoken Confirmation (`kokoro-onnx` / SAPI) | Audio playback device active; Kokoro ONNX model loaded. | `python -m jarvis.voice.tts --text "I have opened Notepad and verified the text: Jarvis is awake." --play` | Synthesizes natural spoken English speech (24 kHz). Synthesis latency < 600ms. Zero 440 Hz mathematical sine-wave beeps. | Audio sample count, duration sec, synthesis latency ms, engine (`kokoro` or `sapi`). | **PASS** if spoken audio heard; **FAIL** if sine-wave beep played. |
| **TC-VOICE-07** | Full-Duplex Barge-In Interruption | TTS speaking a multi-sentence paragraph. | User speaks "Stop" or any word above VAD threshold during playback. | Audio playback halts immediately via `sounddevice.stop()` within < 100ms of user speech detection. | TTS start timestamp, interruption timestamp, delta latency ms, state change log. | **PASS** if audio playback ceases within 100ms of user utterance. |
| **TC-VOICE-08** | End-to-End P0 Voice Activation Verification | Full voice loop running outside Antigravity. | `python tests/manual/verify_p0_voice_notepad.py` (Say "Hey Jarvis... open Notepad and type Jarvis is awake"). | Wakes, acknowledges, transcribes, launches Notepad, types, verifies buffer, speaks confirmation. Complete receipt written to disk. | `data/receipts/p0_voice_verification.json` containing complete execution lifecycle receipts. | **PASS** if all stages succeed; **BLOCKED** if physical hardware unavailable. |

---

### Subsystem 2: Model Router & Local LLM Topology

*Objective:* Verify deterministic bypass, local Ollama execution within the 5.8 GB VRAM budget on RTX 4050, FreeLLMAPI router integration at `http://localhost:3001`, and zero secret egress.

| Test Case ID | Test Scenario | Preconditions / Setup | Stimulus / Execution Command | Expected Output & Acceptance Criteria | Required Evidence Receipt | Verdict Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-ROUTER-01** | Deterministic OS Bypass | Model router initialized. | Send system query: `"mute volume"` or `"what is the time"`. | Bypasses LLM inference completely (0 tokens consumed). Execution latency < 5ms. Returns direct OS execution receipt. | Router tier (`TIER_0_BYPASS`), token count (0), latency ms (<5ms), OS command executed. | **PASS** if routed to bypass with 0 LLM tokens consumed. |
| **TC-ROUTER-02** | Tier 1 Local Reflex Inference (Ollama 3B/4B) | Ollama running locally; `qwen2.5:3b` loaded in VRAM. | Send prompt: `"Summarize Kahn's algorithm in 20 words"`. | Model generates valid summary. Generation throughput > 25 tokens/sec. VRAM usage <= 3.2 GB. Response latency < 1.2s. | Model identifier (`qwen2.5:3b`), prompt tokens, completion tokens, tok/sec, VRAM MB. | **PASS** if generated locally on Ollama without external network calls. |
| **TC-ROUTER-03** | FreeLLMAPI Local Router Probe (`http://localhost:3001`) | FreeLLMAPI service running at `localhost:3001`. | `python -m jarvis.tools.adapters.freellmapi_adapter --health-check --test-inference` | Health endpoint returns 200 OK. Model catalogue listed. Test inference generates coherent completion. Latency recorded. | HTTP status (200), available model array, latency ms, response text, zero external secret egress. | **PASS** if router responds on port 3001; **BLOCKED** if service not running. |
| **TC-ROUTER-04** | RTX 4050 VRAM Budget Ceiling Enforcement | `pynvml` GPU monitor active; background voice active. | Trigger complex planning prompt requiring Tier 2 model. | Total active VRAM usage across all Jarvis processes strictly <= 5.8 GB. If 32B model requested, router rejects with `HardwareBudgetExceededError`. | NVML VRAM allocation log, process memory map, exception trace if budget exceeded. | **PASS** if peak VRAM <= 5.8 GB; **FAIL** if CUDA out-of-memory occurs. |
| **TC-ROUTER-05** | Offline Survival & Network Disconnection | Disconnect physical network adapter (disable Wi-Fi / Ethernet). | Send command: `"Hey Jarvis, list files in scratch folder"`. | System functions 100% offline. Voice, Ollama reflex, and OS tools execute without errors. Zero crashes or unhandled socket timeouts. | Network interface status (DOWN), local model execution receipt, tool output. | **PASS** if full execution succeeds while network is offline. |
| **TC-ROUTER-06** | Provider Circuit Breaker Resilience | Mock cloud provider throwing HTTP 500 or timeout. | Dispatch 3 consecutive requests to failing cloud provider. | After 3rd failure, circuit breaker trips to `OPEN` state for 60 seconds. Subsequent calls automatically reroute to local Tier 1/2 models. | Circuit breaker state (`OPEN`), trip timestamp, consecutive failure count (3), fallback tier. | **PASS** if circuit trips and fails over to local models. |

---

### Subsystem 3: Memory Persistence & Database Migrations

*Objective:* Validate the unification of the 4 fragmented databases into a single SQLite WAL database, application of all 10 domain Alembic migrations, FTS5 full-text search, local dense vector embeddings, and Fourth Law reflection persistence.

| Test Case ID | Test Scenario | Preconditions / Setup | Stimulus / Execution Command | Expected Output & Acceptance Criteria | Required Evidence Receipt | Verdict Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-MEM-01** | Alembic Domain Migrations Application | `alembic.ini` configured; clean `data/jarvis.db`. | `alembic upgrade head` | All 10 domain migrations apply sequentially (`001_goals.py` to `010_audit_events.py`). SQLite schema contains all 16 tables. | Alembic revision log, SQLite `pragma table_info()` list of all 16 tables, 0 migration errors. | **PASS** if database schema matches canonical specification. |
| **TC-MEM-02** | SQLite FTS5 Full-Text Search Retrieval | 1,000 document chunks indexed in `data/jarvis.db`. | `python -m jarvis.search.local_search_engine --query "LangGraph state machine"` | Returns ranked search results via SQLite FTS5 `bm25()` ranking. Query latency < 5ms. Handles punctuation and boolean operators cleanly. | FTS5 query plan (`EXPLAIN QUERY PLAN`), result count, execution duration ms (<5ms), rank scores. | **PASS** if search query resolves in < 5ms with valid ranked matches. |
| **TC-MEM-03** | Local Dense Vector Embedding Retrieval | Local embedding model (`nomic-embed-text`) active. | Ingest 5 technical paragraphs; query with semantic paraphrase. | Top-1 retrieval accuracy recall > 0.85 cosine similarity. Search latency < 50ms. Zero reliance on MD5 word hashing fallback. | Cosine similarity scores, embedding vector dimensions (768), latency ms. | **PASS** if semantic match retrieved without keyword overlap. |
| **TC-MEM-04** | Fourth Law Mandatory Reflection Persistence Gate | Task execution completes successfully. | Attempt to mark goal `COMPLETED` without writing reflection record. | Transition rejected; goal marked `INCOMPLETE` with `fourth_law_compliant=false`. Persisting reflection record allows `COMPLETED` transition. | Database row in `reflections` table, goal status change receipt, validation boolean. | **PASS** if completion is physically blocked until reflection is saved. |
| **TC-MEM-05** | Scoped Multi-Tenant Scoping Isolation | 2 goals created: one for `user_id="ganesh"`, one for `user_id="test_user"`. | Query memory repository with `user_id="ganesh"`. | Returns ONLY rows matching `user_id="ganesh"`. Zero rows belonging to `"test_user"` leaked in query results. | Executed SQL statement, bound query parameters, returned row ID set. | **PASS** if zero cross-tenant memory leakage occurs. |

---

### Subsystem 4: Autonomous Workforce & Dynamic Execution

*Objective:* Validate dynamic agent lifecycle management (spawn on demand, pause/yield, retire), LangGraph DAG execution, Kahn's algorithm cycle detection, and the total eradication of the 105 mock dataclasses.

| Test Case ID | Test Scenario | Preconditions / Setup | Stimulus / Execution Command | Expected Output & Acceptance Criteria | Required Evidence Receipt | Verdict Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-WORK-01** | Dynamic Agent Lifecycle Concurrency Control | System initialized; concurrency ceiling set to 3. | Dispatch goal requiring 6 sequential and parallel tasks. | Workers spawn dynamically only when assigned active task. Active workers bounded to <= 3 at all times. Completed workers transition to `RETIRED`. | Time-series log of active agent PIDs/IDs, state transitions (`SPAWNING->ACTIVE->RETIRED`), peak concurrency count. | **PASS** if peak concurrent agents <= 3 and all retire cleanly. |
| **TC-WORK-02** | LangGraph DAG Execution & Kahn's Cycle Detection | Task Graph Engine initialized. | Submit DAG containing circular dependency (Task A -> B -> C -> A). | Kahn's algorithm detects circular dependency immediately before execution. Graph aborts with `CyclicDependencyError`. Zero tasks run. | In-degree node table, detected cycle path array, error payload. | **PASS** if circular graph is rejected without executing any node. |
| **TC-WORK-03** | Cascaded Failure & Dependent Task Cancellation | Multi-node DAG (Node A -> Node B -> Node C). | Inject permanent failure into Node A (exhausts 3 retries). | Node A transitions to `FAILED`. Dependent downstream nodes (Node B and Node C) automatically transition to `CANCELLED` without executing. | Node status transition map, retry count audit, cancellation event log. | **PASS** if downstream tasks are safely cancelled. |
| **TC-WORK-04** | CEO Central Routing & Assignment Enforcement | Central CEO Router active. | Agent attempts to self-assign a task or bypass Department Manager. | Assignment rejected immediately. Only assignments signed by the CEO Router (`task_router.py`) and Department Managers are accepted by workers. | Cryptographic `Assignment` token, reject log for unauthorized self-assignment. | **PASS** if self-assignment is physically blocked. |
| **TC-WORK-05** | Verification of Non-Simulated Task Execution | Coding task assigned to engineering worker. | Worker instructed to generate a Python helper and unit test. | Worker produces genuine code file and passes `pytest`. Zero occurrences of `time.sleep()`, fake reflex dictionaries, or mock PDF bytes. | Generated source file path, file SHA-256, pytest terminal output receipt with 0 errors. | **PASS** if real file and tests generated; **FAIL** if mock string returned. |

---

### Subsystem 5: Security, DLP & Tamper-Evident Audit Ledger

*Objective:* Validate 10-layer security shield, Presidio DLP credential redaction, ephemeral HMAC-SHA256 human approval tokens, SHA-256 chained audit ledger, and branch protection guarding against autonomous pushes to `main`.

| Test Case ID | Test Scenario | Preconditions / Setup | Stimulus / Execution Command | Expected Output & Acceptance Criteria | Required Evidence Receipt | Verdict Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-SEC-01** | Presidio DLP Regex & High-Entropy Secret Scanner | Ten-layer shield active. | Feed text containing simulated OpenAI key (`sk-proj-abc123456789...`), GitHub token (`ghp_xyz...`), and AWS secret. | Shield redacts all secrets to `[REDACTED_API_KEY]`. Prevents unredacted tokens from egressing to external API logs or prompts. | Sanitized text payload, count of detected secrets (3), entropy score calculations. | **PASS** if all secrets redacted; **FAIL** if any secret remains plain. |
| **TC-SEC-02** | Deterministic Privilege Gate Enforcement | Policy gate active. | Attempt to execute Level 3 sensitive command (e.g., `rmdir /s /q temp_dir` or shell script). | Action blocked with `ApprovalRequiredException`. Requires explicit human approval token before execution. | Privilege level evaluation (LEVEL_3), authorization prompt event, blocked status. | **PASS** if blocked until approved. |
| **TC-SEC-03** | Ephemeral HMAC-SHA256 Token Payload Binding | Action approved by human, generating signed HMAC token. | Tamper with payload parameters (e.g. change target directory from `temp_dir` to `system32`). | HMAC signature validation fails immediately. Execution aborted. Security alert logged to audit ledger. | Original payload SHA-256, tampered payload SHA-256, HMAC mismatch error. | **PASS** if tampered payload is rejected. |
| **TC-SEC-04** | SHA-256 Chained Audit Ledger Integrity | 20 audit events logged in `audits` table. | Manually alter a payload in audit row #5 via direct SQLite edit. | `AuditLogger.verify_chain_integrity()` detects hash mismatch at row #5. Chain verification fails with `AuditTamperDetectedError`. | Expected hash, calculated hash, tamper index row number. | **PASS** if database alteration is immediately detected. |
| **TC-SEC-05** | Safe PR Workflow Target Branch Protection | Safe PR manager active. | Self-improvement worker attempts `git push origin main`. | `ArchitectureGuard.validate_target_branch()` intercepts and throws `SecurityViolationError`. Push aborted. PR allowed only to `feature/imp-*`. | Intercepted Git command, target branch name (`main`), exception trace. | **PASS** if direct push to `main` is completely blocked. |
| **TC-SEC-06** | Emergency Hardware & Software Kill Switch | Background workers and audio daemons running. | Press hotkey `Ctrl+Alt+Shift+K` or POST `/api/kill`. | System halts all child processes and background tasks within < 50ms. Process states set to `KILLED`. Emergency lock active. | Kill switch trigger timestamp, process termination confirmation list, latency ms (<50ms). | **PASS** if all background activity stops in < 50ms. |

---

### Subsystem 6: Cloned Capability Tools Integration

*Objective:* Verify that the 7 cloned capabilities (`firecrawl`, `obscure-browser`, `freellmapi`, `claude-code-style`, `migrate-workflows`, `generative_ui`, `plugin`) execute as real Jarvis tools through standardized adapters outside Antigravity.

| Test Case ID | Test Scenario | Preconditions / Setup | Stimulus / Execution Command | Expected Output & Acceptance Criteria | Required Evidence Receipt | Verdict Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-CLONE-01** | Firecrawl Local Markdown Extraction Adapter | Playwright/Firecrawl dependencies installed. | `python -m jarvis.tools.adapters.firecrawl_adapter --url "https://httpbin.org/html"` | Extracts HTML and converts to clean GitHub-flavored markdown. Output contains headings and paragraphs. Latency < 3s. | Source URL, extracted markdown length, markdown `content_sha256`, duration ms. | **PASS** if valid markdown produced; **FAIL** if raw unparsed HTML. |
| **TC-CLONE-02** | ObscureBrowser Headless Extraction & SSRF Shield | Obscure-browser adapter active. | Attempt to navigate to private IP: `"http://127.0.0.1:8000/internal"` or `"http://192.168.1.1"`. | Navigation blocked immediately by SSRF filter with `PrivateNetworkAccessDenied`. Public URLs navigate successfully with stealth headers. | Target URL, SSRF block decision log, HTTP status. | **PASS** if private IPs blocked; public URLs scrape cleanly. |
| **TC-CLONE-03** | FreeLLMAPI Standalone Adapter Execution | FreeLLMAPI running on localhost:3001. | `python -m jarvis.tools.adapters.freellmapi_adapter --prompt "Hello Jarvis" --max-tokens 20` | Sends inference request to `http://localhost:3001/v1/chat/completions`. Receives valid text completion. Latency recorded. | HTTP response code (200), completion text, token count, latency ms. | **PASS** if completion received from port 3001. |
| **TC-CLONE-04** | Claude-Code-Style Engineering Linter Tool | Target Python script with formatting/pattern flaws. | `python -m jarvis.tools.adapters.code_style_adapter --check-file jarvis/core/orchestrator.py` | Lints file against agentic engineering rules (no multi-file sprawl, root-cause fixes, test coverage). Returns structured violation list. | File path, violation count, rule IDs triggered, AST analysis metrics. | **PASS** if linter produces structured violation receipts. |
| **TC-CLONE-05** | Workflow Migrator Translation Tool | Legacy shell build script. | `python -m jarvis.tools.adapters.workflow_migrator_adapter --input-script build.sh` | Generates equivalent, valid GitHub Actions YAML workflow adhering to project security constraints. | Generated YAML text, YAML syntax validation status, SHA-256. | **PASS** if valid GitHub Actions YAML generated. |
| **TC-CLONE-06** | Generative UI Dynamic Component Generator | UI adapter registered. | `python -m jarvis.tools.adapters.generative_ui_adapter --schema-type "system_health_widget"` | Generates valid JSON component schema with telemetry gauges, status badges, and action buttons. Validates against schema. | Generated schema JSON, schema validation boolean (`true`), SHA-256. | **PASS** if valid UI descriptor schema returned. |
| **TC-CLONE-07** | Plugin Loader Sandboxed Registration | Dynamic plugin manifest. | Register a custom math utility tool via `PluginLoader`. | Tool registers in `jarvis/tools/registry.py`; executes under privilege isolation; cannot access filesystem or secrets without clearance. | Tool registry entry, permission level, execution result receipt. | **PASS** if tool registers and executes within permission boundary. |

---

### Subsystem 7: Independent Execution Outside Antigravity

*Objective:* Prove that Project JARVIS is entirely self-sufficient and operational from native Windows terminals with Antigravity completely closed.

| Test Case ID | Test Scenario | Preconditions / Setup | Stimulus / Execution Command | Expected Output & Acceptance Criteria | Required Evidence Receipt | Verdict Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-STANDALONE-01** | Native CLI Chat Execution | Antigravity closed. Windows PowerShell terminal. | `python -m jarvis.main chat --query "Jarvis, report system health"` | Starts Python process; queries model router; returns structured health summary to stdout; exits cleanly with code 0. | Process PID, stdout text, exit code (0), execution latency ms. | **PASS** if CLI executes natively without Antigravity hooks. |
| **TC-STANDALONE-02** | Native FastAPI Server & WebSocket HUD | Antigravity closed. Windows PowerShell terminal. | `python -m uvicorn jarvis.api.server:app --port 8000` & `curl.exe http://localhost:8000/health` | Uvicorn server boots on port 8000. `/health` returns `{"status": "healthy", "version": "2.0.0"}` in < 20ms. WebSocket stream accepts connection. | Server PID, port (8000), HTTP response JSON, WebSocket connection receipt. | **PASS** if server serves API and WebSocket natively. |
| **TC-STANDALONE-03** | Standalone Desktop Worker Execution (Notepad) | Antigravity closed. Windows PowerShell terminal. | `python -m jarvis.tools.desktop.notepad --text "Independent test" --verify` | Notepad launches on screen; text types; buffer readback matches; prints JSON receipt to stdout; exits with code 0. | Notepad PID, window HWND, readback text, JSON receipt on stdout. | **PASS** if Notepad automation succeeds outside Antigravity. |
| **TC-STANDALONE-04** | Master Pytest Test Suite Execution | Antigravity closed. Windows PowerShell terminal. | `pytest tests/ -v --ignore=tests/manual` | All unit, integration, and security tests pass. 0 failures. 0 mock fallbacks detected. | Pytest terminal output, passed test count, execution duration. | **PASS** if all automated tests pass natively. |

---

## 4. Test Execution Protocol & Attestation Procedure

### 4.1 Execution Phases & Pre-Flight Checks
Before initiating an acceptance test run:
1. **Host Verification**: Confirm Windows 11 host environment, 24 GB RAM, and NVIDIA RTX 4050 GPU via PowerShell:
   ```powershell
   Get-CimInstance Win32_OperatingSystem | Select-Object Caption, TotalVisibleMemorySize
   nvidia-smi --query-gpu=name,memory.total --format=csv
   ```
2. **Local Model Pre-Flight**: Verify Ollama is running and model weights are present:
   ```powershell
   curl.exe -s http://localhost:11434/api/tags
   ```
3. **Audio Pre-Flight**: Verify physical microphone and playback devices:
   ```powershell
   python -c "import sounddevice as sd; print(sd.query_devices())"
   ```

### 4.2 Logging & Artifact Archival
1. Every test run writes its full execution trace and evidence receipts to:
   `data/receipts/acceptance_runs/[YYYY-MM-DD_HHMMSS]/`
2. Screenshots captured during UI verification are archived in:
   `data/receipts/screenshots/`
3. Audio recordings from voice tests are stored in:
   `data/receipts/audio/`
4. The cryptographic audit chain is written to:
   `data/jarvis.db` (table `audits`) and exported to `data/audit_ledger.jsonl`.

### 4.3 Definition of Test Verdicts

- **`PASS`**: The test executed completely; all assertions evaluated to true; a complete, valid `EvidenceReceipt` was generated with valid PIDs and SHA-256 hashes; zero mock fallbacks or Second Law violations were detected.
- **`FAIL`**: The test threw an unhandled exception, failed an assertion, timed out, or emitted a fake/mocked fallback string.
- **`BLOCKED`**: The test requires physical hardware (e.g., physical Windows microphone or owner vocal input) that is physically unavailable in the current test environment. **A BLOCKED test is NEVER reported as PASSED.** It must remain explicitly marked as `BLOCKED: Awaiting Physical Hardware` until the physical test is performed on the host machine.
- **`REJECTED`**: The test produced fabricated evidence, simulated sleep delays, or attempted to pass via hardcoded test cheats. Triggers immediate integrity rejection.

---

## 5. Forensic Audit & Sign-Off Attestation

| Subsystem Suite | Total Test Cases | Automation Status | Hardware Dependency | Responsible Role | Pass Criteria |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **1. Voice Pipeline & Wake** | 8 | Semi-Automated / Live | Physical Mic, Speakers, GPU | Worker 2 (Roadmap & Matrix) | All 8 pass or physical tests marked BLOCKED |
| **2. Model Router & Local LLM** | 6 | Fully Automated | RTX 4050 GPU, Ollama | Worker 2 | 100% pass; VRAM <= 5.8 GB |
| **3. Memory & Migrations** | 5 | Fully Automated | Local SQLite, Disk I/O | Worker 2 | 100% pass; 10 Alembic revisions active |
| **4. Autonomous Workforce** | 5 | Fully Automated | Local CPU, Memory | Worker 2 | 100% pass; peak concurrency <= 3 |
| **5. Security & Audit Ledger** | 6 | Fully Automated | Cryptographic CPU | Worker 2 | 100% pass; tamper detection active |
| **6. Cloned Capabilities** | 7 | Fully Automated | Playwright, Local Router | Worker 2 | All 7 tools execute outside Antigravity |
| **7. Standalone Execution** | 4 | Fully Automated | Native Terminal, Win32 | Worker 2 | 100% pass with Antigravity closed |
| **Total** | **41** | **39 Auto / 2 Physical** | — | — | **Zero Fabrications Allowed** |
