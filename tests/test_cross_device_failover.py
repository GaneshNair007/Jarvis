"""
Automated Integration Test Suite: Cross-Device Task Queue & Presence-Aware Remote Execution Failover
=====================================================================================================
Covers Requirement R2:
1. Canonical Profile Integration (+91 9324094474, laptop/phone devices).
2. Persistent SQLite WAL CrossDeviceTaskQueue and strict State Machine (QUEUED -> TRANSFERRED -> EXECUTING -> COMPLETED/FAILED).
3. PresenceManager Heartbeat & Availability Monitoring.
4. RemoteRouter Presence-Aware Routing (Laptop Offline -> Phone; Phone Offline -> Laptop).
5. Bidirectional Transport Failover (WhatsApp <-> Switch Protocol Bridge).
6. FastAPI Inbound Webhook Gateways with Security Rejection for Unauthorized Numbers.
7. End-to-End Execution Flow on Host Laptop.
"""

import asyncio
import os
import time
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
from jarvis.api.routes_crossdevice import router as crossdevice_router


@pytest.fixture
def temp_db(tmp_path):
    """Provides isolated temporary SQLite database for queue testing."""
    db_file = tmp_path / "test_cross_device.db"
    return db_file


@pytest.fixture
def queue(temp_db):
    """Provides isolated CrossDeviceTaskQueue instance."""
    return CrossDeviceTaskQueue(db_path=temp_db)


@pytest.fixture
def presence():
    """Provides fresh PresenceManager instance."""
    return PresenceManager()


@pytest.fixture
def test_client():
    """Provides FastAPI test client with crossdevice routes mounted."""
    app = FastAPI(title="Test Cross-Device API")
    app.include_router(crossdevice_router)
    return TestClient(app)


# ── 1. Profile & Presence Configuration Tests ─────────────────────────────────

def test_canonical_profile_and_phone(presence):
    """Verifies profile loads canonical phone +91 9324094474 and device profiles."""
    assert "+91 9324094474" in presence.canonical_phone or "+919324094474" in presence.canonical_phone
    assert DeviceType.LAPTOP.value in presence.devices
    assert DeviceType.PHONE.value in presence.devices

    phone_dev = presence.devices[DeviceType.PHONE.value]
    assert phone_dev.phone_number is not None
    assert "9324094474" in phone_dev.phone_number
    assert phone_dev.preferred_transport == "whatsapp"
    assert phone_dev.fallback_transport == "switch"


# ── 2. Cross-Device Task Queue State Machine Tests ────────────────────────────

def test_queue_state_machine_happy_path(queue):
    """
    Verifies valid lifecycle:
    QUEUED -> TRANSFERRED -> EXECUTING -> COMPLETED
    """
    task = queue.enqueue_task(
        command="Scaffold AI Hackathon Project",
        source_device="phone",
        transport="whatsapp",
        sender_id="+919324094474",
        priority="HIGH",
    )
    assert task.status == TaskStatus.QUEUED.value
    assert task.retry_count == 0

    # Claim task -> TRANSFERRED
    claimed = queue.claim_next_task(worker_id="laptop_worker", target_device="laptop")
    assert claimed is not None
    assert claimed.task_id == task.task_id
    assert claimed.status == TaskStatus.TRANSFERRED.value
    assert claimed.claimed_at is not None

    # Start execution -> EXECUTING
    executing = queue.start_execution(task.task_id)
    assert executing.status == TaskStatus.EXECUTING.value

    # Complete task -> COMPLETED
    completed = queue.complete_task(task.task_id, result={"output": "Repo scaffolded"})
    assert completed.status == TaskStatus.COMPLETED.value
    assert completed.result == {"output": "Repo scaffolded"}
    assert completed.completed_at is not None


def test_queue_illegal_transition_rejected(queue):
    """Verifies that skipping states (e.g. QUEUED directly to COMPLETED) is strictly rejected."""
    task = queue.enqueue_task(command="Direct complete test")
    assert task.status == TaskStatus.QUEUED.value

    # Attempt illegal jump: QUEUED -> COMPLETED
    with pytest.raises(ValueError, match="Illegal state transition"):
        queue.transition_status(task.task_id, TaskStatus.COMPLETED)

    # Attempt illegal jump: QUEUED -> EXECUTING
    with pytest.raises(ValueError, match="Illegal state transition"):
        queue.transition_status(task.task_id, TaskStatus.EXECUTING)


def test_queue_priority_ordering(queue):
    """Verifies that tasks with higher priority are claimed first regardless of enqueue time."""
    t_low = queue.enqueue_task(command="Low priority task", priority="LOW")
    t_high = queue.enqueue_task(command="High priority task", priority="HIGH")
    t_crit = queue.enqueue_task(command="Critical priority task", priority="CRITICAL")

    first = queue.claim_next_task()
    assert first is not None
    assert first.task_id == t_crit.task_id

    second = queue.claim_next_task()
    assert second is not None
    assert second.task_id == t_high.task_id

    third = queue.claim_next_task()
    assert third is not None
    assert third.task_id == t_low.task_id


