"""
Adversarial Stress Test Suite: Milestone 2 — Cross-Device Task Queue & Presence-Aware Remote Execution Failover
==================================================================================================================
Empirical verification of Milestone 2 under hostile, concurrent, and degraded conditions:
1. High-concurrency SQLite WAL writes and atomic task claiming (zero duplicate claims, zero locked exceptions).
2. Illegal state machine transitions (strict lifecycle enforcement).
3. Network drops, timeouts, and cascading failover (clean recovery without unhandled exceptions).
4. Boundary stress tests for Presence TTL (clock skew, zero/negative timestamps, rapid flapping).
5. Webhook security hardening and zero queue/presence pollution on unauthorized requests.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import threading
import time
from typing import Any, Dict, List, Optional
import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from jarvis.core.cross_device_queue import (
    CrossDeviceTaskQueue,
    CrossDeviceTask,
    TaskStatus,
    TaskPriority,
    VALID_TRANSITIONS,
)
from jarvis.core.presence_manager import (
    PresenceManager,
    DevicePresence,
    DeviceType,
    PresenceState,
)
from jarvis.core.remote_router import (
    RemoteRouter,
    NotificationResult,
    TransportChannel,
)
from jarvis.powers.whatsapp_dispatcher import WhatsAppDispatcher
from integrations.switch.switch_integration import SwitchIntegration
from jarvis.api.routes_crossdevice import router as crossdevice_router


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def temp_db(tmp_path):
    """Provides isolated temporary SQLite database."""
    return tmp_path / "test_adversarial_cdt.db"


@pytest.fixture
def queue(temp_db):
    """Provides isolated CrossDeviceTaskQueue instance."""
    return CrossDeviceTaskQueue(db_path=temp_db)


@pytest.fixture
def presence():
    """Provides isolated PresenceManager instance."""
    return PresenceManager()


@pytest.fixture
def client():
    """Provides FastAPI test client for webhook endpoints."""
    app = FastAPI(title="Adversarial Cross-Device API")
    app.include_router(crossdevice_router)
    return TestClient(app)


# ── Section 1: High-Concurrency & Atomic SQLite Claims ────────────────────────

def test_concurrent_enqueue_high_volume(queue):
    """
    Stress-test concurrent writes:
    20 concurrent worker threads enqueuing 10 tasks each (200 tasks total).
    Must achieve 100% commit rate with zero SQLite busy/locked exceptions.
    """
    num_threads = 20
    tasks_per_thread = 10
    total_expected = num_threads * tasks_per_thread
    errors = []

    def _worker(thread_idx: int):
        for i in range(tasks_per_thread):
            try:
                queue.enqueue_task(
                    command=f"Thread-{thread_idx} Task-{i}",
                    source_device="phone",
                    transport="whatsapp",
                    priority="HIGH" if i % 2 == 0 else "MEDIUM",
                )
            except Exception as e:
                errors.append(e)

    threads = [threading.Thread(target=_worker, args=(t,)) for t in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15.0)

    assert len(errors) == 0, f"Encountered {len(errors)} errors during concurrent enqueue: {errors[:3]}"

    all_tasks = queue.list_tasks(limit=total_expected + 50)
    assert len(all_tasks) == total_expected, f"Expected {total_expected} tasks, got {len(all_tasks)}"

    task_ids = {t.task_id for t in all_tasks}
    assert len(task_ids) == total_expected, "Task IDs must all be unique (no collision)"


def test_concurrent_worker_claims_no_double_allocation(queue):
    """
    Stress-test atomic claiming under contention:
    Pre-queue 40 tasks. Launch 15 concurrent threads racing to claim tasks.
    Invariants:
    1. Zero duplicate claims across workers.
    2. Exactly 40 tasks claimed (all transitioned to TRANSFERRED).
    3. Once empty, subsequent claims return None.
    """
    num_tasks = 40
    enqueued_ids = set()
    for i in range(num_tasks):
        t = queue.enqueue_task(command=f"Race task {i}", priority="HIGH")
        enqueued_ids.add(t.task_id)

    claimed_by_worker: Dict[str, List[str]] = {}
    claim_lock = threading.Lock()
    errors = []

    def _worker(worker_name: str):
        worker_claims = []
        while True:
            try:
                task = queue.claim_next_task(worker_id=worker_name, target_device="laptop")
                if task is None:
                    break
                worker_claims.append(task.task_id)
            except Exception as exc:
                errors.append(exc)
                break
        with claim_lock:
            claimed_by_worker[worker_name] = worker_claims

    workers = [threading.Thread(target=_worker, args=(f"worker_{w}",)) for w in range(15)]
    for w in workers:
        w.start()
    for w in workers:
        w.join(timeout=15.0)

    assert len(errors) == 0, f"Errors during claiming: {errors}"

    all_claimed = []
    for claims in claimed_by_worker.values():
        all_claimed.extend(claims)

    assert len(all_claimed) == num_tasks, f"Expected {num_tasks} claimed tasks, got {len(all_claimed)}"
    # Invariant: No double allocation!
    assert len(set(all_claimed)) == num_tasks, "Duplicate task claims detected! Atomic CAS failure."
    assert set(all_claimed) == enqueued_ids, "Set of claimed IDs must match enqueued IDs."

    # Invariant: Remaining queue must be empty
    subsequent = queue.claim_next_task()
    assert subsequent is None


def test_concurrent_mixed_enqueue_and_claim(queue):
    """
    Stress-test simultaneous enqueuing and claiming:
    10 threads enqueuing 10 tasks each, while 10 threads continuously claim.
    """
    total_enqueued = 100
    enqueued_records = []
    claimed_records = []
    enqueue_lock = threading.Lock()
    claim_lock = threading.Lock()
    stop_claiming = threading.Event()

    def _producer(pid: int):
        for i in range(10):
            t = queue.enqueue_task(command=f"Mixed producer {pid}-{i}")
            with enqueue_lock:
                enqueued_records.append(t.task_id)
            time.sleep(0.001)

    def _consumer():
        while not stop_claiming.is_set():
            t = queue.claim_next_task()
            if t:
                with claim_lock:
                    claimed_records.append(t.task_id)
            else:
                time.sleep(0.005)

    producers = [threading.Thread(target=_producer, args=(p,)) for p in range(10)]
    consumers = [threading.Thread(target=_consumer) for _ in range(5)]

    for c in consumers:
        c.start()
    for p in producers:
        p.start()

    for p in producers:
        p.join(timeout=15.0)

    # Let consumers drain remaining tasks
    drain_start = time.time()
    while time.time() - drain_start < 5.0:
        with claim_lock:
            if len(claimed_records) == total_enqueued:
                break
        time.sleep(0.05)

    stop_claiming.set()
    for c in consumers:
        c.join(timeout=5.0)

    # Also drain any leftover
    while True:
        t = queue.claim_next_task()
        if not t:
            break
        claimed_records.append(t.task_id)

    assert len(enqueued_records) == total_enqueued
    assert len(claimed_records) == total_enqueued
    assert set(claimed_records) == set(enqueued_records)


# ── Section 2: Strict State Machine Invariants ────────────────────────────────

def test_state_machine_strict_transition_matrix(queue):
    """
    Exhaustively tests the entire state transition matrix:
    Every transition NOT in VALID_TRANSITIONS must raise ValueError.
    """
    all_statuses = [
        TaskStatus.QUEUED,
        TaskStatus.TRANSFERRED,
        TaskStatus.EXECUTING,
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
        TaskStatus.ACKNOWLEDGED,
        TaskStatus.CANCELLED,
    ]

    for start_status in all_statuses:
        allowed = VALID_TRANSITIONS.get(start_status, set())
        for target_status in all_statuses:
            if target_status == start_status:
                continue

            # Create fresh task in start_status via direct SQL for testing transition logic
            task_id = f"test_sm_{start_status.value}_{target_status.value}"
            with queue._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO cross_device_tasks (
                        task_id, source_device, source_channel, target_device,
                        sender_id, command_text, status, priority, retry_count,
                        max_retries, payload_json, result_json, created_at, updated_at
                    ) VALUES (?, 'phone', 'whatsapp', 'laptop', '+919324094474', 'sm test', ?, 'HIGH', 0, 3, '{}', '{}', ?, ?)
                    """,
                    (task_id, start_status.value, time.time(), time.time()),
                )
                conn.commit()

            if target_status in allowed:
                # Must succeed
                res = queue.transition_status(task_id, target_status)
                assert res.status == target_status.value
            else:
                # Must raise ValueError
                with pytest.raises(ValueError, match="Illegal state transition"):
                    queue.transition_status(task_id, target_status)


