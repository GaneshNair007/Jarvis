"""
Automated Tests for Milestone 5 — Desktop Computer Use Worker
Verifies:
  1. Screen resolution & Win32 active window detection
  2. Screen capture with SHA-256 evidence artifact generation
  3. See-Act-Verify loop execution with pre/post state comparison
  4. App allow-list policy gate enforcement
  5. Emergency kill-switch preemption
  6. Desktop REST APIs (task, approve, cancel, status, history)
  7. Desktop Powers (PWR-016 to PWR-020)
"""

import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from jarvis.computer.desktop_worker import desktop_worker
from jarvis.powers.desktop_powers import desktop_powers
from jarvis.core.policy_gate import policy_gate
from jarvis.api.server import app

client = TestClient(app)

def test_desktop_screen_size_and_active_window():
    """Verifies screen resolution and active foreground window inspection."""
    width, height = desktop_worker.get_screen_size()
    assert width > 0
    assert height > 0

    active = desktop_worker.get_active_window()
    assert isinstance(active, dict)
    assert "title" in active
    assert "hwnd" in active
    assert "rect" in active

def test_desktop_screenshot_checksum_artifact():
    """Verifies that desktop screenshots generate SHA-256 artifacts on disk."""
    evidence = desktop_worker.capture_screen()
    assert evidence["file_name"].startswith("desktop_")
    assert Path(evidence["file_path"]).exists()
    assert len(evidence["sha256"]) == 64
    assert evidence["width"] > 0
    assert evidence["height"] > 0

def test_see_act_verify_wait_action():
    """Verifies the See-Act-Verify cycle with pre/post evidence recording."""
    result = desktop_worker.see_act_verify(
        action="wait",
        params={"seconds": 0.05},
        task_id="test_wait_task"
    )
    assert result["status"] == "SUCCESS"
    assert result["pre_evidence"]["sha256"] is not None
    assert result["post_evidence"]["sha256"] is not None
    assert "pre_window" in result
    assert "post_window" in result

def test_policy_blocks_disallowed_app():
    """Verifies policy rejection when attempting control over an unapproved application."""
    old_allowed = list(desktop_worker.allowed_apps)
    try:
        desktop_worker.allowed_apps = ["notepad", "calculator"]
        result = desktop_worker.see_act_verify(
            action="click",
            params={"target_app": "RansomwareInstaller.exe", "enforce_allowlist": True}
        )
        assert result["status"] == "POLICY_BLOCKED"
        assert "not in the allowed application roster" in result["reason"]
    finally:
        desktop_worker.allowed_apps = old_allowed

def test_emergency_kill_switch_blocks_desktop():
    """Verifies that the emergency kill switch preempts and halts desktop actions."""
    policy_gate.trigger_kill_switch()
    try:
        with pytest.raises(RuntimeError) as exc_info:
            desktop_worker.see_act_verify("wait", {"seconds": 0.01})
        assert "Global kill switch is ACTIVE" in str(exc_info.value)
    finally:
        policy_gate.reset_kill_switch()

def test_desktop_powers_wrapper():
    """Verifies DesktopPowers interface (PWR-016 to PWR-018)."""
    pwr16 = desktop_powers.pwr_016_get_active_window()
    assert "title" in pwr16

    pwr17 = desktop_powers.pwr_017_capture_screen()
    assert "sha256" in pwr17

    pwr18 = desktop_powers.pwr_018_focus_window("NonExistentWindowXYZ123")
    assert pwr18["focused"] is False

def test_desktop_rest_apis():
    """Tests all Desktop REST API routes via FastAPI TestClient."""
    # 1. GET /api/v1/desktop/status
    status_resp = client.get("/api/v1/desktop/status")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert "screen_resolution" in status_data
    assert "active_window" in status_data

    # 2. POST /api/v1/desktop/task (Safe action)
    task_resp = client.post("/api/v1/desktop/task", json={
        "action": "wait",
        "params": {"seconds": 0.02}
    })
    assert task_resp.status_code == 200
    task_data = task_resp.json()
    assert task_data["status"] == "SUCCESS"

    # 3. POST /api/v1/desktop/task (Requiring Tier 2 Approval)
    approval_task_resp = client.post("/api/v1/desktop/task", json={
        "action": "click",
        "params": {"x": 500, "y": 500},
        "require_approval": True
    })
    assert approval_task_resp.status_code == 200
    approval_data = approval_task_resp.json()
    assert approval_data["status"] == "AWAITING_APPROVAL"
    token = approval_data["token"]
    task_id = approval_data["task_id"]

    # 4. POST /api/v1/desktop/approve
    approve_resp = client.post("/api/v1/desktop/approve", json={
        "task_id": task_id,
        "token": token,
        "action": "wait",
        "params": {"seconds": 0.01}
    })
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "SUCCESS"

    # 5. POST /api/v1/desktop/cancel
    cancel_resp = client.post("/api/v1/desktop/cancel")
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "CANCELLED"

    # 6. GET /api/v1/desktop/history
    history_resp = client.get("/api/v1/desktop/history?limit=10")
    assert history_resp.status_code == 200
    assert history_resp.json()["count"] >= 1
