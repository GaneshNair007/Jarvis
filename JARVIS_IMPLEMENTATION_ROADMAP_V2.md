# JARVIS Personal AI Operating System: Implementation Roadmap (V2)

**Document Version:** 2.0.0  
**Date:** 2026-11-10  
**Status:** Approved Technical Blueprint  
**Target Environment:** Windows 11 (64-bit), 24 GB System RAM, NVIDIA GeForce RTX 4050 Laptop GPU (6 GB VRAM)  
**Governing Documents:** `docs/constitution/JARVIS_MASTER_DIRECTIVE.md` (v1.2.0), `jarvis/constitution/*.yaml`, `ORIGINAL_REQUEST.md` (Corrective Priority Update)  
**Supersedes:** `docs/IMPLEMENTATION_ROADMAP.md` (v1.0.0)

---

## 1. Executive Summary & Architectural Alignment

Project JARVIS is a private, local-first **Personal AI Operating System** and autonomous cognitive enterprise engineered exclusively for **Ganesh Nair**. Its sole constitutional mission is to maximize Ganesh's growth, technical opportunities, engineering output, and research capabilities without compromising local data privacy or relying on mandatory paid cloud infrastructure.

Following the comprehensive repository audit and corrective priority directive, this Roadmap (V2) establishes a strict, non-negotiable **5-Stage execution order**. It directly eliminates the historical pathologies identified across the codebase: structural dualism (root shadow trees), 8 competing orchestration engines, pervasive mock fallbacks (fake resume PDFs, hardcoded test strings, 440 Hz sine-wave beeps), superficial 105-agent dataclass loops, and unverified cloned repositories.

