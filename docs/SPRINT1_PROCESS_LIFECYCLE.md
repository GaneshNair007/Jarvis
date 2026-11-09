# Sprint 1 — Process Lifecycle Stabilization

Status: **IMPLEMENTED AND VERIFIED (process-level)**  
Branch: `feature/jarvis-google-voice-multiagent`  
Date: 2026-11-09

## 1. Audit findings (before this sprint)

| Finding | Evidence | Risk |
| :--- | :--- | :--- |
| `stop_jarvis.ps1` killed the API server, voice daemon **and** HUD | Script matched `uvicorn jarvis.api.server` and `jarvis.hud.overlay` in addition to the daemon | A voice-only stop took the dashboard and HUD offline |
| The startup VBS could not be parsed | `cscript scripts\start_jarvis_background.vbs` → `(18, 145) Microsoft VBScript compilation error: Expected end of statement` | The documented always-on boot path had never actually launched anything |
| No process identity registry | Only regex command-line matching, no PID/creation-time validation | A reused PID could be killed; health could not distinguish registered from stray processes |
| No full-stop script | `stop_jarvis.ps1` was the only stop path | No way to stop the API + HUD without blanket process kills |
| Health was optimistic | `/health` returned `healthy` whenever the API answered, regardless of voice/HUD state | Dashboard could not tell that the rest of JARVIS was down |

The VBS defect was a genuine syntax error: `2>&1` was outside the quoted
command string on all three `shell.Run` lines. The launcher architecture was
preserved; only the string boundaries were corrected.

## 2. Implementation

### 2.1 Validated process registry

`jarvis/ops/process_registry.py`

Every record contains:

- `instance_id` (random per registration)
- `pid`
- `role` (`api_server`, `voice_daemon`, `hud_overlay`)
- `executable` (full path)
- `cmdline`
- `create_time` (OS process creation timestamp)
- `repo_root`
- `registered_at`
- `source` (`registered`, `adopted`, `discovered`)

Safety rules:

1. A PID is never trusted on its own. Before signalling, the registry
   re-validates the live creation timestamp (PID-reuse guard), command line,
   Python executable, and repository working directory.
2. Discovery of unregistered processes requires the same evidence. This
   covers processes started before the registry existed.
3. The registry file is written atomically and guarded by a cross-platform
   advisory lock (Windows `msvcrt` / POSIX `flock`).
4. Stale records are pruned; invalid records are reported as `refused`, never
   killed.
5. The registry never enumerates or kills `python.exe`/`pythonw.exe` by name.

The singleton role claim makes repeated launcher invocations idempotent:
`claim_role()` returns `EXISTING` when a validated instance already owns the
role, and the new process exits cleanly.

### 2.2 Registration points

| Process | Registration | Release |
| :--- | :--- | :--- |
| API server | FastAPI lifespan startup (`register_current("api_server")`) | lifespan shutdown |
| Voice daemon | `main()` before audio initialization (`claim_role("voice_daemon")`) | `finally` on exit |
| HUD overlay | `main()` before the tkinter loop (`claim_role("hud_overlay")`) | `finally` on exit |

`register_current()` refuses to register a process whose command line does not
match the role signature, so pytest/import-time app construction does not
pollute the production registry.

### 2.3 Stop contracts

- `scripts/stop_jarvis.ps1` → `stop --role voice_daemon`.
  Leaves the API server and HUD running.
- `scripts/stop_all_jarvis.ps1` → `stop --all`, then an independent
  `--json health` check. Exits non-zero if any required role is still running.
- Both scripts are idempotent; a stop with nothing running is a success no-op.
- Both scripts parse cleanly under the PowerShell language parser.

### 2.4 Accurate health

- `GET /health` now includes a `processes` summary.
- `GET /api/v1/system/processes` returns the full validated report:
  per-role status (`RUNNING`, `RUNNING_UNREGISTERED`, `STOPPED`), PIDs,
  creation times, command lines, stale records, and `all_required_running`.
- CLI: `python -m jarvis.ops.process_registry health [--json]`.

### 2.5 Startup contract

`scripts/start_jarvis_background.vbs` remains the single launcher and still
starts exactly three hidden processes:

1. `pythonw -m uvicorn jarvis.api.server:app --host 127.0.0.1 --port 8000`
2. `pythonw -m jarvis.voice.daemon`
3. `pythonw -m jarvis.hud.overlay`

The installed Startup copy is byte-identical to the repository source:

```
SHA-256 09158842C70AFBF41D3CA74C8B6D8F279A60EEBACCDB768F99D8E33E74836CF8
```

## 3. Verification evidence

### 3.1 Real launcher run

```
cscript //nologo scripts\start_jarvis_background.vbs   -> exit 0
```

Validated health after startup:

```
api_server    RUNNING              pid 33556
voice_daemon  RUNNING              pid 36252
hud_overlay   RUNNING              pid 54224
all required running: True
```

API cold start completed at `14:43:03` (`Application startup complete`);
`GET http://127.0.0.1:8000/health` returned HTTP 200.

### 3.2 Voice-only stop

```
powershell -File scripts\stop_jarvis.ps1   -> exit 0
  stopped 36252 (voice_daemon)
```

After the stop:

```
api_server    RUNNING   pid 33556
voice_daemon  STOPPED
hud_overlay   RUNNING   pid 54224
GET /health -> HTTP 200
```

A second invocation returned `idempotent no-op` with exit 0.

### 3.3 Full stop

```
powershell -File scripts\stop_all_jarvis.ps1   -> exit 0
  stopped 54224 (hud_overlay)
  stopped 33556 (api_server)
Verified: API server, voice daemon and HUD overlay are all stopped.
```

After the full stop, port 8000 was no longer listening and health reported
all three roles `STOPPED`.

### 3.4 Automated tests

```
pytest tests/test_process_registry.py tests/test_startup_scripts.py -v
18 passed
```

Includes:

- PID-reuse refusal (forged record pointing at the pytest process; pytest
  survived and the record was reported `refused: creation time mismatch`).
- Voice-only stop leaves a HUD stand-in process alive.
- Full stop terminates both roles.
- Idempotent second stop.
- Unregistered-process discovery (`RUNNING_UNREGISTERED`).
- PowerShell parse checks for both stop scripts.
- Installer copy byte-identity check.

Related regression run:

```
pytest tests/test_api.py tests/test_milestone1_core.py tests/test_dashboard.py \
       tests/test_voice_daemon.py tests/test_iron_man_hud.py -q
57 passed
```

## 4. Known limits / not yet verified

1. **Full Windows sign-out/sign-in boot test has not been performed.** The
   launcher was executed directly with `cscript`; it must still be verified
   after a real sign-in. See the manual checklist in
   `docs/WINDOWS_BOOT_CHECKLIST.md`.
2. HUD survival was verified at process level (PID alive and `/health`
   reachable). Visual HUD presence after a voice-only stop was not
   instrumented; the HUD writes no window-title evidence.
3. API cold start measured ~60 seconds on this machine because module imports
   load wake-word/STT models. This is a startup-latency issue for a later
   sprint, not a lifecycle failure.
4. The VBS fix changes the source file; the Startup copy was reinstalled and
   hash-matched. Any future edit must repeat the installer and hash check.
