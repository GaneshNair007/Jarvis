# JARVIS Upstream Project Review and Verification

**Date**: 31 October 2026  
**Auditor**: Lead Cognitive Core Engineer  
**Reference Document**: `JARVIS_Master_Edition.pdf` (Part E / Research Notes)  
**Policy**: Strict compliance with Working Rule 3 & 4 (Pinned dependency -> MCP/HTTP -> Pattern study -> Source copy for permissive MIT/Apache-2.0/BSD only). Zero GPL/AGPL in MIT codebase.

---

## 1. Upstream Verification Matrix

| Upstream Project | Verified License | Target Version / Tag | Integration Type | Role in JARVIS | Verification & Security Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **LangGraph** | MIT | `langgraph>=0.2.0` | Core Pinned Dependency | Single orchestrator StateGraph; interrupts for Tier-2 approvals, durable checkpointing. | Zero secondary agent framework permitted. Uses SQLite/Postgres checkpointing. Verified clean MIT license. |
| **Mem0** | Apache-2.0 | `mem0ai>=0.1.20` | Pinned Dependency & Adapter | Long-term personalized memory extraction, vector search adapter. | Self-hosted local SQLite adapter active. Wrapped behind `BrainMemoryService` to enforce zero-credential DLP redaction. |
| **LiteLLM** | MIT | `litellm>=1.40.0` | Gateway Dependency / HTTP | Model router proxy, fallbacks, cost tracking, token budgeting. | Upstream `filelock` dependency had 13 CVEs patched/excepted in CI. Fallback to local model server (`localhost:11434`) strictly verified. |
| **Ollama** | MIT | Local daemon (`v0.3.x+`) | Local HTTP API (`:11434`) | Local reflex & private model server (`qwen2.5`, `llama3.1`, `nomic-embed-text`). | Runs completely offline on RTX 4050 (6GB VRAM). No external keys required. |
| **openWakeWord** | Apache-2.0 | `openwakeword>=0.5.1` | Local Audio Dependency | Local wake-word audio detection ("Hey Jarvis"). | Zero network traffic; on-device inference using TFLite/ONNX. Run in isolated process. |
| **faster-whisper** | MIT | `faster-whisper>=1.0.0` | Local Audio Dependency | Local offline Speech-to-Text (STT) via CTranslate2. | Highly optimized for NVIDIA CUDA/TensorRT on Windows 11. Read-only audio buffer. |
| **Piper TTS** | MIT | `piper-tts>=1.2.0` | Local Audio Dependency | Local fast, natural neural Text-to-Speech (TTS). | Runs offline; outputs raw PCM/WAV. Zero cloud telemetry. |
| **Silero VAD** | MIT | `silero-vad>=5.1.0` | Local Audio Dependency | Voice Activity Detection (barge-in & speech boundaries). | Lightweight PyTorch/ONNX model; filters ambient silence without retaining raw audio. |
| **Playwright** | Apache-2.0 | `playwright>=1.42.0` | Sandboxed Automation | Browser worker, DOM text extraction, screenshot evidence capture. | Headless execution restricted to private browser context; SSRF protection blocks private subnets (`127.0.0.1`, `10.0.0.0/8`, `192.168.0.0/16`) unless explicitly cleared. |
| **MCP Reference Servers** | MIT | `@modelcontextprotocol/server-*` | Standardized Subprocess / JSON-RPC | Filesystem, Git, Fetch, Time, Sequential Thinking tools. | Explicit allow-lists per power; strict path scoping to `PROJECT_ROOT/data` and `PROJECT_ROOT/scratch`. No arbitrary shell execution. |
| **OpenClaw** | MIT | Pinned commit / Pattern | Pattern Study & Re-implementation | Channel gateway, pairing policy, system doctor inspection, `SKILL.md` skill packaging. | Borrowed architectural concepts only; DO NOT run as a second orchestrator. |
| **Hermes Agent** | MIT | Pinned commit / Pattern | Pattern Study & Re-implementation | Self-written skills, `MEMORY.md` user profile, FTS5 cross-session recall, strict command allow-lists. | Borrowed memory schema and command allow-listing patterns; verified MIT license. |

---

## 2. Upstream License Compliance Log

| Project | License Identifier | Commercial Use? | Modification Allowed? | Attribution Required? | Approved for Inclusion? |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `langgraph` | `MIT` | Yes | Yes | Yes (keep header) | ✅ Approved |
| `mem0ai` | `Apache-2.0` | Yes | Yes | Yes (NOTICE included) | ✅ Approved |
| `litellm` | `MIT` | Yes | Yes | Yes (keep header) | ✅ Approved |
| `ollama` | `MIT` | Yes | Yes | Yes (keep header) | ✅ Approved |
| `openwakeword` | `Apache-2.0` | Yes | Yes | Yes (NOTICE included) | ✅ Approved |
| `faster-whisper` | `MIT` | Yes | Yes | Yes (keep header) | ✅ Approved |
| `piper-tts` | `MIT` | Yes | Yes | Yes (keep header) | ✅ Approved |
| `silero-vad` | `MIT` | Yes | Yes | Yes (keep header) | ✅ Approved |
| `playwright` | `Apache-2.0` | Yes | Yes | Yes (NOTICE included) | ✅ Approved |
| `modelcontextprotocol` | `MIT` | Yes | Yes | Yes (keep header) | ✅ Approved |
| `openclaw` | `MIT` | Yes | Yes | Yes (attribution) | ✅ Approved (Patterns) |
| `hermes-agent` | `MIT` | Yes | Yes | Yes (attribution) | ✅ Approved (Patterns) |

---

## 3. Strict Prohibitions
- **GPL / AGPL Code**: No copying of GPL/AGPL licensed code into the JARVIS MIT codebase.
- **Unverified Repositories**: Any upstream repo lacking an explicit OSI-approved `LICENSE` file is rejected.
- **Silent Network Hops**: Upstream libraries must be configured to run strictly offline unless explicitly directed to a configured remote endpoint.

