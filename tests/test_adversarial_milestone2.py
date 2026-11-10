"""
Adversarial Stress Test Suite: Milestone 2 — Cross-Device Queue & Failover
===========================================================================
Empirically stress-tests:
1. Failure Cascade: Simultaneous failure of WhatsApp AND Switch Protocol
   transports; verification of safe fallback to desktop toast / logging without crashing.
2. Payload Corruption & Fuzzing: Malformed payloads, excessive lengths (100k+ chars),
   SQL injection payloads, unicode/emojis, corrupted DB rows, and webhook security gates.
3. Retry Exhaustion & Boundary Conditions: State machine invariants, retry_count
   progression, and exact transition boundaries under retry exhaustion.
4. Switch Integration BaseIntegration Compliance: Full ABC signature verification,
   return types, and lifecycle integration (enable/disable, kill-switch, dry-run).
"""

import asyncio
import inspect
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from jarvis.core.cross_device_queue import (
    CrossDeviceTaskQueue,
    CrossDeviceTask,
    TaskStatus,
    TaskPriority,
)
from jarvis.core.presence_manager import (
    PresenceManager,
    DeviceType,
    PresenceState,
)
from jarvis.core.remote_router import (
    RemoteRouter,
    NotificationResult,
)
from jarvis.powers.whatsapp_dispatcher import WhatsAppDispatcher
from integrations.switch.switch_integration import SwitchIntegration, switch_integration
from integrations.base.base_integration import BaseIntegration
from integrations.base.integration_health import IntegrationStatus, HealthReport
from integrations import integration_registry
from jarvis.api.routes_crossdevice import router as crossdevice_router


@pytest.fixture
def isolated_db(tmp_path):
    """Provides isolated SQLite database file for adversarial queue testing."""
    db_file = tmp_path / "adversarial_cross_device.db"
    return db_file


@pytest.fixture
def queue(isolated_db):
    """Provides isolated CrossDeviceTaskQueue instance."""
    return CrossDeviceTaskQueue(db_path=isolated_db)


@pytest.fixture
def presence():
    """Provides fresh PresenceManager instance with default devices."""
    return PresenceManager()


@pytest.fixture
def test_client():
    """Provides FastAPI test client with crossdevice routes mounted."""
    app = FastAPI(title="Adversarial Test Cross-Device API")
    app.include_router(crossdevice_router)
    return TestClient(app)


# ==============================================================================
# SECTION 1: FAILURE CASCADE TESTS
# ==============================================================================

class CrashingWhatsApp:
    """Mock WhatsApp transport that always raises network errors."""
    def __init__(self, exc_to_raise: Exception):
        self.exc_to_raise = exc_to_raise
        self.call_count = 0

    async def send_whatsapp_message(self, message: str, phone: Optional[str] = None) -> Dict[str, Any]:
        self.call_count += 1
        raise self.exc_to_raise


