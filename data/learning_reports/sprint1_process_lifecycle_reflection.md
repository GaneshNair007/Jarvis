# Fourth-Law Reflection — Sprint 1 Process Lifecycle

**Date:** 2026-11-09  
**Branch:** `feature/jarvis-google-voice-multiagent`  
**Constitution:** v1.2.0, Fourth Law — NO MEMORY WITHOUT REFLECTION

## What was claimed before

Previous work described the always-on startup path as:
`VBS → API server + pythonw voice daemon → live wake → HUD`, and described
`stop_jarvis.ps1` as stopping background processes.

## What was actually true

1. The VBS launcher did not compile. `cscript` reported
   `(18, 145) Microsoft VBScript compilation error: Expected end of statement`
   because `2>&1` was outside the quoted command on all three launch lines.
   No process could have been started by that file in its committed state.
2. `stop_jarvis.ps1` deliberately killed the API server, voice daemon and HUD.
   That contradicted the new voice-only stop contract.
3. There was no process identity registry, so "JARVIS is running" could only
   mean "some process matched a regex once."

## What changed

- Fixed the VBS string boundaries without changing the launcher architecture.
- Added `jarvis/ops/process_registry.py` with PID + creation-time + command-line
  validation, atomic persistence, role claims, discovery, pruning and
  idempotent stop.
- Split stop behavior:
  - `stop_jarvis.ps1` = voice daemon only.
  - `stop_all_jarvis.ps1` = all three roles + independent verification.
- Registered all three real processes and exposed validated health at
  `/api/v1/system/processes` and in `/health`.
- Reinstalled the Startup copy and confirmed byte-identity by SHA-256.

## Evidence ledger

| Claim | Evidence | Result |
| :--- | :--- | :--- |
| VBS is executable | `cscript //nologo scripts\start_jarvis_background.vbs` | exit 0 |
| Three processes started | registry health | PIDs 33556 / 36252 / 54224, all RUNNING |
| API actually serves | `GET /health` | HTTP 200 |
| Voice-only stop works | `stop_jarvis.ps1` | voice 36252 stopped; API/HUD still RUNNING; HTTP 200 |
| Stop is idempotent | second `stop_jarvis.ps1` | no-op, exit 0 |
| Full stop works | `stop_all_jarvis.ps1` | all roles stopped; port 8000 closed |
| Startup copy matches source | SHA-256 | `09158842...74836CF8` both files |
| PID reuse is safe | pytest forged-record test | record refused, pytest process survived |
| HUD survives voice stop | pytest + real health | HUD PID alive, API 200 |

## What remains unproven

- A real Windows sign-out/sign-in cycle. Direct `cscript` execution is not the
  same as the Startup-folder path. This remains **UNVERIFIED** until the owner
  performs it.
- Visual HUD presence after a voice-only stop (process-level only).
- API cold-start time (~60 s) is measured but not yet optimized.

## Lesson

A launcher that is never executed is documentation, not automation. The
previous "always-on" claim was unsupported by execution evidence. This sprint
replaced regex hope with process identity proof, and replaced a blanket stop
with role-scoped, validated termination.