def test_queue_retry_and_failure_semantics(queue):
    """Verifies retryable failure increments retry count and resets to QUEUED, then FAILED when exhausted."""
    task = queue.enqueue_task(command="Flaky command", max_retries=2)
    queue.claim_next_task()

    # Attempt 1: retryable
    t1 = queue.fail_task(task.task_id, error="Network glitch", retryable=True)
    assert t1.status == TaskStatus.QUEUED.value
    assert t1.retry_count == 1

    # Claim again
    queue.claim_next_task()

    # Attempt 2: retryable, but max_retries reached
    t2 = queue.fail_task(task.task_id, error="Terminal failure", retryable=True)
    assert t2.status == TaskStatus.FAILED.value
    assert t2.error_message == "Terminal failure"
    assert t2.completed_at is not None


# ── 3. Presence Monitoring Tests ──────────────────────────────────────────────

def test_presence_heartbeat_and_timeout(presence):
    """Verifies presence tracking, TTL expiration, and manual status override."""
    # Active heartbeat
    now = time.time()
    presence.record_heartbeat("laptop", timestamp=now)
    assert presence.is_device_online("laptop") is True

    # Simulate expired heartbeat
    presence.devices["laptop"].last_heartbeat = now - 300.0  # 5 minutes ago (TTL=60s)
    assert presence.is_device_online("laptop") is False
    assert presence.devices["laptop"].evaluate_status() == PresenceState.OFFLINE.value

    # Manual status override
    presence.set_device_status("laptop", PresenceState.ONLINE.value, reason="Test override")
    assert presence.is_device_online("laptop") is True

    presence.set_device_status("laptop", PresenceState.OFFLINE.value, reason="Simulated sleep")
    assert presence.is_device_online("laptop") is False


# ── 4. Presence-Aware Notification Routing Tests ──────────────────────────────

@pytest.mark.asyncio
async def test_presence_routing_laptop_offline_routes_to_phone(presence):
    """
    Rule 1 Verification:
    When the laptop is OFFLINE, notifications MUST automatically route to the phone.
    """
    presence.set_device_status("laptop", "OFFLINE", reason="Host laptop asleep")
    presence.set_device_status("phone", "ONLINE")

    mock_toast_called = []
    router = RemoteRouter(presence_mon=presence)
    router.set_desktop_notifier(lambda t, m: mock_toast_called.append((t, m)) or True)

    # Route a notification
    res = await router.route_notification(
        title="Hackathon Alert",
        message="AI Agent track closes in 2 hours",
        priority="normal",
    )

    assert res.success is True
    assert res.delivered_to == "phone"
    assert res.channel_used in ("whatsapp", "switch")
    assert len(mock_toast_called) == 0  # Should NOT attempt toast on offline laptop


@pytest.mark.asyncio
async def test_presence_routing_phone_offline_falls_back_to_laptop(presence):
    """
    Rule 2 Verification:
    When phone delivery fails, notifications MUST route to the host laptop desktop toast.
    """
    presence.set_device_status("laptop", "ONLINE")
    presence.set_device_status("phone", "OFFLINE")

    mock_wa = WhatsAppDispatcher()
    # Force mock WhatsApp to throw error
    def _failing_wa(num, msg):
        raise httpx.ConnectTimeout("Cellular network unreachable")
    mock_wa.transport_hook = _failing_wa

    # Disable Switch to simulate complete phone delivery failure
    mock_switch = SwitchIntegration()
    mock_switch.enabled = False

    mock_toast_called = []
    router = RemoteRouter(
        presence_mon=presence,
        whatsapp_disp=mock_wa,
        switch_int=mock_switch,
    )
    router.set_desktop_notifier(lambda t, m: mock_toast_called.append((t, m)) or True)

    res = await router.route_notification(
        title="Build Complete",
        message="Antigravity project built successfully",
        target="phone",
    )

    assert res.success is True
    assert res.delivered_to == "laptop"
    assert res.channel_used == "windows_toast"
    assert res.failover_occurred is True
    assert len(mock_toast_called) == 1
    assert mock_toast_called[0][0] == "Build Complete"


# ── 5. Transport Failover Engine Tests (WhatsApp <-> Switch) ──────────────────

@pytest.mark.asyncio
async def test_failover_whatsapp_to_switch_on_network_error(presence):
    """
    Verifies automatic failover from WhatsApp to Switch:
    When WhatsApp encounters an HTTP timeout or network error,
    RemoteRouter seamlessly fails over to Switch Protocol bridge.
    """
    presence.set_device_status("laptop", "OFFLINE")  # Forces phone routing
    presence.set_device_status("phone", "ONLINE")

    mock_wa = WhatsAppDispatcher()
    def _wa_timeout(num, msg):
        raise httpx.ConnectTimeout("CallMeBot/Twilio gateway timed out (504)")
    mock_wa.transport_hook = _wa_timeout

    mock_switch = SwitchIntegration()
    mock_switch.enabled = True

    router = RemoteRouter(
        presence_mon=presence,
        whatsapp_disp=mock_wa,
        switch_int=mock_switch,
    )

    res = await router.route_notification(
        title="Failover Test",
        message="Testing dynamic failover to Switch",
        primary_transport="whatsapp",
    )

    assert res.success is True
    assert res.delivered_to == "phone"
    assert res.channel_used == "switch"
    assert res.failover_occurred is True
    assert "whatsapp_error" in res.details
    assert "Switch" in res.details["switch"]["message"] or res.details["switch"].get("data", {}).get("status") == "DISPATCHED"