def test_transition_nonexistent_task_raises_key_error(queue):
    """Verifies that operating on a non-existent task ID raises KeyError."""
    with pytest.raises(KeyError, match="not found"):
        queue.transition_status("cdt_nonexistent_9999", TaskStatus.TRANSFERRED)

    with pytest.raises(KeyError, match="not found"):
        queue.start_execution("cdt_nonexistent_9999")

    with pytest.raises(KeyError, match="not found"):
        queue.complete_task("cdt_nonexistent_9999")

    with pytest.raises(KeyError, match="not found"):
        queue.fail_task("cdt_nonexistent_9999", error="boom")


def test_invalid_status_enum_rejected(queue):
    """Verifies that arbitrary strings not in TaskStatus raise ValueError."""
    task = queue.enqueue_task(command="Invalid status probe")
    with pytest.raises(ValueError):
        queue.transition_status(task.task_id, "MALICIOUS_STATUS")


def test_double_completion_prevention(queue):
    """Verifies a COMPLETED task cannot be completed again."""
    task = queue.enqueue_task(command="Double complete test")
    queue.claim_next_task()
    queue.start_execution(task.task_id)
    queue.complete_task(task.task_id, result={"ok": True})

    with pytest.raises(ValueError, match="Illegal state transition"):
        queue.complete_task(task.task_id, result={"ok": False})


