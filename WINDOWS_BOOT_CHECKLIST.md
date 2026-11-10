# JARVIS Windows Sign-In Boot Checklist

This checklist is the only accepted proof of the full boot path. Unit tests,
direct `cscript` runs and isolated smoke tests do **not** prove the Windows
Startup-folder flow.

Owner action required: sign out of Windows, sign back in, then complete the
steps below. Record the observed result and timestamp for each step.

| # | Step | How to verify | Status |
| :- | :--- | :--- | :--- |
| 1 | Windows sign-out completes | Normal Start → Sign out | ☐ Not yet performed |
| 2 | Windows sign-in completes | Sign in with the owner account | ☐ Not yet performed |
| 3 | Startup VBS executes | `Get-Process pythonw` shows the launcher's children; `logs\launcher.log` has a new line | ☐ Not yet performed |
| 4 | API server starts | `GET http://127.0.0.1:8000/health` → 200; registry `api_server` = RUNNING | ☐ Not yet performed |
| 5 | Voice daemon starts | Registry `voice_daemon` = RUNNING; `logs\voice_daemon.log` shows microphone opened | ☐ Not yet performed |
| 6 | Microphone acquisition | `voice_daemon.log` names the real microphone and `mic_live=True` | ☐ Not yet performed |
| 7 | Real "Hey Jarvis" detection | Say "Hey Jarvis"; HUD wake animation / daemon log wake event | ☐ Not yet performed |
| 8 | Real harmless voice command | e.g. "Hey Jarvis, what time is it?"; spoken response | ☐ Not yet performed |
| 9 | HUD accessibility | HUD visible and responsive; `/api/v1/system/processes` shows `hud_overlay` RUNNING | ☐ Not yet performed |
| 10 | Voice-only shutdown | Run `scripts\stop_jarvis.ps1`; voice stops, API + HUD remain; `/health` still 200 | ☐ Not yet performed |
| 11 | Full shutdown | Run `scripts\stop_all_jarvis.ps1`; all three roles STOPPED; port 8000 closed | ☐ Not yet performed |

## Evidence commands

```powershell
python -m jarvis.ops.process_registry --json health
Invoke-WebRequest http://127.0.0.1:8000/health -UseBasicParsing
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\stop_jarvis.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\stop_all_jarvis.ps1
```

## Current status

Steps 1–11 remain **UNVERIFIED** for a real sign-in cycle. Steps 3–11 have been
verified by direct `cscript` execution on 2026-11-09; that is necessary but not
sufficient evidence for the Startup-folder path.