@pytest.mark.asyncio
async def test_failover_switch_to_whatsapp_on_room_error(presence):
    """
    Verifies automatic failover from Switch to WhatsApp:
    When Switch Protocol bridge is disconnected or unavailable,
    RemoteRouter seamlessly fails over to WhatsApp Dispatcher.
    """
    presence.set_device_status("laptop", "OFFLINE")
    presence.set_device_status("phone", "ONLINE")

    mock_switch = SwitchIntegration()
    mock_switch.enabled = False  # Disabled Switch daemon

    mock_wa = WhatsAppDispatcher()
    delivered_msgs = []
    def _wa_ok(num, msg):
        delivered_msgs.append((num, msg))
        return {"status": "delivered", "channel": "mock_whatsapp"}
    mock_wa.transport_hook = _wa_ok

    router = RemoteRouter(
        presence_mon=presence,
        whatsapp_disp=mock_wa,
        switch_int=mock_switch,
    )

    res = await router.route_notification(
        title="Reverse Failover",
        message="Testing failover from Switch to WhatsApp",
        primary_transport="switch",
    )

    assert res.success is True
    assert res.delivered_to == "phone"
    assert res.channel_used == "whatsapp"
    assert res.failover_occurred is True
    assert "switch_error" in res.details
    assert len(delivered_msgs) == 1


# ── 6. Inbound Webhook API & Security Tests ───────────────────────────────────

def test_whatsapp_webhook_authorized_sender(test_client):
    """Verifies authorized phone (+91 9324094474) successfully enqueues command."""
    response = test_client.post(
        "/api/v1/crossdevice/whatsapp/webhook",
        json={
            "From": "+919324094474",
            "Body": "BUILD: Autonomous Search Engine",
            "priority": "HIGH",
            "execute_now": False,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "QUEUED"
    assert data["command"] == "BUILD: Autonomous Search Engine"
    assert data["task_id"].startswith("cdt_")


def test_whatsapp_webhook_unauthorized_sender_rejected(test_client):
    """Verifies unauthorized sender number is rejected with HTTP 403 Forbidden."""
    response = test_client.post(
        "/api/v1/crossdevice/whatsapp/webhook",
        json={
            "From": "+15550199234",
            "Body": "rm -rf /",
            "priority": "CRITICAL",
            "execute_now": False,
        },
    )
    assert response.status_code == 403
    assert "Security violation" in response.json()["detail"] or "not authorized" in response.json()["detail"]


def test_switch_webhook_ingestion(test_client):
    """Verifies Switch room webhook ingests team room task."""
    response = test_client.post(
        "/api/v1/crossdevice/switch/webhook",
        json={
            "room_id": "hackathon-war-room",
            "sender": "ganesh",
            "command": "Scaffold FastMCP bridge",
            "priority": "HIGH",
            "execute_now": False,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "QUEUED"
    assert data["source"] == "switch"
    assert data["room_id"] == "hackathon-war-room"


def test_presence_api_endpoints(test_client):
    """Verifies presence telemetry and heartbeat submission endpoints."""
    # 1. Query presence
    resp = test_client.get("/api/v1/crossdevice/presence")
    assert resp.status_code == 200
    pdata = resp.json()
    assert "devices" in pdata
    assert "laptop" in pdata["devices"]
    assert "phone" in pdata["devices"]

    # 2. Submit heartbeat
    hb_resp = test_client.post(
        "/api/v1/crossdevice/presence/heartbeat",
        json={"device_id": "phone", "metadata": {"battery": 88}},
    )
    assert hb_resp.status_code == 200
    assert hb_resp.json()["status"] == "RECORDED"


# ── 7. End-to-End Task Flow on Host Laptop ────────────────────────────────────

@pytest.mark.asyncio
async def test_end_to_end_remote_task_execution(queue):
    """
    Verifies that a task issued from the phone is transferred,
    executed locally, and marked COMPLETED with verified result payload.
    """
    task = queue.enqueue_task(
        command="Run security vulnerability audit",
        source_device="phone",
        transport="whatsapp",
        sender_id="+919324094474",
    )

    # Mock local executor
    async def _mock_executor(cmd: str):
        return {"status": "success", "scanned_files": 42, "threats_found": 0}

    executed_task = await queue.execute_task_flow(task.task_id, executor_fn=_mock_executor)

    assert executed_task.status == TaskStatus.COMPLETED.value
    assert executed_task.result["status"] == "success"
    assert executed_task.result["scanned_files"] == 42
    assert executed_task.completed_at is not None