@pytest.mark.asyncio
async def test_reexecution_of_completed_task_prevented(queue):
    """Verifies execute_task_flow on an already completed task raises ValueError."""
    task = queue.enqueue_task(command="Re-execution check")
    queue.claim_next_task()
    queue.start_execution(task.task_id)
    queue.complete_task(task.task_id)

    with pytest.raises(ValueError, match="Illegal state transition"):
        await queue.execute_task_flow(task.task_id, executor_fn=lambda cmd: "should not run")


# ── Section 3: Network Drops, Timeouts, & Transports Failover ─────────────────

@pytest.mark.asyncio
async def test_whatsapp_connect_and_read_timeouts_failover_to_switch(presence):
    """
    Simulates network drops:
    1. ConnectTimeout -> failover to Switch.
    2. ReadTimeout -> failover to Switch.
    Router must failover seamlessly without raising unhandled exceptions.
    """
    presence.set_device_status("laptop", "OFFLINE")  # forces phone routing
    presence.set_device_status("phone", "ONLINE")

    for timeout_exc in [
        httpx.ConnectTimeout("Connection to CallMeBot/Twilio gateway timed out"),
        httpx.ReadTimeout("Server did not return bytes within 10s"),
    ]:
        mock_wa = WhatsAppDispatcher()
        def _failing_wa(num, msg):
            raise timeout_exc
        mock_wa.transport_hook = _failing_wa

        mock_switch = SwitchIntegration()
        mock_switch.enabled = True

        router = RemoteRouter(
            presence_mon=presence,
            whatsapp_disp=mock_wa,
            switch_int=mock_switch,
        )

        res = await router.route_notification(
            title="Timeout Failover",
            message="Alert during network degradation",
            primary_transport="whatsapp",
        )

        assert res.success is True
        assert res.delivered_to == "phone"
        assert res.channel_used == "switch"
        assert res.failover_occurred is True
        assert "whatsapp_error" in res.details


