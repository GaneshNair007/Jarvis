# Sprint 3 Reflection — Iron Man HUD / App Connections ("As Soon As I Say Hey Jarvis")

**Date:** 2026-11-09
**Branch:** `feature/sprint2-acoustic-wake-and-always-on` (continuation of sprint 2 commit `1a3f03e`)
**Fourth Law record:** written before completion claims. Builds on
`sprint2_acoustic_wake_reflection.md` (this file adds no new wake evidence —
wake receipts stay there).

## What I built
1. **Iron Man HUD overlay** (`jarvis/hud/overlay.py`): frameless, topmost
   tkinter arc reactor, bottom-center, cyan "LISTENING" during capture /
   amber "THINKING" during processing / green "READY" flash on done (≈3 s
   settle), then hides. Never activates the window, steals no focus.
2. **Daemon → HUD bridge** (`jarvis/hud/state.py`): daemon writes
   `data/logs/daemon_state.json` atomically (tmp + os.replace) at every
   transition; overlay polls every 300 ms; missing/invalid/stale (>30 s)
   files all fail closed to hidden. HUD shows only during
   CAPTURING_COMMAND / PROCESSING / SPEAKING.
3. **App connections** (`jarvis/automation/app_connector.py`):
   - opencode → `opencode run --auto "<task>"` headless delegate (per-task
     log `data/logs/opencode_*.log`, detached, First-Law evidence).
   - `opencode run in <folder>` → visible console session (user drives TUI).
   - Antigravity (new agentic app) and Antigravity IDE (`bin\antigravity-ide.cmd`) — launch (+ folder arg) — the task is put on the
     clipboard for the agent panel (Ctrl+V). No public API is faked; the
     handoff is stated on every receipt.
   - Generic launchers resolved on THIS host (chrome/spotify/vscode/
     notepad/explorer/terminal via full paths or PATH).
   - Loopback/headless honesty: `launch_app` uses injected spawner in tests.
4. **Voice fast-path** in VoiceDaemon `_execute_command`: wake → phrase match
   → strip → `match_app_intent` regex family (launch / delegate / opencode_in)
   executes directly — no LLM roundtrip; orchestrator untouched. Env lever
   `JARVIS_APP_INTENTS=off` restores pure orchestrator routing.
5. **Wake acknowledgment**: bare "Hey Jarvis" → daemon speaks "Yes?" and HUD
   pops (state CAPTURING_COMMAND) — the Iron Man beat, then it listens.
6. **Always-on boot**: `JARVIS Background.vbs` now starts 3 processes
   (uvicorn :8000 + voice daemon + HUD overlay); Startup copy refreshed;
   `stop_jarvis.ps1` kills the HUD too.

## Measured / verified
- Suite: 645 + 51 new (app-connector match/execute + HUD bridge +
  wake→"open antigravity" end-to-end: launcher invoked, orchestrator NOT,
  evidence recorded, HUD state file written through the cycle) = full green.
- HUD smoke: overlay process starts, stays alive 6 s, renders without
  Tcl errors; killed cleanly; state file reset to IDLE after smoke.
- app-intent executes on REAL executables on this host: Antigravity.exe,
  `Antigravity IDE.exe` (launch), npm `opencode.cmd` (PATH-resolved).

## Known limits (honest)
- Antigravity has no stable public task API: the connector LAUNCHES it and
  pre-loads the task on the clipboard; it does not push keystrokes into the
  agent panel (injecting blind Enter/Ctrl+V into the wrong window is how
  files get deleted). If/when an official Antigravity MCP/ACP server ships,
  wire it here.
- Whisper on the user's wake utterances can garble command text
  ("a service") — acceptable for launching apps, risky for exact paths.
- The wake→HUD beat is UNTESTED under the REAL live boot path end-to-end
  until the user speaks through the Startup-installed stack; the HUD smoke
  and bridge tests prove the mechanism, not the coincidental focus state
  of a fullscreen app.

## Next sprint (with owner = "do it")
- Pre-warm the acoustic gate inside `VoiceDaemon.start()` (kills the 10 s
  silent model-load window).
- ACP/connector for opencode via `opencode acp` if the user wants streaming
  status into the HUD (orbital ring shows real task progress).
- Antigravity CLI probe: watch for `antigravity cli` (alpha channel) to
  upgrade the clipboard handoff to a real agent delegation.
- Human wake receipt already banked
  (0.7134 offline re-score of the capture, live 0.7157, SAPI 0.9985 through
  frames, 0.9034 through air); this sprint adds no new wake evidence.

