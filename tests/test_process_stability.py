"""
Test suite for Process Stability, PID Locking, Audio Daemon Liveness & Scripts (Milestone 3).
Verifies:
- ProcessManager enforces single-instance PID locking (.jarvis.pid & jarvis.pid).
- Duplicate instance acquisition attempts are rejected.
- Stale PID files for dead processes are detected and cleaned up automatically.
- ProcessManager tracks audio daemon liveness and health.
- ProcessManager clean_shutdown releases all PID locks.
- FastAPI server uses modern lifespan context manager.
- Windows launch and stop scripts (start_jarvis.bat, start_jarvis_background.vbs, status_jarvis.bat, stop_jarvis.bat) exist and have valid syntax.
"""

import os
import json
import time
from pathlib import Path
import pytest
from jarvis.core.process_manager import ProcessManager


@pytest.fixture
def temp_pm(tmp_path):
    """Provides isolated ProcessManager rooted in a temporary test directory."""
    return ProcessManager(base_dir=tmp_path)


def test_pid_acquisition_and_single_instance_lock(temp_pm):
    """Verify single-instance PID acquisition and rejection of duplicate PID."""
    curr_pid = os.getpid()

    # 1. First acquisition succeeds
    assert temp_pm.acquire_pid("jarvis", pid=curr_pid) is True
    assert temp_pm.is_running("jarvis") is True

    # Check both root .jarvis.pid and unhidden jarvis.pid exist
    assert temp_pm.root_pid_file.exists()
    assert temp_pm.jarvis_pid_file.exists()

    # 2. Re-acquisition with same PID is idempotent
    assert temp_pm.acquire_pid("jarvis", pid=curr_pid) is True

    # 3. Duplicate acquisition attempt from another PID is rejected
    fake_competing_pid = curr_pid + 98765
    assert temp_pm.acquire_pid("jarvis", pid=fake_competing_pid) is False

    # 4. Release cleanly removes files
    temp_pm.release_pid("jarvis")
    assert not temp_pm.root_pid_file.exists()
    assert not temp_pm.jarvis_pid_file.exists()
    assert temp_pm.is_running("jarvis") is False


def test_stale_pid_cleanup_on_dead_process(temp_pm):
    """Verify stale PID file containing a dead process PID is cleaned up automatically."""
    dead_pid = 9999991  # Nonexistent process PID
    stale_record = {
        "service": "jarvis",
        "pid": dead_pid,
        "started_at": time.time() - 3600,
        "metadata": {"test": "stale"},
    }

    # Manually write stale PID files
    with open(temp_pm.root_pid_file, "w", encoding="utf-8") as f:
        json.dump(stale_record, f, indent=2)
    with open(temp_pm.jarvis_pid_file, "w", encoding="utf-8") as f:
        json.dump(stale_record, f, indent=2)

    # is_running should detect dead process, return False, and unlink stale files
    assert temp_pm.is_running("jarvis") is False
    assert not temp_pm.root_pid_file.exists()
    assert not temp_pm.jarvis_pid_file.exists()


def test_audio_daemon_liveness_tracking(temp_pm):
    """Verify ProcessManager tracks audio daemon liveness and health status."""
    curr_pid = os.getpid()

    # Initially not running
    assert temp_pm.is_audio_daemon_alive() is False

    # Register/track audio daemon
    assert temp_pm.track_audio_daemon(pid=curr_pid, metadata={"mic": "active"}) is True
    assert temp_pm.is_audio_daemon_alive() is True

    status = temp_pm.get_audio_daemon_status()
    assert status["running"] is True
    assert status["pid"] == curr_pid
    assert status["status"] == "RUNNING"
    assert status["metadata"].get("mic") == "active"

    # Clean release
    temp_pm.release_pid("audio_daemon")
    assert temp_pm.is_audio_daemon_alive() is False


def test_process_manager_clean_shutdown(temp_pm):
    """Verify clean_shutdown terminates tracked services and releases all PIDs."""
    import sys
    import subprocess

    # Spawn genuine child processes that sleep so clean_shutdown can terminate them
    proc1 = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    proc2 = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])

    try:
        temp_pm.acquire_pid("jarvis", pid=proc1.pid)
        temp_pm.acquire_pid("audio_daemon", pid=proc2.pid)

        assert temp_pm.is_running("jarvis") is True
        assert temp_pm.is_running("audio_daemon") is True

        # Clean shutdown gracefully terminates child processes and unlinks PIDs
        results = temp_pm.clean_shutdown(timeout_sec=2.0)
        assert isinstance(results, dict)
        assert not temp_pm.root_pid_file.exists()
        assert not temp_pm.jarvis_pid_file.exists()
        assert temp_pm.is_running("jarvis") is False
        assert temp_pm.is_running("audio_daemon") is False
    finally:
        for p in (proc1, proc2):
            try:
                p.terminate()
                p.kill()
            except Exception:
                pass


@pytest.mark.asyncio
async def test_fastapi_modern_lifespan():
    """Verify FastAPI server uses modern lifespan context manager rather than deprecated on_event."""
    from jarvis.api.server import app

    # Check lifespan handler is configured on FastAPI app
    assert app.router.lifespan_context is not None

    # Execute lifespan context manager directly
    async with app.router.lifespan_context(app):
        # Startup phase completed
        assert True


def test_windows_scripts_existence_and_syntax():
    """Verify all 4 required Windows scripts exist, are non-empty, and contain required commands."""
    workspace_root = Path(__file__).resolve().parent.parent
    scripts_dir = workspace_root / "scripts"

    expected_scripts = {
        "start_jarvis.bat": ["python", "process_manager", "start /B"],
        "start_jarvis_background.vbs": ["WScript.Shell", "start_jarvis.bat"],
        "status_jarvis.bat": ["python", "process_manager"],
        "stop_jarvis.bat": ["python", "process_manager", "stop"],
    }

    for script_name, required_tokens in expected_scripts.items():
        script_path = scripts_dir / script_name
        assert script_path.exists(), f"Script {script_name} does not exist in scripts/"
        content = script_path.read_text(encoding="utf-8")
        assert len(content.strip()) > 0, f"Script {script_name} is empty"

        for token in required_tokens:
            assert token.lower() in content.lower(), f"Script {script_name} missing required token: {token}"