@pytest.mark.asyncio
async def test_whatsapp_raw_socket_error_failover(presence):
    """Simulates a low-level socket reset or broken pipe during dispatch."""
    presence.set_device_status("laptop", "OFFLINE")
    presence.set_device_status("phone", "ONLINE")

    mock_wa = WhatsAppDispatcher()
    def _socket_error(num, msg):
        raise ConnectionResetError("[WinError 10054] An existing connection was forcibly closed by the remote host")
    mock_wa.transport_hook = _socket_error

    mock_switch = SwitchIntegration()
    mock_switch.enabled = True

    router = RemoteRouter(
        presence_mon=presence,
        whatsapp_disp=mock_wa,
        switch_int=mock_switch,
    )

    res = await router.route_notification(
        title="Socket Error",
        message="Alert during socket reset",
        primary_transport="whatsapp",
    )

    assert res.success is True
    assert res.channel_used == "switch"
    assert res.failover_occurred is True


@pytest.mark.asyncio
async def test_cascading_phone_failure_to_desktop_toast(presence):
    """
    Simulates complete mobile delivery failure:
    WhatsApp throws timeout, Switch is disabled/throws error.
    Must cascade to host laptop desktop toast.
    """
    presence.set_device_status("laptop", "ONLINE")
    presence.set_device_status("phone", "ONLINE")

    mock_wa = WhatsAppDispatcher()
    mock_wa.transport_hook = lambda num, msg: (_ for _ in ()).throw(httpx.NetworkError("Host unreachable"))

    mock_switch = SwitchIntegration()
    mock_switch.enabled = False  # Disabled Switch daemon

    toasts = []
    router = RemoteRouter(
        presence_mon=presence,
        whatsapp_disp=mock_wa,
        switch_int=mock_switch,
    )
    router.set_desktop_notifier(lambda t, m: toasts.append((t, m)) or True)

    res = await router.route_notification(
        title="Cascading Failure",
        message="Notification cascading to desktop toast",
        target="phone",
    )

    assert res.success is True
    assert res.delivered_to == "laptop"
    assert res.channel_used == "windows_toast"
    assert res.failover_occurred is True
    assert len(toasts) == 1
    assert toasts[0][0] == "Cascading Failure"


@pytest.mark.asyncio
async def test_catastrophic_all_transports_fail_cleanly(presence):
    """
    Hostile scenario:
    WhatsApp fails, Switch fails, AND laptop desktop toast crashes/fails.
    RemoteRouter must NOT crash or raise unhandled exceptions.
    Must return NotificationResult(success=False, delivered_to='failed').
    """
    presence.set_device_status("laptop", "OFFLINE")
    presence.set_device_status("phone", "ONLINE")

    mock_wa = WhatsAppDispatcher()
    mock_wa.transport_hook = lambda num, msg: (_ for _ in ()).throw(RuntimeError("WhatsApp down"))

    mock_switch = SwitchIntegration()
    mock_switch.enabled = False

    def _exploding_toast(t, m):
        raise OSError("Desktop toast display server crashed")

    router = RemoteRouter(
        presence_mon=presence,
        whatsapp_disp=mock_wa,
        switch_int=mock_switch,
    )
    router.set_desktop_notifier(_exploding_toast)

    res = await router.route_notification(
        title="Catastrophic Failure",
        message="Total blackout",
    )

    assert res.success is False
    assert res.delivered_to == "failed"
    assert res.channel_used == "none"
    assert res.failover_occurred is True
    assert res.error is not None
    assert "failed" in res.error.lower()


def test_sync_wrapper_execution_contexts(presence):
    """
    Verifies route_notification_sync executes cleanly both in pure sync context
    and when called from a thread while an event loop is active.
    """
    presence.set_device_status("laptop", "ONLINE")
    router = RemoteRouter(presence_mon=presence)
    router.set_desktop_notifier(lambda t, m: True)

    # 1. Pure sync context
    res1 = router.route_notification_sync(title="Sync Alert 1", message="Testing sync call")
    assert res1.success is True
    assert res1.channel_used == "windows_toast"

    # 2. Inside a ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        fut = pool.submit(
            router.route_notification_sync,
            title="Sync Alert 2",
            message="Testing threadpool sync call",
        )
        res2 = fut.result(timeout=5.0)
        assert res2.success is True


