# JARVIS Build Log

A running audit log of all build iterations, test suites, and git commits.

---

## 1. Commit History
- **`e4732d4`**: Initial production release of JARVIS Personal AI Operating System (Core, Configuration, 3-Tier Router, SQLite Memory, Policy Gate, 355 Powers Catalog).
- **`d0b026d`**: Complete sequential non-lossy PDF extraction (434 pages, 30,162 lines) and final merged blueprint.
- **`6b9a025`**: Phase 0 & Phase 1 Foundations (RotatingFileHandler logger, Full-Duplex Voice Pipeline: Wake word, PTT, STT, SAPI WAV TTS, Barge-in, Iron Man Glassmorphic HUD Dashboard).
- **`223f5dc`**: CLI `--help` flag documentation and usage improvements.
- **`9a8dc54`**: Milestone B — Safe Browser Read-Only Subsystem (Playwright DOM extraction, SSRF protection, screenshot evidence capture with SHA-256 hashes, DuckDuckGo search, and deep research worker).
- **`949cbbd`**: Part 2 Task Engine APIs, LiteLLM unified model router, and architecture docs.
- **`2a6d78d`**: Milestone 3 — Private Memory Vault & Document RAG (7-Layer cognitive store, fact/hypothesis differentiation, user correction pipeline with auto-directive promotion, PyMuPDF page-specific chunking with exact citations, and Part 7 REST APIs).
- **Milestone 5 — Desktop Computer Use Worker**: See-Act-Verify operator loop, OS UI automation via win32gui, PyAutoGUI fallback coordinate controls with physical mouse-corner failsafe, safety app allow-list, credential typing protection, and Part 11 Desktop REST APIs.

---

## 2. Test Verification History
- **Test Session 1 (Core)**: 23 passed in 1.48s
- **Test Session 2 (Phase 0 & 1 with Voice & Dashboard)**: 37 passed in 4.31s
- **Test Session 3 (Post Polish)**: 37 passed in 4.15s
- **Test Session 4 (Milestone B & Task Engine/LiteLLM)**: 51 passed in 73.79s
- **Test Session 5 (Milestone 3 — Private Memory Vault & RAG)**: 57 passed in 76.76s
- **Test Session 6 (Milestone 5 — Desktop Computer Use Worker)**: 64 passed in 78.49s
  - `tests/test_api.py`: 8 passed
  - `tests/test_audit.py`: 1 passed
  - `tests/test_browser.py`: 8 passed
  - `tests/test_dashboard.py`: 5 passed
  - `tests/test_desktop.py`: 7 passed
  - `tests/test_memory_vault.py`: 6 passed
  - `tests/test_model_router.py`: 7 passed
  - `tests/test_orchestrator.py`: 3 passed
  - `tests/test_policy_gate.py`: 3 passed
  - `tests/test_power_registry.py`: 2 passed
  - `tests/test_privacy_gate.py`: 2 passed
  - `tests/test_tasks_and_litellm.py`: 6 passed
  - `tests/test_voice.py`: 6 passed
