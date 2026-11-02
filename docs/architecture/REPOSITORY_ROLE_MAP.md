# JARVIS External Repository & Pattern Role Map

**Generated:** 2026-11-03  
**Audit Branch:** `audit/capability-audit`  
**Purpose:** Evidence-based mapping between claimed external repository integrations, actual on-disk code, and production reachability.

---

## 1. Overview of Claimed vs. Actual Integrations

Project documentation, configuration catalogs (`config/powers/master_powers_355.json`), and previous architectural summaries claimed integration with **14 external open-source repositories and architectures**. 

A strict physical directory audit confirms:
- **`repos/` directory status:** **NOT FOUND**. The root path `C:\Users\Ganesh Nair\.gemini\antigravity\scratch\Jarvis\repos` does not exist on disk (`Test-Path` returned `False`).
- **Vendored Code:** Zero lines of foreign vendor repositories are cloned or vendored directly.
- **Pattern Adaptation:** The codebase consists of native Python reimplementations, stubs, and wrappers that borrow nomenclature, prompt templates, or conceptual APIs from these repositories.

Below is the exhaustive, item-by-item audit of each claimed repository.

---

## 2. Detailed Repository Role Inventory

### 1. OpenMausBot
- **Source:** [OpenMaus / open-maus-bot](https://github.com/openmaus) multi-bot Slack/Discord agent framework.
- **Claimed Integration:** Multi-bot agent roster (GrokBot, CodeMaus, ScoutMaus, OpsMaus, ReflexMaus), dual-engine fallback, multi-channel event router (`#general`, `#dev`, `#research`, `#ops`), and single-use cryptographic permission broker.
- **Actual Code on Disk:**
  - `jarvis/core/openmaus_grok.py` (458 lines): Defines `OpenMausBot`, `OpenMausAgentRoster`, `OpenMausPermissionBroker`, and `OpenMausGrokHarness`.
  - `jarvis/api/routes_grok.py` (93 lines): Mounted at `/api/v1/grok` with endpoints `/chat`, `/roster`, `/channels`, `/events`, `/approvals/pending`, and `/approvals/resolve`.
  - Persona dictionaries: Defined as static text prompts in `GROK_PERSONAS` (`jarvis/core/openmaus_grok.py:100-168`).
- **Production Reachability:**
  - **PARTIAL**: The route `POST /api/v1/grok/chat` is reachable in FastAPI (`jarvis/api/server.py:40`).
  - **Runtime Reality:** Invoking `POST /api/v1/grok/chat` does NOT execute sub-agents or tasks. It runs a single-turn text completion via `groq_rotator`, `openrouter_rotator`, or local `model_router`.
  - **Permission Broker Reality:** `self.broker.inspect_action()` is never invoked within `chat()`. The permission broker exists purely as an uncalled class with unit tests (`tests/test_openmaus_grok.py`).
  - **Bot Autonomy Reality:** The bots cannot poll, accept delegated DAG tasks, or run asynchronously. They are static system prompt overrides for standard LLM completion.

---

### 2. Kokoro-TTS
- **Source:** [Kokoro-82M](https://github.com/hexgrad/kokoro) open-weight neural text-to-speech model.
- **Claimed Integration:** High-fidelity, low-latency, local neural TTS engine running without cloud dependencies.
- **Actual Code on Disk:**
  - `jarvis/voice/tts.py` (176 lines): TextToSpeech class.
  - Inspecting lines 1–60 reveals:
    - ElevenLabs REST API (`https://api.elevenlabs.io/v1/text-to-speech`)
    - Windows native SAPI (`win32com.client.Dispatch("SAPI.SpVoice")`)
    - Pure Python fallback generating synthetic sine-wave PCM audio into a WAV buffer.
  - **Kokoro Code:** **NOT FOUND**. The string `kokoro` does not appear anywhere in `jarvis/voice/tts.py`. It is only referenced as an aspirational string in test mocks (`tests/test_architectural_blueprint.py`, `tests/test_database_repositories.py`).
- **Production Reachability:**
  - **DEAD / NOT FOUND**: The Kokoro engine does not exist in the codebase. Audio synthesis defaults to Windows SAPI (if COM is available) or a sine-wave beep fallback.

---

### 3. RuFlo
- **Source:** [ruvnet/ruflo](https://github.com/ruvnet/ruflo) distributed multi-agent consensus and swarm coordination engine.
- **Claimed Integration:** Decentralized multi-agent consensus voting, agent reputation scoring, and quorum thresholds for high-risk operations.
- **Actual Code on Disk:**
  - `jarvis/agents/ruflo_swarm.py` (157 lines): Implements `RuFloConsensusSwarm`, `SwarmVote`, and `ConsensusDecision`. Contains static reputation weights for `sec_auditor_01`, `arch_reviewer_01`, `devops_gate_01`, etc.
- **Production Reachability:**
  - **DORMANT / UNREACHABLE**: Zero production routes, schedulers, or orchestrators import `RuFloConsensusSwarm`. It is imported exclusively in `tests/test_career_autofill_and_ruflo.py`.

---

### 4. atticus-mac
- **Source:** Atticus macOS personal assistant (push-to-talk, menu-bar actions, instant commands).
- **Claimed Integration:** `handler_module: jarvis.powers.instant_local`, `primary_file: repos/atticus-mac/atticus.py`. Powers PWR-001 through PWR-015.
- **Actual Code on Disk:**
  - `repos/atticus-mac/`: **NOT FOUND**.
  - `jarvis.powers.instant_local`: **NOT FOUND**.
  - `jarvis/powers/instant_powers.py` (377 lines): Contains native Python methods using `os.system`, `ctypes`, and `psutil` (e.g., volume control, app launching, clipboard reading).
- **Production Reachability:**
  - **ACTIVE**: `InstantPowers` is imported by `jarvis/core/power_registry.py` and called by `model_router.py` when intent bypasses LLM inference.

---

### 5. browser-use
- **Source:** [browser-use / browser-use](https://github.com/browser-use/browser-use) autonomous web browsing agent.
- **Claimed Integration:** `handler_module: jarvis.browser.research_worker`, `primary_file: repos/browser-use/browser_use/agent/service.py`. Powers PWR-063 to PWR-075.
- **Actual Code on Disk:**
  - `repos/browser-use/`: **NOT FOUND**.
  - `jarvis/browser/research_worker.py` (253 lines): Native implementation using Playwright directly via `BrowserContextManager` (`jarvis/browser/context_manager.py`). Does not import or depend on `browser_use` package.
  - `jarvis/browser/url_reader.py` (160 lines): Custom DOM text extraction and regex-based prompt injection detection.
- **Production Reachability:**
  - **ACTIVE**: Reachable via `POST /api/v1/browser/research` (`jarvis/api/routes_browser.py:100`).

---

### 6. career-ops
- **Source:** Career automation scripts for internship applications, resume parsing, and outreach.
- **Claimed Integration:** `handler_module: jarvis.integrations.career_ops`, `primary_file: repos/career-ops/skills`. Powers PWR-328 to PWR-337.
- **Actual Code on Disk:**
  - `repos/career-ops/`: **NOT FOUND**.
  - `jarvis.integrations.career_ops`: **NOT FOUND** (`jarvis/integrations` package does not exist).
  - Actual implementation located in:
    - `jarvis/career/service.py` (220 lines)
    - `jarvis/career/form_autofill_agent.py` (405 lines)
    - `jarvis/career/scanner.py` (130 lines)
    - `jarvis/powers/career_powers.py` (230 lines)
- **Production Reachability:**
  - **ACTIVE**: Reachable via `jarvis/api/routes_career.py` (`POST /api/v1/career/scan`, `POST /api/v1/career/apply`).
  - Note: `form_autofill_agent.py` uses Playwright to fill job applications; tested in `tests/test_career_autofill_and_ruflo.py`.

---

### 7. cua (Computer Use Agent)
- **Source:** Anthropic Computer Use Agent / CUA sandbox reference architecture.
- **Claimed Integration:** `handler_module: jarvis.computer.sandbox`, `primary_file: repos/cua/libs/core`. Powers PWR-016 to PWR-026.
- **Actual Code on Disk:**
  - `repos/cua/`: **NOT FOUND**.
  - `jarvis.computer.sandbox`: **NOT FOUND** (`jarvis/computer` directory does not exist).
  - Actual implementation: `jarvis/powers/screen_powers.py` (460 lines) and `jarvis/powers/desktop_powers.py` (72 lines). Uses `pyautogui` and `win32gui` for screenshot capture and mouse coordinates.
- **Production Reachability:**
  - **ACTIVE**: Powers are registered in `power_registry.py` and callable via `/api/v1/desktop/click` and `/api/v1/desktop/screenshot`.

---

### 8. hermes-agent
- **Source:** NousResearch Hermes Agent long-term memory vault and function calling schemas.
- **Claimed Integration:** `handler_module: jarvis.memory.hermes_vault`, `primary_file: repos/hermes-agent/agent/skills.py`.
- **Actual Code on Disk:**
  - `repos/hermes-agent/`: **NOT FOUND**.
  - `jarvis.memory.hermes_vault`: **NOT FOUND**.
  - Actual memory implementation: `jarvis/memory/layers.py` (7-layer SQLite memory store) and `jarvis/memory/mem0_client.py` (`LocalMem0Adapter`).
- **Production Reachability:**
  - **ACTIVE**: The memory layer is active through `LocalMem0Adapter` and `db_store`, but has no code derived from `hermes-agent`.

---

### 9. mcp-servers
- **Source:** Model Context Protocol (MCP) reference server catalog.
- **Claimed Integration:** `handler_module: jarvis.mcp_gateway`, `primary_file: repos/mcp-servers/src`.
- **Actual Code on Disk:**
  - `repos/mcp-servers/`: **NOT FOUND**.
  - `jarvis.mcp_gateway`: **NOT FOUND**.
  - `jarvis/core/mcp_client.py` (150 lines): Implements a basic stdio client for spawning MCP subprocesses and JSON-RPC messaging.
- **Production Reachability:**
  - **DORMANT**: `mcp_client.py` is tested in `tests/test_mcp_client.py`, but is never initialized or invoked by `server.py` or any mounted router.

---

### 10. open-interpreter
- **Source:** [open-interpreter / open-interpreter](https://github.com/open-interpreter/open-interpreter) local code execution and desktop control.
- **Claimed Integration:** `handler_module: jarvis.powers.desktop_powers`, `primary_file: repos/open-interpreter/interpreter`.
- **Actual Code on Disk:**
  - `repos/open-interpreter/`: **NOT FOUND**.
  - `jarvis/powers/developer_powers.py` (520 lines): Contains native Python methods to execute bash/cmd subshells with timeout and stdout capture (`PWR-305`).
- **Production Reachability:**
  - **ACTIVE**: Reachable via developer powers registry and tested in `tests/test_developer_powers.py`. Does not vendor or import Open-Interpreter.

---

### 11. open-jarvis
- **Source:** Open-Jarvis multimodal multimodal agent framework.
- **Claimed Integration:** `handler_module: jarvis.graph.jarvis_graph`, `primary_file: repos/open-jarvis/configs`.
- **Actual Code on Disk:**
  - `repos/open-jarvis/`: **NOT FOUND**.
  - `graph/jarvis_graph.py` (294 lines): Custom LangGraph StateGraph implementation with 8 nodes (`perceive`, `recall`, `plan`, `policy`, `act`, `verify`, `reflect`, `remember`).
- **Production Reachability:**
  - **ACTIVE**: Mounted as primary cognitive graph in `jarvis/api/server.py:346` (`POST /chat`).

---

### 12. openclaw
- **Source:** OpenClaw robotic / GUI operating harness.
- **Claimed Integration:** `handler_module: jarvis.integrations.openclaw`, `primary_file: repos/openclaw/skills`.
- **Actual Code on Disk:**
  - `repos/openclaw/`: **NOT FOUND**.
  - `jarvis.integrations.openclaw`: **NOT FOUND**.
  - Pure metadata artifact: only appears in `config/powers/master_powers_355.json` as a `contributing_repos` label.
- **Production Reachability:**
  - **DEAD / NOT FOUND**: No executable code or wrapper exists.

---

### 13. openhands (formerly OpenDevin)
- **Source:** [All-Hands-AI / OpenHands](https://github.com/All-Hands-AI/OpenHands) autonomous software development agent.
- **Claimed Integration:** `handler_module: jarvis.powers.developer_powers`, `primary_file: repos/openhands/openhands`.
- **Actual Code on Disk:**
  - `repos/openhands/`: **NOT FOUND**.
  - `jarvis/powers/developer_powers.py`: Implements AST parsing, Git repository operations, and test runner wrappers natively using Python's standard `ast`, `git` (or subshell `git`), and `pytest`.
- **Production Reachability:**
  - **ACTIVE**: `developer_powers.py` is actively used in `TaskExecutor` pipelines and `test_developer_powers.py`. No OpenHands code is present.

---

### 14. ui-tars-desktop
- **Source:** [ByteDance / UI-TARS](https://github.com/bytedance/ui-tars) vision-language GUI agent.
- **Claimed Integration:** Vision-based GUI automation via local VLM.
- **Actual Code on Disk:**
  - `repos/ui-tars-desktop/`: **NOT FOUND**.
  - Mentioned in `jarvis/capabilities/registry.py` and `jarvis/api/routes/reflections.py` as a placeholder string capability.
  - Coordinate clicking is implemented via `pyautogui` in `jarvis/powers/screen_powers.py`. No local vision-language model (VLM) is connected or downloaded.
- **Production Reachability:**
  - **DORMANT / PLACEHOLDER**: Coordinate execution exists, but multimodal UI-TARS model reasoning is NOT FOUND.

---

## 3. Summary Map

| External Repository | Claimed Handler Path | Real Code Path | Real Status | Reality Classification |
| :--- | :--- | :--- | :--- | :--- |
| **OpenMausBot** | `jarvis.core.openmaus_grok` | `jarvis/core/openmaus_grok.py` | ACTIVE | Prompt personas + LLM router (no autonomous bot workers) |
| **Kokoro-TTS** | `jarvis.voice.tts` | `jarvis/voice/tts.py` | NOT FOUND | SAPI + ElevenLabs + Sine PCM (Kokoro not present) |
| **RuFlo** | `jarvis.agents.ruflo_swarm` | `jarvis/agents/ruflo_swarm.py` | DORMANT | Class exists, tested in isolation, 0 production callers |
| **atticus-mac** | `repos/atticus-mac` | `jarvis/powers/instant_powers.py` | ACTIVE | Native Windows/OS commands, no external repo |
| **browser-use** | `repos/browser-use` | `jarvis/browser/research_worker.py` | ACTIVE | Native Playwright wrapper, no browser-use library |
| **career-ops** | `jarvis.integrations.career_ops` | `jarvis/career/service.py` | ACTIVE | Native Pydantic + Playwright service |
| **cua** | `jarvis.computer.sandbox` | `jarvis/powers/screen_powers.py` | ACTIVE | Native PyAutoGUI / Win32 stubs |
| **hermes-agent** | `jarvis.memory.hermes_vault` | `jarvis/memory/layers.py` | ACTIVE | Native SQLite 7-layer schema |
| **mcp-servers** | `jarvis.mcp_gateway` | `jarvis/core/mcp_client.py` | DORMANT | Unused stdio subprocess wrapper |
| **open-interpreter**| `repos/open-interpreter` | `jarvis/powers/developer_powers.py`| ACTIVE | Native `subprocess` execution |
| **open-jarvis** | `repos/open-jarvis` | `graph/jarvis_graph.py` | ACTIVE | Native LangGraph 8-node state machine |
| **openclaw** | `jarvis.integrations.openclaw` | None | NOT FOUND | Label in JSON catalog only |
| **openhands** | `repos/openhands` | `jarvis/powers/developer_powers.py`| ACTIVE | Native AST and subshell scripts |
| **ui-tars-desktop** | `repos/ui-tars-desktop` | `jarvis/powers/screen_powers.py` | DORMANT | PyAutoGUI coordinate clicks; no VLM |