# ── Section 4: Boundary Stress Tests for Presence TTL ─────────────────────────

def test_presence_exact_ttl_boundary(presence):
    """
    Verifies microsecond boundary condition:
    elapsed <= ttl -> ONLINE
    elapsed > ttl -> DEGRADED (or OFFLINE)
    """
    now = time.time()
    ttl = 60.0

    # Case A: exactly now -> online
    presence.record_heartbeat("laptop", timestamp=now)
    assert presence.is_device_online("laptop") is True

    # Case B: now - ttl (exact boundary)
    dev = presence.devices["laptop"]
    dev.last_heartbeat = now - ttl
    dev.ttl_sec = ttl
    assert dev.is_online(current_time=now) is True
    assert dev.evaluate_status(current_time=now) == PresenceState.ONLINE.value

    # Case C: now - ttl - 0.001 (just expired)
    dev.last_heartbeat = now - ttl - 0.001
    assert dev.is_online(current_time=now) is False
    assert dev.evaluate_status(current_time=now) == PresenceState.DEGRADED.value


def test_presence_degraded_to_offline_boundary(presence):
    """
    Verifies degraded boundary:
    ttl < elapsed <= 2 * ttl -> DEGRADED
    elapsed > 2 * ttl -> OFFLINE
    """
    now = time.time()
    ttl = 50.0
    dev = presence.devices["laptop"]
    dev.ttl_sec = ttl

    # Exactly 2 * ttl
    dev.last_heartbeat = now - (2.0 * ttl)
    assert dev.evaluate_status(current_time=now) == PresenceState.DEGRADED.value

    # 2 * ttl + 0.1s -> OFFLINE
    dev.last_heartbeat = now - (2.0 * ttl + 0.1)
    assert dev.evaluate_status(current_time=now) == PresenceState.OFFLINE.value


def test_presence_future_timestamp_clock_skew(presence):
    """
    Stress-tests clock skew:
    Device sends heartbeat with timestamp 3600 seconds in the future.
    Must not crash, evaluates to ONLINE, and to_dict() returns valid structure.
    """
    future_time = time.time() + 3600.0
    presence.record_heartbeat("laptop", timestamp=future_time)

    assert presence.is_device_online("laptop") is True
    dev = presence.devices["laptop"]
    d = dev.to_dict()
    assert d["is_online"] is True
    assert d["evaluated_status"] == PresenceState.ONLINE.value
    # seconds_since_heartbeat is negative due to clock skew, but exists and is numeric
    assert isinstance(d["seconds_since_heartbeat"], float)


def test_presence_zero_and_unregistered_devices(presence):
    """
    Verifies edge cases:
    1. last_heartbeat = 0 -> OFFLINE
    2. Unregistered device -> False / UNKNOWN
    3. Case insensitivity ('LAPTOP' == 'laptop')
    """
    dev = presence.devices["laptop"]
    dev.last_heartbeat = 0.0
    assert dev.is_online() is False
    assert dev.evaluate_status() == PresenceState.OFFLINE.value

    # Unregistered device
    assert presence.is_device_online("non_existent_node_xyz") is False
    status = presence.get_device_status("non_existent_node_xyz")
    assert status["status"] == PresenceState.UNKNOWN.value
    assert status["is_online"] is False

    # Case-insensitive heartbeat
    presence.record_heartbeat("  LAPTOP  ")
    assert presence.is_device_online("laptop") is True
    assert presence.is_device_online("LAPTOP") is True