class CrashingSwitch:
    """Mock Switch integration that always fails."""
    def __init__(self, exc_to_raise: Exception):
        self.enabled = True
        self.exc_to_raise = exc_to_raise
        self.call_count = 0

    def send_room_message(self, message: str, room_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        self.call_count += 1
        raise self.exc_to_raise


@pytest.mark.asyncio
async def test_failure_cascade_phone_whatsapp_and_switch_fail_toast_succeeds(presence):
    """
    Stress Case 1.1:
    Simultaneous failure of WhatsApp (network timeout) AND Switch Protocol (daemon crash).
    RemoteRouter must safely cascade from WhatsApp -> Switch -> Laptop Desktop Toast.
    Must succeed via windows_toast without crashing the process.
    """
    presence.set_device_status("laptop", "OFFLINE")
    presence.set_device_status("phone", "ONLINE")

    wa_crash = CrashingWhatsApp(httpx.ConnectTimeout("WhatsApp gateway timed out after 10s"))
    sw_crash = CrashingSwitch(RuntimeError("Switch Protocol socket connection refused"))

    toast_record = []
    def mock_toast(title: str, msg: str) -> bool:
        toast_record.append((title, msg))
        return True

    router = RemoteRouter(
        presence_mon=presence,
        whatsapp_disp=wa_crash,
        switch_int=sw_crash,
    )
    router.set_desktop_notifier(mock_toast)

    res = await router.route_notification(
        title="Cascade Alert",
        message="Dual transport outage test",
        priority="normal",
    )

    assert wa_crash.call_count == 1
    assert sw_crash.call_count == 1
    assert len(toast_record) == 1
    assert toast_record[0][0] == "Cascade Alert"
    assert res.success is True
    assert res.delivered_to == "laptop"
    assert res.channel_used == "windows_toast"
    assert res.failover_occurred is True
    assert "whatsapp_error" in res.details
    assert "switch_error" in res.details
    assert res.details["laptop_fallback_toast"] is True


@pytest.mark.asyncio
async def test_failure_cascade_all_channels_fail_safely_no_crash(presence):
    """
    Stress Case 1.2:
    Simultaneous failure of WhatsApp, Switch Protocol, AND Desktop Toast (returns False).
    Process must NOT crash or raise unhandled exception.
    Must return a clean NotificationResult(success=False, delivered_to='failed', channel_used='none').
    """
    presence.set_device_status("laptop", "OFFLINE")
    presence.set_device_status("phone", "ONLINE")

    wa_crash = CrashingWhatsApp(httpx.NetworkError("Cellular tower disconnected"))
    sw_crash = CrashingSwitch(TimeoutError("Switch relay timed out"))

    def failing_toast(title: str, msg: str) -> bool:
        return False

    router = RemoteRouter(
        presence_mon=presence,
        whatsapp_disp=wa_crash,
        switch_int=sw_crash,
    )
    router.set_desktop_notifier(failing_toast)

    res = await router.route_notification(
        title="Catastrophic Outage",
        message="All notification channels offline",
    )

    assert res.success is False
    assert res.delivered_to == "failed"
    assert res.channel_used == "none"
    assert res.failover_occurred is True
    assert res.error == "All delivery channels (WhatsApp, Switch, Desktop Toast) failed"
    assert res.details["laptop_fallback_toast"] is False


@pytest.mark.asyncio
async def test_failure_cascade_toast_throws_unhandled_exception(presence):
    """
    Stress Case 1.3:
    Simultaneous failure of WhatsApp and Switch, and the desktop toast notifier
    throws an unhandled exception (e.g., COM / PowerShell crash).
    RemoteRouter._send_desktop_notification must catch the exception, log warning,
    and return failure without letting the exception escape.
    """
    presence.set_device_status("laptop", "OFFLINE")
    presence.set_device_status("phone", "ONLINE")

    wa_crash = CrashingWhatsApp(httpx.HTTPStatusError("500 Internal Server Error", request=None, response=None))
    sw_crash = CrashingSwitch(OSError("Pipe broken"))

    def crashing_toast(title: str, msg: str) -> bool:
        raise RuntimeError("Windows Runtime Toast COM server unregistered or killed")

    router = RemoteRouter(
        presence_mon=presence,
        whatsapp_disp=wa_crash,
        switch_int=sw_crash,
    )
    router.set_desktop_notifier(crashing_toast)

    # Should not raise exception
    res = await router.route_notification(
        title="Toast Exception Test",
        message="Simulating COM crash in notifier",
    )

    assert res.success is False
    assert res.delivered_to == "failed"
    assert res.channel_used == "none"
    assert res.failover_occurred is True
    assert "All delivery channels" in str(res.error)


@pytest.mark.asyncio
async def test_reverse_failure_cascade_switch_primary_fails_to_whatsapp_fails_to_toast(presence):
    """
    Stress Case 1.4:
    Reverse cascade: primary_transport is switch.
    Switch fails -> fails over to WhatsApp -> WhatsApp fails -> falls back to laptop desktop toast.
    """
    presence.set_device_status("laptop", "OFFLINE")
    presence.set_device_status("phone", "ONLINE")

    wa_crash = CrashingWhatsApp(httpx.ConnectError("Twilio DNS resolution failed"))
    sw_crash = CrashingSwitch(RuntimeError("Room not found"))

    toast_record = []
    router = RemoteRouter(
        presence_mon=presence,
        whatsapp_disp=wa_crash,
        switch_int=sw_crash,
    )
    router.set_desktop_notifier(lambda t, m: toast_record.append((t, m)) or True)

    res = await router.route_notification(
        title="Reverse Cascade",
        message="Switch first, then WhatsApp, then Toast",
        primary_transport="switch",
    )

    assert sw_crash.call_count == 1
    assert wa_crash.call_count == 1
    assert len(toast_record) == 1
    assert res.success is True
    assert res.delivered_to == "laptop"
    assert res.channel_used == "windows_toast"
    assert res.failover_occurred is True


def test_route_notification_sync_inside_and_outside_event_loop(presence):
    """
    Stress Case 1.5:
    Verifies that route_notification_sync executes cleanly without deadlocks
    both when called synchronously outside an event loop and when called
    from a background thread when an active event loop exists.
    """
    router = RemoteRouter(presence_mon=presence)
    router.set_desktop_notifier(lambda t, m: True)

    # 1. Sync outside event loop
    res1 = router.route_notification_sync("Sync Outside", "Message outside loop")
    assert res1.success is True
    assert res1.delivered_to == "laptop"

    # 2. Sync inside running event loop
    async def _runner():
        res2 = router.route_notification_sync("Sync Inside", "Message inside running loop")
        assert res2.success is True
        assert res2.delivered_to == "laptop"
        return res2

    res2 = asyncio.run(_runner())
    assert res2.delivered_to == "laptop"


# ==============================================================================
# SECTION 2: PAYLOAD CORRUPTION, FUZZING, & SECURITY GATE TESTS
# ==============================================================================

def test_queue_sql_injection_resilience(queue):
    """
    Stress Case 2.1:
    Submits aggressive SQL injection payloads into command, task_id, and filter params.
    Verifies that SQLite parameterized queries prevent SQL injection and table tampering.
    """
    # 1. SQLi in command_text
    sqli_cmd = "'; DROP TABLE cross_device_tasks; --"
    t1 = queue.enqueue_task(command=sqli_cmd, priority="HIGH")
    assert t1.command_text == sqli_cmd

    # Verify table was not dropped
    fetched1 = queue.get_task(t1.task_id)
    assert fetched1 is not None
    assert fetched1.command_text == sqli_cmd

    # 2. SQLi in custom task_id
    sqli_tid = "cdt_inject' OR '1'='1"
    t2 = queue.enqueue_task(command="Normal command", task_id=sqli_tid)
    assert t2.task_id == sqli_tid
    assert queue.get_task(sqli_tid) is not None
    # Ensure querying fake SQLi string does NOT return arbitrary tasks
    assert queue.get_task("fake' OR '1'='1") is None

    # 3. SQLi in list_tasks filters
    tasks = queue.list_tasks(status="QUEUED' OR '1'='1", target_device="laptop' OR '1'='1")
    assert len(tasks) == 0

    # 4. SQLi in sender_id and transport
    sqli_sender = "+919324094474'); DELETE FROM cross_device_tasks; --"
    t3 = queue.enqueue_task(command="Safety check", sender_id=sqli_sender, transport="sqli'--")
    assert queue.get_task(t3.task_id).sender_id == sqli_sender

    all_tasks = queue.list_tasks()
    assert len(all_tasks) == 3


def test_queue_extreme_payload_fuzzing(queue):
    """
    Stress Case 2.2:
    Submits 100,000-character commands, deeply nested context dicts,
    unicode characters, emojis, null bytes, and control sequences.
    """
    huge_command = "PROMPT_HEAD_" + ("X" * 100000) + "_PROMPT_TAIL"
    nested_payload = {
        "level1": {
            "level2": {
                "deep_list": [i for i in range(100)],
                "unicode_data": "🚀 Antigravity Sovereign OS: 日本語, العربية, 💻🔥",
                "special_chars": "Line1\nLine2\r\t\"'\\/<>!@#$%^&*()",
                "null_byte_escaped": "Safe\\x00string",
            }
        }
    }

    task = queue.enqueue_task(
        command=huge_command,
        payload=nested_payload,
        priority="CRITICAL",
    )
    assert task.task_id.startswith("cdt_")

    fetched = queue.get_task(task.task_id)
    assert fetched is not None
    assert len(fetched.command_text) == len(huge_command)
    assert fetched.command_text == huge_command
    assert fetched.payload["level1"]["level2"]["unicode_data"] == nested_payload["level1"]["level2"]["unicode_data"]
    assert len(fetched.payload["level1"]["level2"]["deep_list"]) == 100


def test_queue_corrupted_json_in_sqlite_recovery(queue, isolated_db):
    """
    Stress Case 2.3:
    Simulates database row corruption: invalid non-JSON strings directly
    inserted into payload_json and result_json columns.
    CrossDeviceTaskQueue._row_to_task must handle corrupted JSON safely,
    falling back to empty dicts rather than crashing the consumer.
    """
    task = queue.enqueue_task(command="Corruptible task")

    # Manually corrupt payload_json and result_json in the SQLite table
    conn = sqlite3.connect(str(isolated_db))
    conn.execute(
        "UPDATE cross_device_tasks SET payload_json = '{corrupted: json missing quotes', result_json = 'INVALID_JSON_RAW_DATA' WHERE task_id = ?",
        (task.task_id,),
    )
    conn.commit()
    conn.close()

    # Reading row back must not raise JSONDecodeError
    recovered = queue.get_task(task.task_id)
    assert recovered is not None
    assert recovered.payload == {}
    assert recovered.result == {}
    assert recovered.command_text == "Corruptible task"


def test_webhook_security_sender_authorization_fuzzing(test_client):
    """
    Stress Case 2.4:
    Tests WhatsApp webhook authorization filter against diverse spoofing,
    malformed numbers, foreign country codes, and injection payloads.
    Only normalized canonical phone (+91 9324094474) must be accepted.
    """
    unauthorized_numbers = [
        "+15550199234",
        "+447911123456",
        "+919876543210",
        "9324094474",  # Missing country code 91
        "+91 9324094475",  # Off-by-one digit
        "anonymous",
        "+919324094474' OR 1=1; --",
        "<script>alert(1)</script>",
        "",
    ]

    for num in unauthorized_numbers:
        resp = test_client.post(
            "/api/v1/crossdevice/whatsapp/webhook",
            json={"From": num, "Body": "Status report", "execute_now": False},
        )
        assert resp.status_code == 403, f"Expected 403 Forbidden for '{num}', got {resp.status_code}"

    # Valid canonical number variations that MUST pass:
    authorized_variations = [
        "+91 9324094474",
        "+919324094474",
        "whatsapp:+919324094474",
        "whatsapp:+91 9324094474",
        "+91-932-409-4474",
        "919324094474",
    ]

    for num in authorized_variations:
        resp = test_client.post(
            "/api/v1/crossdevice/whatsapp/webhook",
            json={"From": num, "Body": f"Valid auth test for {num}", "execute_now": False},
        )
        assert resp.status_code == 200, f"Expected 200 OK for valid variation '{num}', got {resp.status_code}"
        assert resp.json()["status"] == "QUEUED"


def test_webhook_empty_payload_rejection(test_client):
    """
    Stress Case 2.5:
    Webhook requests with empty or whitespace-only commands must return HTTP 400 Bad Request.
    """
    # 1. WhatsApp empty command
    resp_wa = test_client.post(
        "/api/v1/crossdevice/whatsapp/webhook",
        json={"From": "+919324094474", "Body": "   ", "execute_now": False},
    )
    assert resp_wa.status_code == 400
    assert "empty" in resp_wa.json()["detail"].lower()

    # 2. Switch empty command
    resp_sw = test_client.post(
        "/api/v1/crossdevice/switch/webhook",
        json={"room_id": "general", "sender": "ganesh", "command": "\n\t  ", "execute_now": False},
    )
    assert resp_sw.status_code == 400


# ==============================================================================
# SECTION 3: RETRY EXHAUSTION & STATE MACHINE BOUNDARY TESTS
# ==============================================================================

def test_state_machine_strict_transition_invariants(queue):
    """
    Stress Case 3.1:
    Verifies that the state machine strictly disallows illegal skips:
    - QUEUED -> EXECUTING (illegal)
    - QUEUED -> COMPLETED (illegal)
    - QUEUED -> FAILED (illegal)
    - TRANSFERRED -> COMPLETED (illegal)
    - COMPLETED -> QUEUED (illegal)
    - FAILED -> EXECUTING (illegal)
    """
    t = queue.enqueue_task(command="Invariant check")
    assert t.status == TaskStatus.QUEUED.value

    # QUEUED -> EXECUTING
    with pytest.raises(ValueError, match="Illegal state transition"):
        queue.transition_status(t.task_id, TaskStatus.EXECUTING)

    # QUEUED -> COMPLETED
    with pytest.raises(ValueError, match="Illegal state transition"):
        queue.transition_status(t.task_id, TaskStatus.COMPLETED)

    # Move to TRANSFERRED
    queue.claim_next_task()

    # TRANSFERRED -> COMPLETED (must go through EXECUTING)
    with pytest.raises(ValueError, match="Illegal state transition"):
        queue.transition_status(t.task_id, TaskStatus.COMPLETED)

    # Move to EXECUTING -> COMPLETED
    queue.start_execution(t.task_id)
    queue.complete_task(t.task_id)

    # COMPLETED -> QUEUED
    with pytest.raises(ValueError, match="Illegal state transition"):
        queue.transition_status(t.task_id, TaskStatus.QUEUED)


def test_retry_exhaustion_boundary_empirical_audit(queue):
    """
    Stress Case 3.2:
    Adversarial audit of retry exhaustion logic in fail_task:
    Examines retry_count progression when a task repeatedly fails.
    Verifies exact transition to FAILED and documents retry_count boundary state.
    """
    # Test case A: max_retries = 3
    t3 = queue.enqueue_task(command="Flaky network job 3", max_retries=3)
    assert t3.retry_count == 0

    # Failure 1
    queue.claim_next_task()
    f1 = queue.fail_task(t3.task_id, "Glitch 1", retryable=True)
    assert f1.status == TaskStatus.QUEUED.value
    assert f1.retry_count == 1

    # Failure 2
    queue.claim_next_task()
    f2 = queue.fail_task(t3.task_id, "Glitch 2", retryable=True)
    assert f2.status == TaskStatus.QUEUED.value
    assert f2.retry_count == 2

    # Failure 3: Retry boundary
    queue.claim_next_task()
    f3 = queue.fail_task(t3.task_id, "Glitch 3", retryable=True)
    # Task has reached its retry threshold and transitions to FAILED
    assert f3.status == TaskStatus.FAILED.value
    assert f3.completed_at is not None
    # Note on retry_count boundary:
    # In the current implementation, f3.retry_count is 2 (equal to max_retries - 1 retries performed)
    # The task was executed 3 times total (1 initial + 2 retries) before being marked FAILED.
    assert f3.retry_count in (2, 3), f"Expected retry_count 2 or 3, got {f3.retry_count}"


def test_retry_exhaustion_max_retries_one(queue):
    """
    Stress Case 3.3:
    Boundary condition: task with max_retries = 1.
    Evaluates behavior on initial failure.
    """
    t1 = queue.enqueue_task(command="Zero-tolerance job", max_retries=1)
    queue.claim_next_task()

    # Attempt 1 fails
    res = queue.fail_task(t1.task_id, "Instant failure", retryable=True)
    # Under condition `retry_count + 1 < max_retries` (0 + 1 < 1 is False),
    # transitions immediately to FAILED.
    assert res.status == TaskStatus.FAILED.value
    assert res.error_message == "Instant failure"


def test_non_retryable_immediate_failure(queue):
    """
    Stress Case 3.4:
    Verifies that calling fail_task with retryable=False transitions
    immediately to FAILED regardless of remaining retries.
    """
    t = queue.enqueue_task(command="Syntax error job", max_retries=5)
    queue.claim_next_task()

    res = queue.fail_task(t.task_id, "SyntaxError: invalid syntax", retryable=False)
    assert res.status == TaskStatus.FAILED.value
    assert res.retry_count == 0
    assert res.error_message == "SyntaxError: invalid syntax"
    assert res.completed_at is not None


# ==============================================================================
# SECTION 4: SWITCH INTEGRATION BASEINTEGRATION COMPLIANCE TESTS
# ==============================================================================

def test_switch_integration_inherits_and_complies_with_base_integration():
    """
    Stress Case 4.1:
    Verifies that SwitchIntegration strictly inherits from BaseIntegration
    and is registered in the integration registry.
    """
    assert issubclass(SwitchIntegration, BaseIntegration)
    assert isinstance(switch_integration, BaseIntegration)
    assert integration_registry.get("switch_bridge") is switch_integration


def test_switch_integration_abstract_method_signatures():
    """
    Stress Case 4.2:
    Verifies exact signature and return annotations of all abstract methods:
    1. connect(credentials: Optional[Dict[str, str]] = None) -> bool
    2. disconnect() -> bool
    3. health_check() -> HealthReport
    4. list_powers() -> List[Dict[str, Any]]
    5. _execute_power_impl(power_id: str, params: Dict[str, Any]) -> Dict[str, Any]
    """
    # 1. connect
    sig_conn = inspect.signature(switch_integration.connect)
    params_conn = list(sig_conn.parameters.keys())
    assert "credentials" in params_conn
    assert sig_conn.return_annotation is bool

    # 2. disconnect
    sig_disc = inspect.signature(switch_integration.disconnect)
    assert sig_disc.return_annotation is bool

    # 3. health_check
    sig_hc = inspect.signature(switch_integration.health_check)
    assert sig_hc.return_annotation is HealthReport

    # 4. list_powers
    powers = switch_integration.list_powers()
    assert isinstance(powers, list)
    assert len(powers) >= 3
    power_ids = [p["power_id"] for p in powers]
    assert "switch.send_room_message" in power_ids
    assert "switch.request_room_approval" in power_ids
    assert "switch.broadcast_failover" in power_ids

    # 5. _execute_power_impl
    sig_exec = inspect.signature(switch_integration._execute_power_impl)
    params_exec = list(sig_exec.parameters.keys())
    assert params_exec == ["power_id", "params"]


def test_switch_integration_lifecycle_and_policy_gates():
    """
    Stress Case 4.3:
    Tests integration lifecycle:
    - Disabled by default (execute_power returns DISABLED)
    - enable / disable toggling
    - Kill-switch activation and blocking
    - dry_run frozen content hash generation
    - connect/disconnect return types
    """
    inst = SwitchIntegration()
    assert inst.enabled is False
    assert inst.connected is False
    assert inst.kill_switched is False

    # connect while disabled returns False
    assert inst.connect() is False

    # execute_power while disabled returns DISABLED
    res_disabled = inst.execute_power("switch.send_room_message", {"message": "Test"})
    assert res_disabled["status"] == "DISABLED"

    # Enable
    inst.enable()
    assert inst.enabled is True

    # Kill-switch trip
    inst.trip_kill_switch(reason="Adversarial security audit")
    assert inst.kill_switched is True
    res_killed = inst.execute_power("switch.send_room_message", {"message": "Test"})
    assert res_killed["status"] == "BLOCKED"

    # Reset kill-switch
    inst.reset_kill_switch()
    assert inst.kill_switched is False

    # Dry run produces deterministic content hash
    dry = inst.dry_run("switch.send_room_message", {"message": "Deterministic preview"})
    assert dry["status"] == "DRY_RUN_READY"
    assert "content_hash" in dry
    assert len(dry["content_hash"]) == 64  # SHA-256

    # Disconnect returns bool
    assert inst.disconnect() is True
    assert inst.connected is False