### 1.1 The Inviolable 5-Stage Execution Order

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ STAGE 1: Architecture & Repository Audit (Deliverable 1 Foundation)         │
│  - 4 Constitutional Audit Documents + Top 10 Critical Architectural Gaps    │
│  - Cloned Capability Inventory + Empirical FreeLLMAPI (3001) Verification    │
│  - Consolidation of Root Shadow Trees into Unified `jarvis/` Packaging      │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STAGE 2: "Hey Jarvis" — Real Voice Activation (P0 Runtime Milestone)       │
│  - Physical Windows Microphone Capture (`sounddevice`)                      │
│  - Local Acoustic Wake Word Gate (`openWakeWord`) < 500ms                   │
│  - Streaming Speech Capture & Local Transcription (`faster-whisper` CUDA)   │
│  - Two-Stage Interaction: (1) "Hey Jarvis" -> (2) "Yes, Ganesh?" chime/voice│
│  - Core Dispatch -> Win32 Tool -> Open Notepad -> Type "Jarvis is awake"   │
│  - Window Text Buffer Extraction & Cryptographic Hash Verification Receipt  │
│  - Local Neural TTS Spoken Response (`kokoro-onnx` / Windows SAPI)          │
│  - ZERO Mock Audio, ZERO Sine Beeps, ZERO Antigravity Delegation            │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STAGE 3: Seven Cloned Capabilities Integration                              │
│  - Rigorous Adapters for Cloned Repositories in `repos/` and Config Skills   │
│  - `firecrawl` & `obscure-browser` -> Safe Local Extraction Tools           │
│  - `freellmapi` -> Port 3001 Cloud Proxy Router Adapter (with Presidio DLP)  │
│  - `claude-code-style` -> Engineering Discipline & Linter Rule Engine       │
│  - `generative_ui` & `plugin` -> Dynamic Interface & Capability Registry    │
│  - `migrate-workflows` -> Workflow Transformation Substrate                 │
│  - Independent Execution Test Harness (Zero Antigravity Reliance)           │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STAGE 4: Canonical Multi-Agent Workforce                                    │
│  - Purge 105 Fake Dataclasses, RuFlo String Matching, & Mock PDF Generators │
│  - Dynamic Lifecycle Management: Spawn on Demand, Pause/Yield, Retire       │
│  - Central CEO Router & 6 Real Departmental Workflows                       │
│  - LangGraph Deterministic DAG Engine with Cycle Detection (Kahn's Algo)    │
│  - Strict Bounded Concurrency (Max 2-3 Active Workers <= 3.8 GB VRAM)       │
│  - Tamper-Evident Chained SHA-256 Audit Ledger + Ten-Layer Security Shield  │
│  - 8-Layer Memory Hierarchy & Fourth Law Mandatory Reflection Gate          │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STAGE 5: Always-On Personal AI Operating System                             │
│  - Autonomous Proactive Scheduler (Hackathons, Career Radar, arXiv Sync)    │
│  - See-Act-Verify UI Worker (Win32 Accessibility + Presidio DLP Blurring)   │
│  - Glassmorphic WebSocket HUD & Telemetry Dashboard                         │
│  - Windows Native Background Service Startup & Tray Failsafe                │
│  - Continuous Self-Audit & Safe PR Workflow (Zero Direct Push to Main)      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Core Execution Rules & Integrity Mandates
1. **Rule 1 — Zero Mock Fallbacks (The Second Law)**: Hardcoded string matching to pass tests (e.g. `core/model_router.py` returning canned text for "remember", or `career_ops.py` writing `"%PDF-1.4 Mock ATS Resume"`) is strictly forbidden. Disconnected components must fail honestly with clear error telemetry (`trust_level="unverified"` or explicit exception).
2. **Rule 2 — Independent Execution Outside Antigravity**: Every milestone must be independently runnable and verifiable via native Python (`python -m ...`) or PowerShell (`pwsh`) from a terminal where Antigravity is closed.
3. **Rule 3 — Strict Local Hardware Envelope & Egress Truthfulness**: Total concurrent VRAM utilization must never exceed **3.8 GB active allocation** (leaving >=2.2 GB headroom below the 6.0 GB ceiling of the NVIDIA RTX 4050 GPU). Primary reasoning and reflex operations must run locally via Ollama without WAN egress. FreeLLMAPI at `http://localhost:3001` is classified as a Tier 3 external cloud proxy fallback to Groq, strictly subject to Presidio DLP redaction and prohibited from receiving private memory vault facts.
4. **Rule 4 — Objective Evidence Receipts**: Every operation must generate an `EvidenceReceipt` containing OS process IDs (PIDs), cryptographic SHA-256 hashes of generated buffers or files, tool invocation timestamps, and verifiable exit codes.

---

## 2. Stage 1: Architecture & Repository Audit (Deliverable 1 Foundation)

**Objective:** Establish the ground-truth technical state of the repository, deliver the 4 governing architecture documents, expose the Top 10 Critical Architectural Gaps, audit the 7 cloned repositories, verify the local FreeLLMAPI router, and consolidate the fragmented root shadow directories.

### Milestone 1.1: Vision Audit & Top 10 Critical Architectural Gaps
- **Deliverable Path:** `docs/JARVIS_VISION_VS_IMPLEMENTATION_AUDIT.md`
- **Scope:** Complete comparison of constitutional directives against physical codebase implementation. Detailed documentation of the Top 10 Critical Gaps with exact line numbers, architectural impact, and remediation paths.
- **Defects Resolved:**
  - Reconciles unverified documentation claims against actual code.
  - Documents all disconnected execution paths and mock fallbacks across 133+ modules.
- **Files Modified / Created:**
  - `docs/JARVIS_VISION_VS_IMPLEMENTATION_AUDIT.md` (Created)
- **Prerequisites:** Completion of survey reports (`survey_spec_report.md`, `survey_repo_report.md`, `survey_subsystems_report.md`).
- **Implementation Steps:**
  1. Audit governing principles against existing code (Four Laws, 4 Inviolable Constraints, 10-Layer Shield).
  2. Detail the 10 Critical Gaps:
     - Gap 1: Structural Dualism & Root Shadow Trees.
     - Gap 2: Orchestration Fragmentation across 8 Competing Engines.
     - Gap 3: Pervasive Mock Fallbacks & Test-Gaming Stubs.
     - Gap 4: Superficial Workforce Simulation (105 Dataclass Counter).
     - Gap 5: Memory Subsystem Fragmentation (4 Incompatible DBs & Orphaned Alembic Migrations).
     - Gap 6: Ghost Voice & Perception Pipeline (Missing Dependencies & 440 Hz Sine Beeps).
     - Gap 7: Hardware Over-Allocation (32B Model on 6GB VRAM) & Absent FreeLLMAPI.
     - Gap 8: Unmounted API Routers & Dead Demonstration Code (`apps/ecommerce-astra`).
     - Gap 9: Cloned Repositories Bloat (`repos/` Unlinked Code Drops).
     - Gap 10: Docker Infrastructure Bloat vs. Native Windows Runtime.
  3. Formulate concrete remediation strategies for each gap.
- **Verification Commands:**
  ```powershell
  # Verify existence and completeness of Audit Document
  Get-Item "C:\Users\Ganesh Nair\.gemini\antigravity-ide\scratch\jarvis\docs\JARVIS_VISION_VS_IMPLEMENTATION_AUDIT.md"
  # Confirm all 10 critical gaps are documented with exact file references
  Select-String -Path "docs\JARVIS_VISION_VS_IMPLEMENTATION_AUDIT.md" -Pattern "### Gap "
  ```

### Milestone 1.2: Canonical Architecture Blueprint Consolidation
- **Deliverable Path:** `docs/JARVIS_CANONICAL_ARCHITECTURE.md`
- **Scope:** Define the unified, local-first target architecture resolving the 8 competing orchestration engines into a single LangGraph state machine, establishing dynamic agent lifecycles, and specifying the 8-layer unified memory vault.
- **Defects Resolved:**
  - Resolves bifurcated chat routes (`/api/v1/chat` and `/chat`).
  - Replaces superficial agent counters with verifiable dynamic lifecycle specifications.
- **Files Modified / Created:**
  - `docs/JARVIS_CANONICAL_ARCHITECTURE.md` (Created)
- **Prerequisites:** Milestone 1.1.
- **Implementation Steps:**
  1. Define the 12 Canonical Systems with strict boundaries and zero-trust interfaces.
  2. Map the 8-node LangGraph execution cycle (`Perceive -> Recall -> Plan -> Policy -> Act -> Verify -> Reflect -> Remember`).
  3. Specify dynamic agent lifecycle transitions (`UNINITIALIZED -> SPAWNING -> ACTIVE -> PAUSED -> RETIRED`).
  4. Specify the unified SQLite WAL database schema and repository pattern (`UnitOfWork`).
  5. Codify the 3-Tier Model Routing hierarchy with hardware budget ceilings.
- **Verification Commands:**
  ```powershell
  Get-Item "C:\Users\Ganesh Nair\.gemini\antigravity-ide\scratch\jarvis\docs\JARVIS_CANONICAL_ARCHITECTURE.md"
  Select-String -Path "docs\JARVIS_CANONICAL_ARCHITECTURE.md" -Pattern "## 8-Node LangGraph State Machine"
  ```

### Milestone 1.3: Cloned Capability Inventory & FreeLLMAPI Live Verification
- **Deliverable Path:** `docs/JARVIS_CLONED_CAPABILITY_INVENTORY.md`
- **Scope:** Exhaustive inspection of the 7 cloned capabilities (`claude-code-style`, `firecrawl`, `freellmapi`, `generative_ui`, `migrate-workflows`, `obscure-browser`, `plugin`). Empirical probe of FreeLLMAPI router at `http://localhost:3001`.
- **Defects Resolved:**
  - Eliminates blind trust in unverified cloned repositories in `repos/` and configuration skills.
  - Verifies whether `http://localhost:3001` is live, its response latency, models, and privacy leak risks.
- **Files Modified / Created:**
  - `docs/JARVIS_CLONED_CAPABILITY_INVENTORY.md` (Created)
- **Prerequisites:** Survey reports and live socket probes.
- **Implementation Steps:**
  1. Inspect physical directory, git commit, remote, and entry points for all 7 clones.
  2. Classify each as runtime tool candidate, development guideline, or standalone utility.
  3. Execute HTTP probes against `http://localhost:3001` (`/v1/models`, `/health`, test inference).
  4. Measure latency, verify local loopback binding (`127.0.0.1`), and document offline fallback behavior.
  5. Design concrete tool adapter specifications for runtime integration in Stage 3.
- **Verification Commands:**
  ```powershell
  # Probe FreeLLMAPI router live
  curl.exe -s http://localhost:3001/v1/models
  Get-Item "C:\Users\Ganesh Nair\.gemini\antigravity-ide\scratch\jarvis\docs\JARVIS_CLONED_CAPABILITY_INVENTORY.md"
  ```

### Milestone 1.4: Repository Structural Unification (Package Reorganization)
- **Scope:** Eliminate root shadow directories (`core/`, `graph/`, `search/`, `db/`, `integrations/`, `dashboard/`) by migrating all genuine code into `jarvis/`, updating `pyproject.toml`, and establishing standard editable package installation (`pip install -e .`).
- **Defects Resolved:**
  - Eliminates `sys.path` collision between root stubs and `jarvis/` submodules.
  - Replaces root `graph/jarvis_graph.py` (8-node) over `jarvis/graph/jarvis_graph.py` (4-node stub).
  - Merges orphaned `db/migrations/` (10 domain revisions) into `alembic/versions/`.
- **Files to Modify / Move / Delete:**
  - **Move / Consolidate:**
    - `graph/jarvis_graph.py` -> `jarvis/brain/graph.py` (authoritative 8-node LangGraph)
    - `search/local_search_engine.py`, `hybrid_ranker.py` -> `jarvis/search/`
    - `integrations/*` -> `jarvis/integrations/`
    - `dashboard/*` -> `jarvis/dashboard/`
    - `db/migrations/*.py` -> `alembic/versions/`
  - **Delete:**
    - `core/model_router.py` (mock test fallback stub)
    - Root `core/` directory
    - `apps/ecommerce-astra/` (unrelated demo app)
    - `jarvis/mcp_gateway/` (empty directory)
  - **Modify:**
    - `alembic.ini` (wire to `alembic/versions/` containing all 10 domain migrations)
    - `pyproject.toml` (add package discovers and declare real dependencies)
- **Prerequisites:** Milestones 1.1–1.3.
- **Implementation Steps:**
  1. Transfer genuine logic from root packages into corresponding `jarvis/` submodules.
  2. Refactor all import statements across the codebase from `import core.*`, `import graph.*`, `import search.*` to `from jarvis.core import ...`, `from jarvis.brain import ...`, `from jarvis.search import ...`.
  3. Delete duplicate root directories and stubs.
  4. Run `alembic check` and ensure all 10 domain revisions are recognized.
- **Verification Commands:**
  ```powershell
  pytest tests/test_imports.py -v
  python -c "import jarvis; print(jarvis.__file__)"
  alembic history
  ```

---

## 3. Stage 2: "Hey Jarvis" — Real Voice Activation (P0 Runtime Milestone)

**Objective:** Implement the real-world, hardware-grounded acoustic perception, speech transcription, core dispatch, desktop tool execution, content verification, and voice synthesis pipeline. When Ganesh speaks "Hey Jarvis", the system wakes, acknowledges, accepts an instruction ("open Notepad and type Jarvis is awake"), opens physical Notepad, types the text, reads back the window text buffer to verify content, and speaks confirmation.

**Zero Mock Audio Mandate:** No synthetic sine-wave beeps, no pre-recorded audio buffers, no simulated STT strings, no fake GUI clicks, and no Antigravity delegation.

### Milestone 2.1: Physical Microphone Audio Stream & VAD Capture
- **Target Subsystem:** `jarvis/voice/` (`capture.py`, `vad.py`)
- **Defects Resolved:** Resolves missing `sounddevice` and `webrtcvad` in project dependencies. Eliminates simulated audio buffer generators.
- **Files to Modify / Create:**
  - `pyproject.toml` & `requirements.txt` (Add `sounddevice>=0.4.6`, `numpy>=1.24.0`, `webrtcvad>=2.0.10`)
  - `jarvis/voice/capture.py` (New real-time audio capture engine using `sounddevice.InputStream`)
  - `jarvis/voice/vad.py` (Energy + WebRTC VAD voice activity detector)
- **Prerequisites:** Physical audio input device connected to Windows 11 host.
- **Implementation Steps:**
  1. Add audio libraries to `pyproject.toml` with strict version bounds.
  2. Implement `AudioCaptureEngine` in `jarvis/voice/capture.py`:
     - Query and validate default Windows input device (`sounddevice.query_devices(kind='input')`).
     - Configure PCM audio stream: 16,000 Hz sample rate, 16-bit mono linear PCM (`dtype='int16'`).
     - Maintain a thread-safe sliding audio ring buffer (`collections.deque` with max 3 seconds audio).
     - Handle `PortAudioError` gracefully: if no microphone is detected, emit honest hardware failure receipt (`AUDIO_DEVICE_NOT_FOUND`) rather than returning fake silence.
  3. Implement `VoiceActivityDetector` in `jarvis/voice/vad.py`:
     - Process 20ms audio frames (320 samples).
     - Combine WebRTC VAD level 2 with RMS energy threshold to filter background ambient noise.
- **Verification Commands & Criteria:**
  ```powershell
  # Test real audio capture from default physical microphone (records 2 seconds of ambient audio)
  python -m jarvis.voice.capture --probe-devices
  python -m jarvis.voice.capture --record-test --duration 2.0 --out data/test_mic.wav
  ```
  *Pass Criteria:* `data/test_mic.wav` is written to disk with non-zero bytes, valid WAV RIFF header, 16 kHz sample rate, and non-zero RMS amplitude. If no mic is physically attached, command returns exit code 2 with explicit hardware error message.

### Milestone 2.2: Local Acoustic Wake Word Engine (`openWakeWord`)
- **Target Subsystem:** `jarvis/voice/wake.py`
- **Defects Resolved:** Replaces missing wake-word dependencies and string-matching fallbacks (`voice_stream.py:163`) with genuine on-device acoustic wake detection.
- **Files to Modify / Create:**
  - `pyproject.toml` (Add `openwakeword>=0.6.0`, `onnxruntime>=1.16.0`)
  - `jarvis/voice/wake.py` (Re-implement `WakeWordDetector` wrapping `openwakeword.Model`)
  - `jarvis/voice/models/` (Bundle local ONNX wake word weights: `hey_jarvis.onnx` or `jarvis.onnx`)
- **Prerequisites:** Milestone 2.1; CPU or ONNX DirectML/CUDA runtime.
- **Implementation Steps:**
  1. Initialize `openwakeword.Model` targeting pre-trained "hey jarvis" / "jarvis" models.
  2. Feed continuous 80ms audio chunks (1,280 samples) from `AudioCaptureEngine` ring buffer.
  3. Compute prediction score per chunk; evaluate against configurable activation threshold (`threshold = 0.5`).
  4. Enforce refractory lockout (1.5 seconds) post-activation to prevent duplicate wake triggers.
  5. Compute and log wake detection latency (target: < 500ms from utterance completion to trigger).
- **Verification Commands & Criteria:**
  ```powershell
  # Test acoustic wake detector against sample WAV or live mic stream
  python -m jarvis.voice.wake --model-path jarvis/voice/models/hey_jarvis.onnx --test-live
  ```
  *Pass Criteria:* Uttering "Hey Jarvis" triggers a `WakeWordEvent` with confidence score >= 0.5, timestamp, and latency receipt. Silence or unrelated speech produces confidence < 0.1.

### Milestone 2.3: Streaming Speech Capture & Local Transcription (`faster-whisper`)
- **Target Subsystem:** `jarvis/voice/stt.py`
- **Defects Resolved:** Eliminates `jarvis/voice/stt.py:61-72` test cheat where any audio >0.5s returned `"Jarvis, report system health"`.
- **Files to Modify / Create:**
  - `pyproject.toml` (Add `faster-whisper>=1.0.0`, `ctranslate2>=4.0.0`)
  - `jarvis/voice/stt.py` (Complete rewrite using `faster_whisper.WhisperModel`)
- **Prerequisites:** NVIDIA CUDA 12.x or CPU int8 fallback; model weights `base.en` or `small.en`.
- **Implementation Steps:**
  1. Instantiate `WhisperModel("base.en", device="cuda" if cuda_available else "cpu", compute_type="float16" if cuda_available else "int8")`.
  2. Wire audio capture loop:
     - On wake event, begin recording audio stream into speech buffer.
     - VAD monitors speech continuation; detect end-of-speech after 800ms of sustained silence.
     - Maximum command speech window capped at 10.0 seconds.
  3. Transcribe audio buffer via `model.transcribe(audio_buffer, beam_size=1, language="en", vad_filter=False)`:
     - Extract normalized text string, word-level confidence scores, and processing duration.
  4. If audio contains zero speech or transcription confidence < 0.35, return explicit empty transcript (`transcript=""`, `confidence=0.0`), NEVER a canned mock string.
- **Verification Commands & Criteria:**
  ```powershell
  python -m jarvis.voice.stt --model base.en --input-audio data/test_mic.wav
  ```
  *Pass Criteria:* Returns transcribed text reflecting spoken audio; processing latency < 400ms on RTX 4050 GPU; zero hardcoded string injections.

### Milestone 2.4: Core Two-Stage Conversational State Machine
- **Target Subsystem:** `jarvis/voice/conversation_loop.py` & `jarvis/core/orchestrator.py`
- **Defects Resolved:** Implements the mandatory two-stage interaction flow required by the user:
  1. Ganesh says "Hey Jarvis".
  2. Jarvis acknowledges immediately ("Yes, Ganesh?" or acknowledgment tone).
  3. Ganesh speaks the instruction ("Open Notepad and type Jarvis is awake").
  4. Jarvis processes, executes, and verifies.
- **Files to Modify / Create:**
  - `jarvis/voice/conversation_loop.py` (New two-stage conversational loop coordinator)
  - `jarvis/core/orchestrator.py` (Wire voice events to `JarvisOrchestrator`)
- **Prerequisites:** Milestones 2.1–2.3.
- **Implementation Steps:**
  1. Implement state transitions:
     - `LISTENING_FOR_WAKE`: Continuous low-power acoustic monitoring.
     - `ACKNOWLEDGING`: On wake detection, immediately trigger acknowledgment (play local chime or synthesize "Yes, Ganesh?" in <250ms).
     - `CAPTURING_INTENT`: Open microphone for command capture with VAD silence detector.
     - `DISPATCHING`: Send transcribed instruction to `JarvisOrchestrator.process_command()`.
     - `EXECUTING_AND_VERIFYING`: Track tool execution receipts and verification proofs.
     - `RESPONDING`: Synthesize spoken confirmation through TTS and return to `LISTENING_FOR_WAKE`.
  2. Support both two-stage interaction ("Hey Jarvis" -> pause -> "Yes, Ganesh?" -> "Open Notepad...") AND continuous single-utterance interaction ("Hey Jarvis, open Notepad...").
- **Verification Commands & Criteria:**
  ```powershell
  pytest tests/test_conversation_state_machine.py -v
  ```
  *Pass Criteria:* State transitions advance deterministically with timestamped state logs and zero deadlocks.

### Milestone 2.5: Windows 11 Modern Notepad UIAutomation & Buffer Readback Verification
- **Target Subsystem:** `jarvis/tools/desktop/notepad.py` & `jarvis/tools/desktop/win32_window.py`
- **Defects Resolved:** Solves Windows 11 AppX trampoline launcher PID mismatch, WinUI 3 XAML island control discovery failure, and Windows OS focus-stealing locks. Replaces mocks with physical UI Automation and readback verification.
- **Files to Modify / Create:**
  - `pyproject.toml` (Add `pywin32>=306`, `pywinauto>=0.6.8`, `uiautomation>=2.0.18`, `Pillow>=10.0.0`)
  - `jarvis/tools/desktop/notepad.py` (Real Notepad launcher, typist, and buffer reader)
  - `jarvis/tools/desktop/job_object.py` (Win32 Job Object process containment)
  - `jarvis/tools/desktop/win32_window.py` (Win32 focus and window controller)
  - `jarvis/tools/registry.py` (Register `desktop_open_notepad_and_type` in tool registry)
- **Prerequisites:** Windows 11 host environment with Modern Notepad.
- **Implementation Steps:**
  1. Launch Notepad under Win32 Job Object:
     - Spawn Notepad using `subprocess.Popen(["notepad.exe"])` and assign the process to a Win32 Job Object configured with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`.
  2. Resolve True Window PID and HWND (Trampoline Resolution):
     - On Windows 11, `notepad.exe` in `System32` is a trampoline stub that starts the packaged app and terminates.
     - Poll `EnumWindows` matching window title regex `r".*Notepad.*"` or class `"Notepad"`.
     - Extract the true active process ID using `win32process.GetWindowThreadProcessId(hwnd)`.
     - Record this resolved window PID (not the trampoline PID) in the execution receipt.
  3. Reliable Window Focus:
     - Overcome Windows `SPI_SETFOREGROUNDLOCKTIMEOUT` by binding thread input via `user32.AttachThreadInput` to the foreground window thread, or invoking `uiautomation.WindowControl(searchDepth=1, ClassName='Notepad').SetFocus()`.
  4. WinUI 3 Text Typing & Verification via UI Automation:
     - Modern Windows 11 Notepad uses XAML island text controls with class `"RichEditD2DPT"` or control type `EditControl` / `DocumentControl` (zero classic Win32 `"Edit"` controls exist).
     - Use `pywinauto.Application(backend="uia").connect(handle=hwnd)`:
       - Locate the document element: `edit_ctrl = window.child_window(control_type="Document")` or class `"RichEditD2DPT"`.
       - Set focus and type `"Jarvis is awake"` via UI Automation `ValuePattern` or keyboard type keys.
  5. Buffer Readback Verification (First Law Receipt):
     - Read back the text buffer using `edit_ctrl.get_value()` or `DocumentControl.GetTextPattern().DocumentRange.GetText(-1)`.
     - Assert that the extracted buffer exactly contains `"Jarvis is awake"`.
     - Capture active window screenshot via `Pillow.ImageGrab.grab(bbox)` and compute SHA-256 hash.
     - Generate an `EvidenceReceipt`:
       - `target_app`: `"notepad.exe"`
       - `pid`: True resolved window PID (confirmed in `EnumProcesses`)
       - `hwnd`: Integer window handle
       - `verified_text`: `"Jarvis is awake"`
       - `content_sha256`: SHA-256 of extracted text buffer
       - `screenshot_sha256`: SHA-256 of window screenshot
       - `verification_status`: `"VERIFIED_MATCH"`
- **Verification Commands & Criteria:**
  ```powershell
  python -m jarvis.tools.desktop.notepad --text "Jarvis is awake" --verify
  ```
  *Pass Criteria:* Notepad opens on screen; true window PID resolved; text physically typed; buffer read back matches "Jarvis is awake"; screenshot SHA-256 computed; valid receipt printed; exits with code 0.

### Milestone 2.6: Local Neural TTS Spoken Response Synthesis
- **Target Subsystem:** `jarvis/voice/tts.py`
- **Defects Resolved:** Eliminates 440 Hz mathematical sine-wave beeps (`jarvis/voice/tts.py:151-172` and `voice_stream.py:229-247`). Implements genuine neural speech synthesis via `kokoro-onnx` or Windows native SAPI.
- **Files to Modify / Create:**
  - `pyproject.toml` (Add `kokoro-onnx>=0.2.0`, `soundfile>=0.12.1`)
  - `jarvis/voice/tts.py` (Rewrite `TextToSpeechEngine` with primary `kokoro-onnx` and native SAPI fallback)
  - `jarvis/voice/models/` (Bundle Kokoro 82M ONNX model weights and voice library: `af_heart.bin` / `am_adam.bin`)
- **Prerequisites:** Milestone 2.1; audio output device.
- **Implementation Steps:**
  1. Initialize `KokoroTTS`:
     - Load ONNX weights and voice embedding.
     - Generate natural 24 kHz spoken audio waveform for confirmation message: `"I have opened Notepad and verified the text: Jarvis is awake."`
  2. Implement local Windows SAPI fallback:
     - If Kokoro model is missing or initializing, fallback to Windows `win32com.client.Dispatch("SAPI.SpVoice")` to speak through the native Windows speech engine.
     - NEVER fall back to sine-wave audio tones. If audio output fails, log honest error receipt.
  3. Output audio stream to default playback device via `sounddevice.play()`.
  4. Provide instant barge-in cancellation: if user speaks during TTS playback, immediately halt audio stream (`sounddevice.stop()`).
- **Verification Commands & Criteria:**
  ```powershell
  python -m jarvis.voice.tts --text "I have opened Notepad and verified the text: Jarvis is awake." --play
  ```
  *Pass Criteria:* Natural spoken voice is heard through speakers; audio synthesis latency < 600ms; zero sine-wave beeps generated.

### Milestone 2.7: End-to-End P0 Physical Verification Run
- **Target Subsystem:** Full Voice Pipeline Integration (`jarvis/main.py voice`)
- **Defects Resolved:** Validates the entire real voice activation chain end-to-end without Antigravity involvement.
- **Files to Modify / Create:**
  - `tests/manual/verify_p0_voice_notepad.py` (Automated end-to-end test runner producing JSON receipt)
- **Prerequisites:** Physical microphone, speakers, Windows 11 host.
- **Implementation Steps:**
  1. Launch `python tests/manual/verify_p0_voice_notepad.py`.
  2. Stage 1: Wait for acoustic wake "Hey Jarvis" from physical microphone.
  3. Stage 2: Emit acknowledgment chime/voice.
  4. Stage 3: Capture spoken command "Open Notepad and type Jarvis is awake".
  5. Stage 4: Transcribe locally via `faster-whisper`.
  6. Stage 5: Dispatch to `desktop_open_notepad_and_type` tool.
  7. Stage 6: Launch Notepad, type text, extract window buffer, assert match.
  8. Stage 7: Speak confirmation "Jarvis is awake in Notepad".
  9. Write complete cryptographic execution audit receipt to `data/receipts/p0_voice_verification.json`.
- **Verification Commands & Criteria:**
  ```powershell
  # Run P0 Voice Verification outside Antigravity
  python tests/manual/verify_p0_voice_notepad.py
  ```
  *Pass Criteria:* Script logs all 7 stages with physical hardware timestamps; `data/receipts/p0_voice_verification.json` contains real PID, extracted buffer `"Jarvis is awake"`, and SHA-256 hashes; exit code 0. (Note: Marked `BLOCKED: Awaiting Physical Hardware` if executed on headless CI without audio input).

---

## 4. Stage 3: Seven Cloned Capabilities Integration

**Objective:** Inspect, wrap, and integrate the seven cloned repositories and configuration skills into real, independently executable Jarvis tools registered in `PowerBinder` and `jarvis/tools/registry.py`.

### Milestone 3.1: Tool Adapter Abstraction & Security Isolation Layer
- **Target Subsystem:** `jarvis/tools/base.py` & `jarvis/tools/registry.py`
- **Defects Resolved:** Resolves unstructured tool execution and unvetted cloned code drops.
- **Files to Modify / Create:**
  - `jarvis/tools/base.py` (Base class `JarvisToolAdapter` enforcing schemas, DLP, timeouts, and evidence)
  - `jarvis/tools/registry.py` (Central tool registry binding tools to permissions)
- **Implementation Steps:**
  1. Define `JarvisToolAdapter` with abstract methods:
     - `execute(params: dict) -> ToolResult`
     - `verify_result(result: Any) -> EvidenceReceipt`
     - `health_check() -> HealthStatus`
  2. Enforce 10-layer DLP scan on tool inputs and outputs.
  3. Enforce deterministic timeout bounds (default: 30s; maximum: 120s) and subprocess sandboxing.

### Milestone 3.2: Web Extraction & Headless Browser Adapters (`firecrawl` & `obscure-browser`)
- **Target Clones:** `C:\Users\Ganesh Nair\.gemini\config\skills\firecrawl` & `obscure-browser`
- **Defects Resolved:** Replaces unintegrated skill markdown with real Python tool adapters for web scraping, markdown extraction, and anti-blocking headless browsing.
- **Files to Modify / Create:**
  - `jarvis/tools/adapters/firecrawl_adapter.py`
  - `jarvis/tools/adapters/obscure_browser_adapter.py`
- **Implementation Steps:**
  1. Implement `FirecrawlTool`: wraps Firecrawl local extraction scripts or API fallback to convert HTML pages into clean GitHub-flavored markdown.
  2. Implement `ObscureBrowserTool`: wraps Playwright with stealth user-agents, anti-fingerprinting flags, and SSRF private subnet protection (`127.0.0.1`, `10.0.0.0/8`, `192.168.0.0/16` blocked unless explicitly authorized).
  3. Register tools in `PowerBinder`: `web_extract_markdown` (`PWR-042`) and `web_stealth_scrape` (`PWR-043`).
- **Verification Commands & Criteria:**
  ```powershell
  python -m jarvis.tools.adapters.firecrawl_adapter --url "https://raw.githubusercontent.com/python/cpython/main/README.rst"
  python -m jarvis.tools.adapters.obscure_browser_adapter --url "https://httpbin.org/get"
  ```
  *Pass Criteria:* Returns clean extracted content; generates SHA-256 checksum of extracted text; exit code 0.

### Milestone 3.3: FreeLLMAPI External Cloud Proxy Router Integration (`localhost:3001`)
- **Target Clone:** `C:\Users\Ganesh Nair\.gemini\config\skills\freellmapi`
- **Defects Resolved:** Resolves complete absence of FreeLLMAPI router (`localhost:3001`) across `jarvis/core/model_router.py`. Discloses empirical WAN egress to Groq cloud API.
- **Files to Modify / Create:**
  - `jarvis/core/model_router.py` (Add `FreeLLMAPIProvider` client pointing to `http://localhost:3001` as Tier 3 External Cloud Fallback)
  - `jarvis/tools/adapters/freellmapi_adapter.py` (Standalone verification, Presidio DLP sanitization, and inference tool)
- **Implementation Steps:**
  1. Add configuration parameters to `jarvis/config.py`:
     - `freellmapi_base_url: str = "http://localhost:3001/v1"`
     - `freellmapi_enabled: bool = True`
     - `freellmapi_enforce_dlp: bool = True`
  2. In `jarvis/core/model_router.py`:
     - Classify FreeLLMAPI at `http://localhost:3001` as Tier 3 External Cloud Fallback (proxies over WAN to Groq API).
     - Mandate Presidio DLP sanitization before dispatching prompt tokens to port 3001.
     - Strictly prohibit prompts containing private memory vault data, PII, or credentials from routing to FreeLLMAPI.
     - If unreachable or offline, fail over immediately to local Ollama (`qwen2.5:3b` / `llama3.2:3b`); NEVER emit fake heuristic strings.
- **Verification Commands & Criteria:**
  ```powershell
  python -m jarvis.tools.adapters.freellmapi_adapter --test-inference --prompt "Explain Kahn's algorithm in one sentence"
  ```
  *Pass Criteria:* Returns real LLM response from `http://localhost:3001`; logs model name, latency ms, token count, and 0 external credential leaks.

### Milestone 3.4: Code Discipline & Workflow Migration Adapters (`claude-code-style` & `migrate-workflows`)
- **Target Clones:** `C:\Users\Ganesh Nair\.gemini\config\skills\claude-code-style` & `scripts/migrate_workflows.py`
- **Files to Modify / Create:**
  - `jarvis/tools/adapters/code_style_adapter.py`
  - `jarvis/tools/adapters/workflow_migrator_adapter.py`
- **Implementation Steps:**
  1. Implement `ClaudeCodeStyleTool`: parses and enforces agentic engineering disciplines (minimal-change edits, root cause debugging, test-driven validation) via static AST linters and pre-commit checks.
  2. Implement `WorkflowMigratorTool`: wraps `scripts/migrate_workflows.py` to discover legacy markdown workflow runbooks in `.agents/workflows/*.md` and transform them into structured skill packages (`.agents/skills/<slug>/SKILL.md`) with valid YAML frontmatter and backup rotation.
- **Verification Commands:**
  ```powershell
  python -m jarvis.tools.adapters.code_style_adapter --check-file jarvis/core/orchestrator.py
  ```

### Milestone 3.5: Generative UI & Plugin Extensibility Adapters (`generative_ui` & `plugin`)
- **Target Clones:** `generative_ui` & `plugin`
- **Files to Modify / Create:**
  - `jarvis/tools/adapters/generative_ui_adapter.py`
  - `jarvis/tools/adapters/plugin_loader_adapter.py`
- **Implementation Steps:**
  1. Implement `GenerativeUITool`: generates dynamic JSON schemas and React/HTML component descriptors for rendering interactive HUD widgets, data tables, and approval dialogues.
  2. Implement `PluginLoaderTool`: safely scans, validates manifests, and registers modular third-party MCP or Python tools into `jarvis/tools/registry.py` under privilege isolation.
- **Verification Commands:**
  ```powershell
  python -m jarvis.tools.adapters.generative_ui_adapter --schema-type "task_progress"
  ```

### Milestone 3.6: Cloned Capabilities Independent Test Harness
- **Target Subsystem:** `tests/integration/test_cloned_capabilities.py`
- **Scope:** Independent test suite executing all 7 adapters outside Antigravity.
- **Verification Commands:**
  ```powershell
  pytest tests/integration/test_cloned_capabilities.py -v
  ```
  *Pass Criteria:* All 7 adapter tests execute; report valid statuses or graceful offline fallbacks; zero simulated passes.

---

## 4. Stage 4: Canonical Multi-Agent Workforce

**Objective:** Dismantle all superficial agent mocks, purge the 105 fake dataclass counter, and establish the canonical multi-agent workforce governed by dynamic lifecycles, LangGraph DAG execution, Kahn's algorithm cycle detection, SHA-256 audit chaining, and the 8-layer unified memory vault.

### Milestone 4.1: Purge Superficial Mocks, Fake Dataclasses, and Test Cheats
- **Target Subsystem:** `jarvis/agents/`, `jarvis/integrations/`, `core/`
- **Defects Resolved:** Eradicates Second Law violations across the codebase.
- **Files to Modify / Delete:**
  - `jarvis/agents/autonomous_workforce.py` (Purge `_initialize_105_agent_fleet` lines 62-101 and manual status flipping loops)
  - `jarvis/agents/ruflo_swarm.py` (Delete lines 86-118 substring voting heuristics)
  - `jarvis/integrations/career_ops.py` (Purge `"%PDF-1.4 Mock ATS Resume"` and hardcoded job dictionaries)
  - `jarvis/powers/multiagent_powers.py` (Purge fake `TrustResult` in `invoke_subagent` lines 89-108)
- **Implementation Steps:**
  1. Remove hardcoded test responses and simulated sleep patterns.
  2. Implement honest failure paths: if an agent role has no model backend or API key, return `TrustResult.failure("Agent backend unconfigured")`.
  3. Replace fake PDF generation with real ReportLab/Jinja2 PDF rendering engine.
- **Verification Commands:**
  ```powershell
  # Search codebase to confirm zero occurrences of mock cheat strings
  Select-String -Path "jarvis\**\*.py" -Pattern "Mock ATS Resume", "status = .ACTIVE."
  ```
  *Pass Criteria:* 0 occurrences of test-gaming cheat strings found.

### Milestone 4.2: Dynamic Agent Lifecycle Management
- **Target Subsystem:** `jarvis/agents/lifecycle.py` & `jarvis/db/models/agent.py`
- **Files to Modify / Create:**
  - `jarvis/agents/lifecycle.py` (New dynamic lifecycle controller: `AgentLifecycleManager`)
  - `jarvis/db/models/agent.py` (Update SQLAlchemy model to match `DATABASE_HIPPOCAMPUS.md`)
- **Implementation Steps:**
  1. Implement dynamic lifecycle states:
     - `UNINITIALIZED -> SPAWNING -> ACTIVE -> PAUSED -> RETIRED`.
  2. Enforce on-demand instantiation:
     - Worker agents are spawned only when an active DAG node requires their specialized tool set.
     - Workers yield/pause during I/O waits, releasing VRAM and memory buffers.
     - Completed workers transition to `RETIRED`, persisting execution traces into episodic memory.
  3. Enforce concurrency throttle: strictly bound active concurrent worker processes to **max 2–3** to respect the 6 GB VRAM and 24 GB RAM limits.
- **Verification Commands & Criteria:**
  ```powershell
  pytest tests/test_agent_lifecycle.py -v
  ```
  *Pass Criteria:* Agents spawn on demand, execute tasks, transition to RETIRED; zero orphaned background processes.

### Milestone 4.3: CEO Central Routing & 6 Departmental Workflows
- **Target Subsystem:** `jarvis/core/task_router.py` & `jarvis/departments/`
- **Files to Modify / Create:**
  - `jarvis/core/task_router.py` (Wire CEO Router to LangGraph controller)
  - `jarvis/departments/` (Implement real department coordinators: `hackathon`, `career`, `research`, `engineering`, `security`, `operations`)
- **Implementation Steps:**
  1. Implement CEO Central Routing principle ("Rule 2: One Boss — Tasks do not choose agents; the CEO assigns agents through Department Managers").
  2. Wire the 6 functional departments:
     - **Hackathon:** Scrapes live hackathons, analyzes problem statements, generates runnable scaffolds.
     - **Career:** Ingests resumes, matches job openings, computes real ATS scores via local LLM.
     - **Research:** Conducts multi-source search, extracts verbatim citations, synthesizes trade-off reports.
     - **Engineering:** Generates modular code, runs pytest test suites, enforces AST code quality.
     - **Security:** Audits DLP filters, scans entropy secrets, validates Merkle tree integrity.
     - **Operations:** Monitors RTX 4050 GPU VRAM, supervises background daemons, rotates keys.
- **Verification Commands:**
  ```powershell
  pytest tests/test_departments.py -v
  ```

### Milestone 4.4: LangGraph DAG Engine Hardening with Cycle Detection
- **Target Subsystem:** `jarvis/brain/graph.py` & `jarvis/brain/task_graph.py`
- **Files to Modify / Create:**
  - `jarvis/brain/task_graph.py` (DAG execution engine using Kahn's algorithm)
  - `jarvis/brain/graph.py` (Authoritative 8-node LangGraph state machine)
- **Implementation Steps:**
  1. Implement cycle detection using Kahn's algorithm:
     - Compute in-degrees of all DAG nodes.
     - Detect circular dependencies immediately; abort graph before execution with `CyclicDependencyError`.
  2. Implement parallel wave scheduling:
     - Partition independent nodes into concurrent waves.
     - Throttle execution waves to `max_concurrency=3`.
  3. Implement cascaded failure handling:
     - If a task node exhausts retries (default: 3), mark node `FAILED` and cascade `CANCELLED` status to all dependent children.
- **Verification Commands:**
  ```powershell
  pytest tests/test_task_graph_engine.py -v
  ```
  *Pass Criteria:* Valid DAGs execute in dependency order; circular DAGs are rejected instantly with clear cycle trace.

### Milestone 4.5: Evidence-Based Verification Gate & SHA-256 Chained Audit Ledger
- **Target Subsystem:** `jarvis/core/evidence.py`, `jarvis/core/audit.py`, `jarvis/security/ten_layer_shield.py`
- **Files to Modify / Create:**
  - `jarvis/core/evidence.py` (Enforce `Evidence` and `TrustResult` data structures)
  - `jarvis/core/audit.py` (Append-only cryptographic SHA-256 chained transaction log)
  - `jarvis/security/ten_layer_shield.py` (Presidio DLP regex, AES-256 vault, ephemeral HMAC-SHA256 approvals)
- **Implementation Steps:**
  1. Enforce First Law verification gate on every task completion:
     - `TaskVerifier` inspects output completeness, checks for presence of required evidence artifacts, and runs DLP scan.
     - Tasks without evidence cannot transition to `COMPLETED`.
  2. Implement cryptographic SHA-256 hash chaining:
     - Each audit log entry computes: `entry_hash = SHA256(payload + previous_entry_hash)`.
     - Tampering with any log entry breaks the hash chain and triggers a security alert.
  3. Enforce HMAC-SHA256 single-use tokens for sensitive Tier 3 actions (shell commands, file deletions, code merges).
- **Verification Commands:**
  ```powershell
  pytest tests/test_audit_ledger.py tests/test_ten_layer_shield.py -v
  ```
  *Pass Criteria:* Tampering with audit entries is detected; unverified tasks fail verification gate; DLP redacts secrets.

### Milestone 4.6: 8-Layer Unified Memory Vault & Fourth Law Reflection Gate
- **Target Subsystem:** `jarvis/memory/` (`store.py`, `models.py`, `reflection.py`)
- **Defects Resolved:** Consolidates 4 fragmented databases into a single SQLite WAL database and implements Fourth Law reflection persistence.
- **Files to Modify / Create:**
  - `jarvis/memory/store.py` (Unified memory store with SQLite WAL + FTS5 full-text search)
  - `jarvis/memory/reflection.py` (Fourth Law retrospective persistence engine)
  - `jarvis/db/migrations/` (Unify Alembic migrations to apply all 10 domain revisions)
- **Implementation Steps:**
  1. Consolidate memory tables into single `data/jarvis.db`:
     - `Working`, `Conversation`, `Episodic`, `Semantic`, `Procedural`, `Knowledge`, `Identity`, `Correction`.
  2. Implement FTS5 keyword indexing and local dense vector embeddings (`nomic-embed-text` via Ollama).
  3. Enforce Fourth Law Gate:
     - No goal, project, or task graph may reach `COMPLETED` status until a verifiable reflection record (lessons learned, failures, verified successes, capability gaps) is persisted to `reflections` table.
     - If reflection record is missing, mark goal `INCOMPLETE` with `fourth_law_compliant=false`.
- **Verification Commands:**
  ```powershell
  pytest tests/test_unified_memory.py -v
  alembic upgrade head
  ```
  *Pass Criteria:* All 10 Alembic revisions apply; FTS5 search queries return results in < 5ms; reflections persist across database restarts.

---

## 5. Stage 5: Always-On Personal AI Operating System

**Objective:** Transition JARVIS into an autonomous, always-on personal operating system running reliably in the Windows 11 background, proactively monitoring opportunities, providing multi-monitor screen awareness, serving the WebSocket HUD, and managing self-improvement.

### Milestone 5.1: Proactive Background Scheduler & Autonomous Radar
- **Target Subsystem:** `jarvis/core/scheduler.py`
- **Files to Modify / Create:**
  - `jarvis/core/scheduler.py` (Async cron-like autonomous scheduler)
  - `jarvis/radar/` (`hackathon_radar.py`, `career_radar.py`, `research_radar.py`)
- **Implementation Steps:**
  1. Configure scheduled background jobs with low CPU/GPU footprints:
     - Nightly Hackathon Radar: Scrapes Devfolio and Unstop for eligible AI/systems hackathons.
     - Weekly Career Radar: Tracks GSoC organizations, open-source repositories, and targeted internship postings.
     - Daily arXiv Research Radar: Fetches recent pre-prints on LLM reasoning and agent systems.
  2. Persist genuine findings directly into the SQLite `opportunities` table with evidence links.
  3. Enforce Second Law: zero fabricated opportunity entries.
- **Verification Commands:**
  ```powershell
  python -m jarvis.core.scheduler --run-once hackathon_radar
  ```
  *Pass Criteria:* Genuine hackathons saved to database with real URLs and verified deadlines.

### Milestone 5.2: See-Act-Verify UI Worker & Multi-Monitor Awareness
- **Target Subsystem:** `jarvis/tools/desktop/screen.py` & `jarvis/tools/desktop/ui_worker.py`
- **Files to Modify / Create:**
  - `jarvis/tools/desktop/screen.py` (Multi-monitor capture, active window tracking, OCR)
  - `jarvis/tools/desktop/ui_worker.py` (See-Act-Verify desktop automation loop)
- **Implementation Steps:**
  1. Multi-monitor screenshot capture using `mss` with per-window bounding boxes.
  2. Visual DLP: Automatically mask and blur password fields, secret keys, and personal banking windows before passing screenshots to vision models.
  3. Implement See-Act-Verify loop:
     - Observe display state -> Plan UI interaction -> Check Policy Gate -> Actuate -> Verify visual diff -> Write audit log.
  4. Physical Failsafe: Emergency mouse-corner flick or `Ctrl+Alt+Shift+K` hotkey instantly halts automation within 50ms.
- **Verification Commands:**
  ```powershell
  python -m jarvis.tools.desktop.screen --capture-active-window --out data/screen_test.png
  ```

### Milestone 5.3: Mission-Control HUD & Telemetry Dashboard
- **Target Subsystem:** `jarvis/api/server.py` & `jarvis/dashboard/`
- **Files to Modify / Create:**
  - `jarvis/api/server.py` (WebSocket telemetry streamer at `/ws/stream`)
  - `jarvis/dashboard/` (Consolidated dark-mode glassmorphic single-page UI)
- **Implementation Steps:**
  1. Consolidate duplicate dashboard files into `jarvis/dashboard/index.html`.
  2. Implement real-time WebSocket telemetry stream broadcasting:
     - Host CPU %, RAM utilization, RTX 4050 VRAM usage (via `pynvml`), active worker count, live audit ledger stream.
  3. Display active task execution status, two-stage voice indicators, and human approval prompts.
- **Verification Commands:**
  ```powershell
  # Launch API server and test WebSocket connection
  python -m uvicorn jarvis.api.server:app --port 8000
  ```

### Milestone 5.4: Windows Native Background Service Startup & Tray Failsafe
- **Target Subsystem:** `jarvis/ops/` (`windows_service.py`, `tray_app.py`)
- **Files to Modify / Create:**
  - `jarvis/ops/windows_service.py` (Windows Task Scheduler / Service manager script)
  - `jarvis/ops/tray_app.py` (System tray icon with status indicators and emergency kill switch)
- **Implementation Steps:**
  1. Create automated PowerShell installer to register JARVIS in Windows Task Scheduler:
     - Run on user login with high privileges.
     - Auto-restart on failure (max 3 retries within 10 minutes).
  2. Implement lightweight Windows system tray application (`pystray`):
     - Visual state: Green (Active/Listening), Yellow (Executing Task), Red (Killed/Locked).
     - Menu options: Open HUD, Pause Listening, View Audit Log, Emergency Kill Switch.
- **Verification Commands:**
  ```powershell
  python -m jarvis.ops.tray_app --test-launch
  ```

### Milestone 5.5: Governed Self-Improvement & Safe PR Workflow
- **Target Subsystem:** `jarvis/workflows/pr_workflow.py` & `jarvis/self_improvement/`
- **Files to Modify / Create:**
  - `jarvis/workflows/pr_workflow.py` (`SafePRWorkflowManager`)
- **Implementation Steps:**
  1. Enforce Safe PR state machine: `PROPOSED -> PLANNED -> GENERATED -> TESTING -> SECURITY_REVIEW -> AWAITING_APPROVAL -> APPROVED -> MERGED`.
  2. Physical Inviolable Guard: `validate_branch_target()` raises `SecurityViolationError` if any automated agent attempts `git push origin main`.
  3. Automated self-improvements must be committed to isolated feature branches (`feature/imp-{id}`) and require Ganesh's manual review and merge.
- **Verification Commands:**
  ```powershell
  pytest tests/test_safe_pr_workflow.py -v
  ```
  *Pass Criteria:* Autonomous push to `main` is blocked and raises `SecurityViolationError`; pull requests on feature branches require explicit human approval token.

---

## 6. Subsystem Dependency & Traceability Matrix

| Milestone | Stage | Dependencies | Exact Files Impacted | Key Constitutional Mandates Enforced |
|---|---|---|---|---|
| **M1.1: Vision & Gap Audit** | Stage 1 | Survey Reports | `docs/JARVIS_VISION_VS_IMPLEMENTATION_AUDIT.md` | First Law, Second Law, Top 10 Critical Gaps |
| **M1.2: Canonical Architecture** | Stage 1 | M1.1 | `docs/JARVIS_CANONICAL_ARCHITECTURE.md` | 12 Systems, LangGraph 8-Node DAG, Separation of Powers |
| **M1.3: Cloned Capability Inventory** | Stage 1 | FreeLLMAPI probe | `docs/JARVIS_CLONED_CAPABILITY_INVENTORY.md` | Clone Analysis, Port 3001 Verification |
| **M1.4: Structural Unification** | Stage 1 | M1.2 | `jarvis/`, `core/`, `graph/`, `search/`, `pyproject.toml` | Clean Packaging, Root Shadow Tree Removal |
| **M2.1: Physical Mic & VAD** | Stage 2 | M1.4, Win32 Audio | `jarvis/voice/capture.py`, `vad.py`, `pyproject.toml` | Real Audio Capture, Hardware Error Telemetry |
| **M2.2: Acoustic Wake Engine** | Stage 2 | M2.1 | `jarvis/voice/wake.py`, `models/hey_jarvis.onnx` | Local openWakeWord, <500ms Latency |
| **M2.3: Local Transcription** | Stage 2 | M2.1 | `jarvis/voice/stt.py` | Faster-Whisper on CUDA, Zero Mock Fallback |
| **M2.4: Two-Stage Conversation** | Stage 2 | M2.2, M2.3 | `jarvis/voice/conversation_loop.py`, `core/orchestrator.py` | Two-Stage Interaction State Machine |
| **M2.5: Real Desktop Tool (Notepad)** | Stage 2 | M2.4 | `jarvis/tools/desktop/notepad.py`, `win32_window.py` | Win32 Window Buffer Extraction & SHA-256 Receipt |
| **M2.6: Local Neural TTS** | Stage 2 | M2.1 | `jarvis/voice/tts.py` | Kokoro-ONNX / Windows SAPI, Zero Sine Beeps |
| **M2.7: P0 End-to-End Verification** | Stage 2 | M2.1–M2.6 | `tests/manual/verify_p0_voice_notepad.py` | Independent Verification Outside Antigravity |
| **M3.1–M3.6: Cloned Capabilities** | Stage 3 | M1.3, M1.4 | `jarvis/tools/adapters/*.py`, `tests/integration/` | Real Tool Adapters, Firecrawl, Port 3001 Router |
| **M4.1–M4.6: Canonical Workforce** | Stage 4 | M1.4, M3.1 | `jarvis/agents/`, `brain/`, `memory/`, `security/` | Dynamic Lifecycle, Kahn's Algo, SHA-256 Chaining, Fourth Law |
| **M5.1–M5.5: Always-On OS** | Stage 5 | M4.1–M4.6 | `jarvis/core/scheduler.py`, `dashboard/`, `ops/` | Proactive Radar, Multi-Monitor HUD, Windows Service |

---

## 7. Execution Timeline & Governance

```text
Week 1: Stage 1 (Architecture Audit & Structural Consolidation)
 ├── Milestones 1.1 - 1.3: Audit & Architecture Deliverables Complete [CURRENT]
 └── Milestone 1.4: Root shadow tree elimination and package consolidation
Week 2: Stage 2 (P0 Hey Jarvis Voice Activation)
 ├── Milestones 2.1 - 2.3: Audio capture, openWakeWord, faster-whisper integration
 ├── Milestones 2.4 - 2.6: Two-stage interaction, Win32 Notepad typing/verification, Kokoro TTS
 └── Milestone 2.7: Full P0 hardware verification outside Antigravity
Week 3: Stage 3 (Seven Cloned Capabilities Integration)
 ├── Milestones 3.1 - 3.3: Base tool adapter, Firecrawl/ObscureBrowser, FreeLLMAPI router
 └── Milestones 3.4 - 3.6: Code style, workflow migrator, Generative UI, independent tests
Week 4: Stage 4 (Canonical Multi-Agent Workforce)
 ├── Milestones 4.1 - 4.3: Mock purge, dynamic agent lifecycle, CEO router & 6 departments
 └── Milestones 4.4 - 4.6: LangGraph DAG engine, SHA-256 audit ledger, 8-layer unified memory
Week 5: Stage 5 (Always-On Personal AI Operating System)
 ├── Milestones 5.1 - 5.3: Autonomous radar scheduler, screen worker, glassmorphic HUD
 └── Milestones 5.4 - 5.5: Windows service background startup, safe PR self-improvement
```

**Definition of Done (DoD) for Any Milestone:**
1. Code authored adheres to minimal-change principles and follows existing type-annotated style.
2. Zero mock fallbacks, zero synthetic test passes, and zero simulated counters.
3. Relevant unit and integration tests pass via native PowerShell/pytest outside Antigravity.
4. An immutable `EvidenceReceipt` is generated, including PIDs, exit codes, and SHA-256 hashes.
5. All changes committed to an isolated feature branch and documented in the system audit ledger.