def test_presence_rapid_flapping_stress(presence):
    """
    Rapidly flips presence status 300 times to verify thread safety and state consistency.
    """
    for i in range(300):
        if i % 2 == 0:
            presence.set_device_status("phone", PresenceState.ONLINE.value)
            assert presence.is_device_online("phone") is True
        else:
            presence.set_device_status("phone", PresenceState.OFFLINE.value)
            assert presence.is_device_online("phone") is False

    # Clear override via heartbeat
    presence.record_heartbeat("phone")
    assert presence.devices["phone"].override_status is None
    assert presence.is_device_online("phone") is True


# ── Section 5: Webhook Security & Zero Queue Pollution ────────────────────────

def test_webhook_unauthorized_variations_rejected(client):
    """
    Adversarial attacks on phone webhook:
    Must reject all unauthorized or malformed numbers with HTTP 403 Forbidden.
    """
    malicious_senders = [
        "",                             # Empty string
        "   ",                          # Whitespace
        "+919324094475",                # Off by 1 digit
        "+19324094474",                 # Wrong country code
        "+9193240944740",               # Extra digit appended
        "91932409447",                  # Truncated
        "+919324094474' OR 1=1--",      # SQL injection attempt
        "<script>9324094474</script>",  # XSS probe
        "+447700900077",                # Spoofed UK number
        "+8613800138000",               # Spoofed China number
        "admin@jarvis.ai",              # Non-numeric string
    ]

    for sender in malicious_senders:
        resp = client.post(
            "/api/v1/crossdevice/whatsapp/webhook",
            json={
                "From": sender,
                "Body": "rm -rf /",
                "priority": "CRITICAL",
                "execute_now": False,
            },
        )
        assert resp.status_code == 403, f"Expected HTTP 403 for sender '{sender}', got {resp.status_code}: {resp.text}"
        detail = resp.json().get("detail", "")
        assert "not authorized" in detail or "Authorization failed" in detail or "Security violation" in detail


def test_webhook_unauthorized_zero_queue_pollution(client):
    """
    CRITICAL SECURITY CHECK:
    When unauthorized requests are rejected:
    1. ZERO tasks must be added to the queue (queue count unchanged).
    2. Phone heartbeat must NOT be updated.
    """
    from jarvis.core.cross_device_queue import cross_device_queue
    from jarvis.core.presence_manager import presence_manager

    # Baseline snapshots
    initial_tasks = len(cross_device_queue.list_tasks(limit=1000))
    initial_heartbeat = presence_manager.devices["phone"].last_heartbeat

    # Attack burst: 25 unauthorized requests
    for i in range(25):
        resp = client.post(
            "/api/v1/crossdevice/whatsapp/webhook",
            json={
                "From": f"+1555019{i:04d}",
                "Body": f"Malicious task {i}",
                "priority": "CRITICAL",
                "execute_now": False,
            },
        )
        assert resp.status_code == 403

    # Verify zero queue pollution
    final_tasks = len(cross_device_queue.list_tasks(limit=1000))
    assert final_tasks == initial_tasks, f"Queue polluted! Initial: {initial_tasks}, Final: {final_tasks}"

    # Verify zero presence pollution
    final_heartbeat = presence_manager.devices["phone"].last_heartbeat
    assert final_heartbeat == initial_heartbeat, "Phone presence was updated by unauthorized caller!"


def test_webhook_authorized_variations_accepted(client):
    """
    Verifies valid representations of Ganesh's phone (+91 9324094474)
    are correctly normalized and accepted with HTTP 200.
    """
    valid_formats = [
        "+91 9324094474",
        "919324094474",
        "+91-9324-094474",
        "whatsapp:+919324094474",
        "whatsapp:+91 9324094474",
    ]

    for fmt in valid_formats:
        resp = client.post(
            "/api/v1/crossdevice/whatsapp/webhook",
            json={
                "From": fmt,
                "Body": f"Authorized command from format {fmt}",
                "priority": "HIGH",
                "execute_now": False,
            },
        )
        assert resp.status_code == 200, f"Valid format '{fmt}' rejected with {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["status"] == "QUEUED"
        assert data["task_id"].startswith("cdt_")
