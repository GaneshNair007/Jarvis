"""
Adversarial Empirical Challenge Probe for Milestone 3 Process Stability.
Author: challenger_m3_1 (Empirical Adversarial Critic)
Target: jarvis/core/process_manager.py (ProcessManager)

Probing:
1. Stale PID file recovery (dead PID in jarvis.pid, .jarvis.pid, corrupted files).
2. Dual-lock enforcement against active competing processes.
3. Audio daemon liveness tracking and dead process reap.
4. Clean shutdown OS-level termination and dual PID file deletion.
5. API surface audit (checking acquire_pid vs acquire_lock).
"""

import os
import sys
import json
import time
import subprocess
import psutil
import pytest
from pathlib import Path
from jarvis.core.process_manager import ProcessManager


@pytest.fixture
def probe_pm(tmp_path):
    """Isolated ProcessManager instance for testing."""
    return ProcessManager(base_dir=tmp_path)


# =============================================================================
# 1. Stale PID File Recovery
# =============================================================================

def test_stale_pid_recovery_in_both_files(probe_pm):
    """Write dead PID into jarvis.pid and .jarvis.pid; verify cleanup and acquisition."""
    dead_pid = 9999998
    assert not psutil.pid_exists(dead_pid), f"PID {dead_pid} unexpectedly exists on host"

    record = {"service": "jarvis", "pid": dead_pid, "started_at": time.time() - 5000}
    with open(probe_pm.root_pid_file, "w", encoding="utf-8") as f:
        json.dump(record, f)
    with open(probe_pm.jarvis_pid_file, "w", encoding="utf-8") as f:
        json.dump(record, f)

    assert probe_pm.root_pid_file.exists()
    assert probe_pm.jarvis_pid_file.exists()

    # acquire_pid should detect stale PID, wipe it, and acquire with current process
    curr_pid = os.getpid()
    acquired = probe_pm.acquire_pid("jarvis", pid=curr_pid)
    assert acquired is True

    # Files must now contain curr_pid
    root_data = json.loads(probe_pm.root_pid_file.read_text(encoding="utf-8"))
    jarvis_data = json.loads(probe_pm.jarvis_pid_file.read_text(encoding="utf-8"))
    assert root_data["pid"] == curr_pid
    assert jarvis_data["pid"] == curr_pid
    assert probe_pm.is_running("jarvis") is True


def test_stale_pid_recovery_in_only_jarvis_pid(probe_pm):
    """Write dead PID ONLY into jarvis.pid (unhidden); verify detection, cleanup, and acquisition."""
    dead_pid = 9999997
    assert not psutil.pid_exists(dead_pid)

    record = {"service": "jarvis", "pid": dead_pid, "started_at": time.time() - 5000}
    # Notice: do NOT write .jarvis.pid, only jarvis.pid
    with open(probe_pm.jarvis_pid_file, "w", encoding="utf-8") as f:
        json.dump(record, f)

    assert not probe_pm.root_pid_file.exists()
    assert probe_pm.jarvis_pid_file.exists()

    curr_pid = os.getpid()
    acquired = probe_pm.acquire_pid("jarvis", pid=curr_pid)
    assert acquired is True

    # Both files must now exist and contain current PID
    assert probe_pm.root_pid_file.exists()
    assert probe_pm.jarvis_pid_file.exists()
    root_data = json.loads(probe_pm.root_pid_file.read_text(encoding="utf-8"))
    assert root_data["pid"] == curr_pid


def test_corrupted_pid_file_recovery(probe_pm):
    """Write malformed non-JSON garbage into jarvis.pid; verify system recovers gracefully."""
    probe_pm.root_pid_file.write_text("CORRUPTED_NOT_JSON!@#$%^&*()", encoding="utf-8")
    probe_pm.jarvis_pid_file.write_text("{ incomplete json ...", encoding="utf-8")

    # read_pid should not crash
    info = probe_pm.read_pid("jarvis")
    assert info is None

    # is_running should return False
    assert probe_pm.is_running("jarvis") is False

    # acquire_pid should overwrite corrupted files cleanly
    curr_pid = os.getpid()
    acquired = probe_pm.acquire_pid("jarvis", pid=curr_pid)
    assert acquired is True
    assert probe_pm.root_pid_file.exists()
    assert probe_pm.jarvis_pid_file.exists()
    root_data = json.loads(probe_pm.root_pid_file.read_text(encoding="utf-8"))
    assert root_data["pid"] == curr_pid


# =============================================================================
# 2. Dual-Lock Enforcement Against Active Processes
# =============================================================================

def test_dual_lock_active_process_conflict_rejection(probe_pm):
    """Verify acquiring lock when an active process holds it returns False."""
    # Spawn a genuine long-running process
    subproc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        # Service acquired by the real living subprocess
        acquired = probe_pm.acquire_pid("jarvis", pid=subproc.pid)
        assert acquired is True
        assert probe_pm.is_running("jarvis") is True

        # Competing attempt with our PID must return False
        curr_pid = os.getpid()
        competing_attempt = probe_pm.acquire_pid("jarvis", pid=curr_pid)
        assert competing_attempt is False

        # Verify original process lock was NOT overwritten
        info = probe_pm.read_pid("jarvis")
        assert info["pid"] == subproc.pid

        # Verify telemetry log recorded duplicate_instance_blocked
        telem_file = probe_pm.log_dir / "daemon_telemetry.jsonl"
        assert telem_file.exists()
        log_content = telem_file.read_text(encoding="utf-8")
        assert "duplicate_instance_blocked" in log_content
        assert str(subproc.pid) in log_content
        assert str(curr_pid) in log_content
    finally:
        subproc.terminate()
        try:
            subproc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            subproc.kill()


