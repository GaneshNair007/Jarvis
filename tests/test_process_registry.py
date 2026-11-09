"""Sprint 1 lifecycle tests: validated process registry + split stop scripts.

These tests exercise real OS processes.  They never start the microphone
daemon or a visible HUD window; the "voice" and "HUD" roles are represented by
long-lived Python sleepers whose command lines match injected role signatures.
That isolates the lifecycle contract (stop exactly one validated role, leave
the others alive) from audio/display hardware.
"""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import psutil
import pytest

from jarvis.ops.process_registry import ProcessRecord, ProcessRegistry

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"


def _write_records(path: Path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"version": 1, "records": [r.to_dict() for r in records]}),
        encoding="utf-8",
    )


def _spawn_sleeper(marker: str) -> subprocess.Popen:
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(120)", marker],
        cwd=str(REPO),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # Wait until psutil can read cwd/cmdline for the new process.
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            p = psutil.Process(proc.pid)
            p.cmdline()
            p.cwd()
            return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            time.sleep(0.05)
    proc.kill()
    raise RuntimeError("sleeper process did not become inspectable")


def _terminate(proc: subprocess.Popen) -> None:
    try:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        pass


@pytest.fixture
def custom_registry(tmp_path):
    patterns = {
        "voice_daemon": r"fake-voice-role",
        "hud_overlay": r"fake-hud-role",
        "api_server": r"fake-api-role",
    }
    return ProcessRegistry(
        registry_path=tmp_path / "runtime" / "process_registry.json",
        repo_root=REPO,
        role_patterns=patterns,
    )


def test_register_current_refuses_non_matching_process(tmp_path):
    """A pytest process must not be recorded as the production voice daemon."""
    registry = ProcessRegistry(registry_path=tmp_path / "registry.json", repo_root=REPO)
    assert registry.register_current("voice_daemon") is None
    assert registry.load() == []


def test_prune_removes_dead_pid_record(tmp_path):
    registry = ProcessRegistry(registry_path=tmp_path / "registry.json", repo_root=REPO)
    stale = ProcessRecord(
        instance_id="stale-1",
        pid=999_999,
        role="voice_daemon",
        executable="pythonw.exe",
        cmdline="pythonw -m jarvis.voice.daemon",
        create_time=time.time(),
        repo_root=str(REPO),
    )
    _write_records(registry.registry_path, [stale])

    removed = registry.prune()

    assert len(removed) == 1
    assert "no longer exists" in removed[0]["reason"]
    assert registry.load() == []


def test_stop_refuses_pid_reuse_and_never_kills_pytest(tmp_path):
    """A stale PID reused by another process must be skipped, not killed."""
    registry = ProcessRegistry(registry_path=tmp_path / "registry.json", repo_root=REPO)
    forged = ProcessRecord(
        instance_id="forged-1",
        pid=os.getpid(),
        role="voice_daemon",
        executable=sys.executable,
        cmdline="python -m jarvis.voice.daemon",
        create_time=time.time() - 3600,  # deliberately wrong
        repo_root=str(REPO),
    )
    _write_records(registry.registry_path, [forged])

    report = registry.stop(role="voice_daemon", timeout=1)

    assert report["stopped"] == []
    assert report["failed"] == []
    assert report["skipped"], "PID-reuse record should be reported as skipped"
    assert "refused" in report["skipped"][0]["reason"]
    assert "creation time mismatch" in report["skipped"][0]["reason"]
    assert psutil.Process(os.getpid()).is_running()


def test_stop_voice_leaves_hud_running_then_stop_all(custom_registry):
    voice = _spawn_sleeper("fake-voice-role")
    hud = _spawn_sleeper("fake-hud-role")
    try:
        assert custom_registry.adopt("voice_daemon", voice.pid) is not None
        assert custom_registry.adopt("hud_overlay", hud.pid) is not None

        before = custom_registry.health()
        assert before["roles"]["voice_daemon"]["status"] == "RUNNING"
        assert before["roles"]["hud_overlay"]["status"] == "RUNNING"

        report = custom_registry.stop(role="voice_daemon", timeout=3)

        assert report["success"] is True
        assert voice.poll() is not None, "voice daemon stand-in should be stopped"
        assert hud.poll() is None, "HUD must survive a voice-only stop"

        after = custom_registry.health()
        assert after["roles"]["voice_daemon"]["status"] == "STOPPED"
        assert after["roles"]["hud_overlay"]["status"] == "RUNNING"

        full = custom_registry.stop(stop_all=True, timeout=3)
        assert full["success"] is True
        assert hud.poll() is not None
        assert custom_registry.health()["all_required_running"] is False
    finally:
        _terminate(voice)
        _terminate(hud)


def test_stop_is_idempotent(custom_registry):
    voice = _spawn_sleeper("fake-voice-role")
    try:
        assert custom_registry.adopt("voice_daemon", voice.pid) is not None
        first = custom_registry.stop(role="voice_daemon", timeout=3)
        second = custom_registry.stop(role="voice_daemon", timeout=3)
        assert first["success"] is True
        assert second["success"] is True
        assert second["stopped"] == []
        assert second["failed"] == []
    finally:
        _terminate(voice)


def test_health_reports_unregistered_discovered_process(custom_registry):
    hud = _spawn_sleeper("fake-hud-role")
    try:
        report = custom_registry.health()
        assert report["roles"]["hud_overlay"]["status"] == "RUNNING_UNREGISTERED"
        assert report["roles"]["hud_overlay"]["instances"][0]["pid"] == hud.pid
    finally:
        _terminate(hud)


def test_cli_health_json_is_machine_readable():
    result = subprocess.run(
        [sys.executable, "-m", "jarvis.ops.process_registry", "--json", "health"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert set(payload["roles"]) == {"api_server", "voice_daemon", "hud_overlay"}
    assert "all_required_running" in payload
    assert "stale_records" in payload


def test_stop_script_targets_voice_role_only():
    ps1 = (SCRIPTS / "stop_jarvis.ps1").read_text(encoding="utf-8", errors="replace")
    assert "stop --role voice_daemon" in ps1
    assert "stop --all" not in ps1
    assert "Stop-Process -Name python" not in ps1
    assert "taskkill /IM python" not in ps1
    # It must not contain a blanket process-name kill.
    assert not re.search(r"Get-Process\s+python", ps1)


def test_stop_all_script_stops_and_verifies_all_roles():
    ps1 = (SCRIPTS / "stop_all_jarvis.ps1").read_text(encoding="utf-8", errors="replace")
    assert "stop --all" in ps1
    assert "--json health" in ps1
    assert "all_required_running" in ps1
    assert "Stop-Process -Name python" not in ps1
    assert "taskkill /IM python" not in ps1


def test_lifecycle_powershell_scripts_parse_cleanly():
    parser = r"""
$files = @('scripts\stop_jarvis.ps1', 'scripts\stop_all_jarvis.ps1')
$failed = $false
foreach ($f in $files) {
  $tokens = $null; $errors = $null
  [System.Management.Automation.Language.Parser]::ParseFile(
    (Resolve-Path $f), [ref]$tokens, [ref]$errors) | Out-Null
  if ($errors -and $errors.Count -gt 0) {
    Write-Output ("PARSE_ERROR " + $f + ": " + $errors[0].Message)
    $failed = $true
  } else {
    Write-Output ("PARSE_OK " + $f)
  }
}
if ($failed) { exit 1 } else { exit 0 }
"""
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", parser],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PARSE_OK" in result.stdout
    assert "PARSE_ERROR" not in result.stdout