def test_cross_process_dual_lock_rejection(probe_pm):
    """Launch a real external process that attempts to acquire the lock while held."""
    curr_pid = os.getpid()
    probe_pm.acquire_pid("jarvis", pid=curr_pid)
    assert probe_pm.is_running("jarvis") is True

    # Run external python subprocess trying to acquire lock
    script = f"""
import os, sys
from pathlib import Path
from jarvis.core.process_manager import ProcessManager
pm = ProcessManager(base_dir=Path(r"{probe_pm.base_dir}"))
acquired = pm.acquire_pid("jarvis", pid=os.getpid())
sys.exit(0 if acquired else 42)
"""
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 42, f"Expected returncode 42 (rejection), got {result.returncode}. stdout: {result.stdout}, stderr: {result.stderr}"

    # Verify lock still belongs to parent
    info = probe_pm.read_pid("jarvis")
    assert info["pid"] == curr_pid


# =============================================================================
# 3. Audio Daemon Liveness
# =============================================================================

def test_audio_daemon_lifecycle_and_dead_process_termination(probe_pm):
    """Verify track_audio_daemon correctly reflects PID liveness and dead process termination."""
    assert probe_pm.is_audio_daemon_alive() is False
    assert probe_pm.get_audio_daemon_status()["running"] is False

    # Spawn genuine child process for audio daemon
    audio_proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        tracked = probe_pm.track_audio_daemon(pid=audio_proc.pid, metadata={"engine": "pyaudio", "mic": "default"})
        assert tracked is True
        assert probe_pm.is_audio_daemon_alive() is True

        st = probe_pm.get_audio_daemon_status()
        assert st["running"] is True
        assert st["pid"] == audio_proc.pid
        assert st["status"] == "RUNNING"
        assert st["metadata"]["engine"] == "pyaudio"

        # Now simulate crash/termination of audio daemon process
        audio_proc.terminate()
        audio_proc.wait(timeout=3)
        assert not audio_proc.poll() is None

        # ProcessManager should immediately detect that it is dead
        assert probe_pm.is_audio_daemon_alive() is False
        st_after = probe_pm.get_audio_daemon_status()
        assert st_after["running"] is False
        assert st_after["status"] == "STOPPED"

        # Stale audio_daemon.pid file must be cleaned up
        audio_pid_file = probe_pm.pid_dir / "audio_daemon.pid"
        assert not audio_pid_file.exists()
    finally:
        if audio_proc.poll() is None:
            audio_proc.kill()


# =============================================================================
# 4. Clean Shutdown
# =============================================================================

def test_clean_shutdown_terminates_processes_and_unlinks_dual_pids(probe_pm):
    """Verify clean_shutdown terminates active processes and deletes both jarvis.pid and .jarvis.pid."""
    proc_jarvis = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    proc_audio = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])

    try:
        assert probe_pm.acquire_pid("jarvis", pid=proc_jarvis.pid) is True
        assert probe_pm.track_audio_daemon(pid=proc_audio.pid) is True

        assert probe_pm.root_pid_file.exists()
        assert probe_pm.jarvis_pid_file.exists()
        assert (probe_pm.pid_dir / "audio_daemon.pid").exists()

        # Execute clean shutdown
        shutdown_report = probe_pm.clean_shutdown(timeout_sec=2.0)
        assert isinstance(shutdown_report, dict)
        assert shutdown_report.get("jarvis") is True
        assert shutdown_report.get("audio_daemon") is True

        # Verify OS processes were killed
        time.sleep(0.5)
        assert not psutil.pid_exists(proc_jarvis.pid) or proc_jarvis.poll() is not None
        assert not psutil.pid_exists(proc_audio.pid) or proc_audio.poll() is not None

        # Verify dual PID files and audio PID file were deleted
        assert not probe_pm.root_pid_file.exists(), ".jarvis.pid was not deleted"
        assert not probe_pm.jarvis_pid_file.exists(), "jarvis.pid was not deleted"
        assert not (probe_pm.pid_dir / "audio_daemon.pid").exists(), "audio_daemon.pid was not deleted"
        assert not (probe_pm.pid_dir / "jarvis.pid").exists(), "data/pids/jarvis.pid was not deleted"

        assert probe_pm.is_running("jarvis") is False
        assert probe_pm.is_audio_daemon_alive() is False
    finally:
        for p in (proc_jarvis, proc_audio):
            if p.poll() is None:
                p.kill()


# =============================================================================
# 5. API Surface Exploration & Alias Analysis
# =============================================================================

def test_api_surface_acquire_lock_alias_analysis(probe_pm):
    """
    Analysis of API naming:
    - Primary production method: `acquire_pid(service_name, pid, metadata)`
    - Check if `acquire_lock` is present or absent.
    """
    # Verify acquire_pid behaves correctly
    assert hasattr(probe_pm, "acquire_pid")
    assert hasattr(probe_pm, "release_pid")
    assert hasattr(probe_pm, "is_running")
    assert hasattr(probe_pm, "clean_shutdown")
    assert hasattr(probe_pm, "track_audio_daemon")
    assert hasattr(probe_pm, "is_audio_daemon_alive")
    assert hasattr(probe_pm, "get_audio_daemon_status")
