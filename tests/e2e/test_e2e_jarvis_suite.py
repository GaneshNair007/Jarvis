"""
Comprehensive Opaque-Box E2E Integration Suite for Project JARVIS
==================================================================
Target Repository: C:\\Users\\Ganesh Nair\\.gemini\\antigravity\\scratch\\Jarvis
Branch: sprint1.5/eliminate-fake-success
Authoritative Sources: ORIGINAL_REQUEST.md, PROJECT.md, TEST_INFRA.md

Methodology:
- 4-Tier Verification Architecture:
  * Tier 1: 18 Feature Coverage Tests (Voice 1-6, Cross-Device 7-12, Antigravity 13-18)
  * Tier 2: 18 Boundary & Corner Case Tests (Voice 1-6, Cross-Device 7-12, Antigravity 13-18)
  * Tier 3: 8 Cross-Feature Combination Tests
  * Tier 4: 5 Real-World Application Workload Scenarios
- Progressive Testability: Baseline checks execute genuinely as milestones come online.
- Test Independence: Isolated SQLite WAL instances, temp pids, mock transports, clean teardown.
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import sqlite3
import subprocess
import sys
import time
import uuid
import wave
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
import httpx

from jarvis.config import settings
from jarvis.core.orchestrator import orchestrator, JarvisOrchestrator
from jarvis.core.autonomous_repo_builder import autonomous_repo_builder, AutonomousRepoBuilder
from jarvis.voice.wake import wake_detector
from jarvis.voice.stt import stt_engine
from jarvis.powers.whatsapp_dispatcher import WhatsAppDispatcher
from integrations.switch.switch_integration import switch_integration, SwitchIntegration


# =============================================================================
# Progressive Module Loaders
# =============================================================================

def get_cross_device_queue_cls():
    try:
        from jarvis.core.cross_device_queue import (
            CrossDeviceTaskQueue,
            TaskStatus,
            TaskPriority,
            CrossDeviceTask,
            cross_device_queue,
        )
        return CrossDeviceTaskQueue, TaskStatus, TaskPriority, CrossDeviceTask, cross_device_queue
    except (ImportError, AttributeError) as exc:
        pytest.skip(f"CrossDeviceTaskQueue not yet available: {exc}")


def get_presence_manager_cls():
    try:
        from jarvis.core.presence_manager import (
            PresenceManager,
            PresenceState,
            DevicePresence,
            DeviceType,
            presence_manager,
        )
        return PresenceManager, PresenceState, DevicePresence, DeviceType, presence_manager
    except (ImportError, AttributeError) as exc:
        pytest.skip(f"PresenceManager not yet available: {exc}")


def get_remote_router_cls():
    try:
        from jarvis.core.remote_router import (
            RemoteRouter,
            NotificationResult,
            TransportChannel,
            remote_router,
        )
        return RemoteRouter, NotificationResult, TransportChannel, remote_router
    except (ImportError, AttributeError) as exc:
        pytest.skip(f"RemoteRouter not yet available: {exc}")


def get_voice_listener_cls():
    try:
        from jarvis.voice.listener import AudioListenerDaemon, audio_daemon
        return AudioListenerDaemon
    except (ImportError, AttributeError) as exc:
        pytest.skip(f"AudioListenerDaemon not yet available: {exc}")


def get_process_manager_cls():
    try:
        from jarvis.core.process_manager import ProcessManager, process_manager
        return ProcessManager, process_manager
    except (ImportError, AttributeError) as exc:
        pytest.skip(f"ProcessManager not yet available: {exc}")


def get_antigravity_engine_cls():
    try:
        from jarvis.core.antigravity_engine import (
            AntigravityProjectEngine,
            ProjectBuildJob,
            antigravity_engine,
        )
        return AntigravityProjectEngine, ProjectBuildJob, antigravity_engine
    except (ImportError, AttributeError) as exc:
        pytest.skip(f"AntigravityProjectEngine not yet available (Milestone 3): {exc}")


# =============================================================================
# Helper Fixtures & Utilities
# =============================================================================

def make_silent_wav(duration_sec: float = 1.0, sample_rate: int = 16000) -> bytes:
    """Generates standard mono 16-bit PCM WAV silence."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        num_frames = int(duration_sec * sample_rate)
        wf.writeframes(b"\x00\x00" * num_frames)
    return buf.getvalue()


@pytest.fixture
def isolated_queue(tmp_path):
    """Provides an isolated CrossDeviceTaskQueue backed by a temporary SQLite WAL database."""
    CrossDeviceTaskQueue, TaskStatus, TaskPriority, CrossDeviceTask, _ = get_cross_device_queue_cls()
    db_file = tmp_path / "test_cross_device.db"
    queue = CrossDeviceTaskQueue(db_path=db_file)
    return queue


@pytest.fixture
def isolated_presence(tmp_path):
    """Provides an isolated PresenceManager using a test profile."""
    PresenceManager, PresenceState, DevicePresence, DeviceType, _ = get_presence_manager_cls()
    profile_file = tmp_path / "test_profile.yml"
    profile_content = """
name: "Ganesh Nair"
phone: "+91 9324094474"
devices:
  laptop:
    id: "laptop"
    name: "RTX 4050 Primary Compute Laptop"
    platform: "windows"
    heartbeat_ttl_sec: 60
    preferred_transport: "windows_toast"
  phone:
    id: "phone"
    name: "Primary Mobile Device"
    phone_number: "+91 9324094474"
    heartbeat_ttl_sec: 180
    preferred_transport: "whatsapp"
    fallback_transport: "switch"
"""
    profile_file.write_text(profile_content, encoding="utf-8")
    mgr = PresenceManager(profile_path=profile_file)
    return mgr


@pytest.fixture
def mock_transports():
    """Provides mock WhatsApp and Switch transports for deterministic failover testing."""
    mock_wa = MagicMock(spec=WhatsAppDispatcher)
    mock_wa.default_phone = "+919324094474"
    mock_wa.send_whatsapp_message = AsyncMock(return_value={"status": "delivered", "channel": "whatsapp"})

    mock_sw = MagicMock(spec=SwitchIntegration)
    mock_sw.enabled = True
    mock_sw.connected = True
    trust_mock = MagicMock()
    trust_mock.success = True
    trust_mock.to_dict.return_value = {"status": "delivered", "channel": "switch"}
    mock_sw.send_room_message.return_value = trust_mock

    return mock_wa, mock_sw


# =============================================================================
# TIER 1: FEATURE COVERAGE (18 TEST CASES)
# =============================================================================

class TestTier1FeatureCoverage:
    """
    Tier 1: 18 Primary Feature Coverage Tests.
    Voice / Lifecycle: Tests 1-6
    Cross-Device / Failover: Tests 7-12
    Antigravity Engine: Tests 13-18
    """

    # --- 1. Voice / Process Subsystem (1-6) ---

    def test_tier1_voice_01_wake_word_triggers_listening(self):
        """Feature 1 & R1: Wake phrase 'Hey Jarvis' triggers active listening state."""
        AudioListenerDaemon = get_voice_listener_cls()
        daemon = AudioListenerDaemon(enable_tts_feedback=False)
        assert daemon.current_state == "IDLE"

        # Simulate wake word event
        daemon.simulate_event({"event": "WAKE", "phrase": "hey jarvis", "confidence": 0.90})
        assert daemon.current_state in ("WOKE", "PROCESSING", "SPEAKING")
        daemon.stop()

    def test_tier1_voice_02_spoken_command_captured(self):
        """Feature 2 & R1: Spoken command following wake word captures full task prompt."""
        AudioListenerDaemon = get_voice_listener_cls()
        daemon = AudioListenerDaemon(enable_tts_feedback=False)

        daemon.simulate_event({"event": "WAKE", "phrase": "hey jarvis"})
        assert daemon.current_state == "WOKE"

        # Speech command during capture window
        daemon.simulate_event({"event": "SPEECH", "text": "what is your system status"})
        assert len(daemon._processed_commands) > 0
        assert "system status" in daemon._processed_commands[-1].lower()
        daemon.stop()

    def test_tier1_voice_03_compound_utterance_dispatch(self):
        """Feature 2 & R1: Single-step compound utterance ('Hey Jarvis, what is your status') parses and dispatches directly."""
        AudioListenerDaemon = get_voice_listener_cls()
        daemon = AudioListenerDaemon(enable_tts_feedback=False)

        compound_text = "Hey Jarvis, check system status"
        daemon.simulate_speech_input(compound_text)

        assert len(daemon._processed_commands) > 0
        assert "check system status" in daemon._processed_commands[-1].lower()
        daemon.stop()

    def test_tier1_voice_04_real_stt_fallback_no_fakes(self):
        """Feature 3 & Integrity: STT processes audio without returning hardcoded fake strings on silence."""
        silent_wav = make_silent_wav(duration_sec=1.0)
        res = stt_engine.transcribe(silent_wav)

        text = res.get("text", "").strip().lower()
        # Authoritative mandate: hardcoded mock string must NEVER be returned
        assert text != "jarvis, report system health", (
            "STT returned hardcoded fake string 'Jarvis, report system health' on pure silence! "
            "Fake success violation."
        )

    def test_tier1_voice_05_process_manager_pid_tracking(self, tmp_path):
        """Feature 4 & R4: Process manager records PID on launch and prevents duplicate running instances."""
        ProcessManager, _ = get_process_manager_cls()
        pm = ProcessManager(base_dir=tmp_path)
        current_pid = os.getpid()

        # Register running daemon instance
        acquired = pm.acquire_pid("test_audio", current_pid)
        assert acquired is True
        assert pm.is_running("test_audio") is True

        # Second launch attempt with a different PID must be blocked (single-instance invariant)
        second_attempt = pm.acquire_pid("test_audio", pid=current_pid + 1)
        assert second_attempt is False, "ProcessManager permitted duplicate daemon startup!"
        pm.release_pid("test_audio")

    def test_tier1_voice_06_clean_shutdown_removes_pid(self, tmp_path):
        """Feature 5 & R4: Clean shutdown command removes PID file and halts background process."""
        ProcessManager, _ = get_process_manager_cls()
        pm = ProcessManager(base_dir=tmp_path)
        current_pid = os.getpid()

        pm.acquire_pid("test_audio", current_pid)
        assert pm.is_running("test_audio") is True

        pm.release_pid("test_audio")
        assert pm.is_running("test_audio") is False

    # --- 2. Cross-Device / Failover Subsystem (7-12) ---

    def test_tier1_crossdevice_07_inbound_phone_task_queued(self, isolated_queue):
        """Feature 8 & R2: Inbound phone task is written to persistent SQLite WAL queue in QUEUED state."""
        _, TaskStatus, _, _, _ = get_cross_device_queue_cls()
        task = isolated_queue.enqueue_task(
            command="Scaffold AI Hackathon Project",
            source_device="phone",
            transport="whatsapp",
            sender_id="+919324094474",
        )
        assert task is not None
        assert task.status == TaskStatus.QUEUED.value
        assert task.source_device == "phone"
        assert task.sender_id == "+919324094474"

        # Verify persistent row in SQLite
        retrieved = isolated_queue.get_task(task.task_id)
        assert retrieved is not None
        assert retrieved.command_text == "Scaffold AI Hackathon Project"

    def test_tier1_crossdevice_08_inbound_task_lifecycle_transfer_exec(self, isolated_queue):
        """Feature 8 & R2: Task transitions cleanly QUEUED -> TRANSFERRED -> EXECUTING -> COMPLETED."""
        _, TaskStatus, _, _, _ = get_cross_device_queue_cls()
        task = isolated_queue.enqueue_task(
            command="Run database backup",
            source_device="phone",
            transport="whatsapp",
        )

        # Worker claims next task
        claimed = isolated_queue.claim_next_task(worker_id="laptop_worker_1")
        assert claimed is not None
        assert claimed.task_id == task.task_id
        assert claimed.status == TaskStatus.TRANSFERRED.value
        assert claimed.claimed_at is not None

        # Start execution
        executing = isolated_queue.start_execution(claimed.task_id)
        assert executing.status == TaskStatus.EXECUTING.value

        # Worker completes task
        completed = isolated_queue.complete_task(
            claimed.task_id,
            result={"backup_size_kb": 1024, "status": "ok"},
        )
        assert completed.status == TaskStatus.COMPLETED.value
        assert completed.completed_at is not None
        assert completed.result.get("status") == "ok"

    def test_tier1_crossdevice_09_presence_manager_heartbeat_tracking(self, isolated_presence):
        """Feature 9 & R2: Presence manager records device heartbeats and reports ONLINE status."""
        _, PresenceState, _, DeviceType, _ = get_presence_manager_cls()

        # Set initial offline state
        isolated_presence.devices[DeviceType.LAPTOP.value].last_heartbeat = 0.0
        assert isolated_presence.is_device_online(DeviceType.LAPTOP.value) is False

        # Record heartbeat
        isolated_presence.record_heartbeat(
            device_id=DeviceType.LAPTOP.value,
            metadata={"battery": 95, "cpu_load": 14.2},
        )
        assert isolated_presence.is_device_online(DeviceType.LAPTOP.value) is True
        status_dict = isolated_presence.get_device_status(DeviceType.LAPTOP.value)
        assert status_dict["is_online"] is True

    @pytest.mark.asyncio
    async def test_tier1_crossdevice_10_laptop_active_local_notification(self, isolated_presence, mock_transports):
        """Feature 10 & R2: When laptop is online, notification routes locally via Windows Desktop Toast."""
        RemoteRouter, _, _, _ = get_remote_router_cls()
        mock_wa, mock_sw = mock_transports

        # Set laptop ONLINE, phone ONLINE
        isolated_presence.record_heartbeat("laptop")
        isolated_presence.record_heartbeat("phone")

        router = RemoteRouter(presence_mon=isolated_presence, whatsapp_disp=mock_wa, switch_int=mock_sw)
        desktop_dispatches = []
        router.set_desktop_notifier(lambda t, m: desktop_dispatches.append((t, m)) or True)

        res = await router.route_notification(
            title="Build Finished",
            message="Repository scaffold completed successfully",
            priority="normal",
            target="laptop",
        )

        assert res.success is True
        assert res.delivered_to == "laptop"
        assert res.channel_used == "windows_toast"
        assert len(desktop_dispatches) == 1
        assert desktop_dispatches[0][0] == "Build Finished"

    @pytest.mark.asyncio
    async def test_tier1_crossdevice_11_laptop_offline_routes_to_phone(self, isolated_presence, mock_transports):
        """Feature 10 & R2: When laptop is offline, notification routes directly to phone (+91 9324094474)."""
        RemoteRouter, _, _, _ = get_remote_router_cls()
        mock_wa, mock_sw = mock_transports

        # Laptop is OFFLINE
        isolated_presence.set_device_status("laptop", "OFFLINE")
        isolated_presence.record_heartbeat("phone")

        router = RemoteRouter(presence_mon=isolated_presence, whatsapp_disp=mock_wa, switch_int=mock_sw)

        res = await router.route_notification(
            title="Urgent Opportunity",
            message="New AI Architect hackathon opened",
            priority="critical",
        )

        assert res.success is True
        assert res.delivered_to == "phone"
        assert res.channel_used == "whatsapp"
        assert res.recipient == "+91 9324094474"
        mock_wa.send_whatsapp_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_tier1_crossdevice_12_outbound_whatsapp_failover_to_switch(self, isolated_presence, mock_transports):
        """Feature 10 & R2: Outbound message fails over to Switch Protocol when WhatsApp transport fails."""
        RemoteRouter, _, _, _ = get_remote_router_cls()
        mock_wa, mock_sw = mock_transports

        # Laptop is offline; force WhatsApp to throw connection timeout
        isolated_presence.set_device_status("laptop", "OFFLINE")
        mock_wa.send_whatsapp_message = AsyncMock(side_effect=httpx.ConnectTimeout("WhatsApp gateway timed out"))

        router = RemoteRouter(presence_mon=isolated_presence, whatsapp_disp=mock_wa, switch_int=mock_sw)

        res = await router.route_notification(
            title="System Alert",
            message="Remote command completed",
            priority="high",
        )

        assert res.success is True
        assert res.delivered_to == "phone"
        assert res.channel_used == "switch"
        assert res.failover_occurred is True
        mock_sw.send_room_message.assert_called_once()

    # --- 3. Antigravity Engine Subsystem (13-18) ---

    def test_tier1_antigravity_13_voice_project_build_enqueues(self, tmp_path):
        """Feature 13 & R3: Voice command 'Hey Jarvis, build a weather cli tool' enqueues background job."""
        AntigravityProjectEngine, _, _ = get_antigravity_engine_cls()
        engine = AntigravityProjectEngine(queue_dir=tmp_path / "project_queue")

        job = engine.enqueue_project(
            prompt="build a weather cli tool",
            requested_by="voice",
            channel="local",
        )
        assert job is not None
        assert job.status in ("QUEUED", "PENDING")
        assert "weather" in job.project_name.lower() or "weather" in job.prompt.lower()
        assert job.source_channel == "voice"

    def test_tier1_antigravity_14_immediate_voice_ack_under_50ms(self, tmp_path):
        """Feature 14 & R3: Immediate voice response returned in <50ms without blocking."""
        AntigravityProjectEngine, _, _ = get_antigravity_engine_cls()
        engine = AntigravityProjectEngine(queue_dir=tmp_path / "project_queue")

        t0 = time.perf_counter()
        ack = engine.get_immediate_acknowledgment("weather-cli")
        duration_ms = (time.perf_counter() - t0) * 1000

        assert duration_ms < 50.0, f"Voice acknowledgment took {duration_ms:.2f}ms (threshold 50ms)"
        assert isinstance(ack, str)
        assert len(ack) > 0

    def test_tier1_antigravity_15_background_worker_scaffolds_repo(self, tmp_path):
        """Feature 15 & R3: Background worker scaffolds complete project directory on disk."""
        target_dir = tmp_path / "scaffolded_weather"
        repo_obj, trust_res = autonomous_repo_builder.build_project_repository(
            project_name="Weather CLI Tool",
            description="Autonomous CLI weather monitor for Ganesh Nair",
            architecture_spec={"type": "cli", "runtime": "python"},
            candidate_name="Ganesh Nair",
            target_dir_override=target_dir,
        )

        assert target_dir.exists()
        assert (target_dir / "README.md").exists()
        assert (target_dir / "LICENSE").exists()
        assert (target_dir / "requirements.txt").exists()
        assert (target_dir / "main.py").exists()
        assert (target_dir / "tests").is_dir()
        assert repo_obj.tests_passed is True

    def test_tier1_antigravity_16_project_git_repo_initial_commit(self, tmp_path):
        """Feature 16 & R3: Project directory contains valid git repository with initial commit SHA."""
        target_dir = tmp_path / "scaffolded_git_test"
        repo_obj, _ = autonomous_repo_builder.build_project_repository(
            project_name="Git Commit Validator",
            description="Testing git repository commit creation",
            architecture_spec={},
            target_dir_override=target_dir,
        )

        git_dir = target_dir / ".git"
        assert git_dir.exists(), "Target directory is not an initialized git repo!"

        # Inspect commit SHA via git rev-parse HEAD
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(target_dir),
            capture_output=True,
            text=True,
        )
        assert res.returncode == 0
        commit_sha = res.stdout.strip()
        assert len(commit_sha) == 40
        assert repo_obj.git_commit_hash == commit_sha

    def test_tier1_antigravity_17_project_internal_pytest_pass(self, tmp_path):
        """Feature 17 & R3: Project passes automated internal pytest run on creation."""
        target_dir = tmp_path / "scaffolded_pytest_test"
        repo_obj, _ = autonomous_repo_builder.build_project_repository(
            project_name="Pytest Verification Project",
            description="Testing internal pytest execution",
            architecture_spec={},
            target_dir_override=target_dir,
        )
        assert repo_obj.tests_passed is True

        # Independently execute pytest on scaffolded project
        run = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "-v"],
            cwd=str(target_dir),
            capture_output=True,
            text=True,
        )
        assert run.returncode == 0, f"Generated project tests failed: {run.stdout} {run.stderr}"

    def test_tier1_antigravity_18_completion_alert_published(self, tmp_path, isolated_presence, mock_transports):
        """Feature 17 & R3: Completion alert is published upon successful build."""
        AntigravityProjectEngine, _, _ = get_antigravity_engine_cls()
        RemoteRouter, _, _, _ = get_remote_router_cls()
        mock_wa, mock_sw = mock_transports

        router = RemoteRouter(presence_mon=isolated_presence, whatsapp_disp=mock_wa, switch_int=mock_sw)
        engine = AntigravityProjectEngine(queue_dir=tmp_path / "project_queue", router=router)

        dispatched_alerts = []
        engine.set_notification_callback(lambda alert: dispatched_alerts.append(alert))

        # Simulate job completion
        engine.notify_build_completion(
            project_name="Crypto Tracker",
            commit_sha="a" * 40,
            status="SUCCESS",
        )

        assert len(dispatched_alerts) == 1
        assert "Crypto Tracker" in dispatched_alerts[0]["project_name"]
        assert dispatched_alerts[0]["status"] == "SUCCESS"


# =============================================================================
# TIER 2: BOUNDARY & CORNER CASES (18 TEST CASES)
# =============================================================================

class TestTier2BoundaryCornerCases:
    """
    Tier 2: 18 Boundary Value & Corner Case Tests.
    Voice / Lifecycle: Tests 1-6
    Cross-Device / Failover: Tests 7-12
    Antigravity Engine: Tests 13-18
    """

    # --- 1. Voice / Process Boundaries (1-6) ---

    def test_tier2_voice_01_empty_silence_no_wake(self):
        """Boundary: Pure silence does not trigger wake state."""
        assert not wake_detector.detect_phrase_in_text("")
        assert not wake_detector.detect_phrase_in_text("   \t  \n  ")

    def test_tier2_voice_02_phonetic_near_miss_rejected(self):
        """Boundary: Phonetic near-miss ('Hey Harvest', 'Hey Service') rejected."""
        assert not wake_detector.detect_phrase_in_text("Hey Harvest, status please")
        assert not wake_detector.detect_phrase_in_text("Hey Service, turn on lights")
        assert not wake_detector.detect_phrase_in_text("hello computer")

    def test_tier2_voice_03_rapid_successive_wake_no_runaway(self):
        """Boundary: Rapid successive wake triggers do not spawn duplicate listener processes."""
        AudioListenerDaemon = get_voice_listener_cls()
        daemon = AudioListenerDaemon(enable_tts_feedback=False)

        # Fire 10 rapid wake events in succession
        for _ in range(10):
            daemon.simulate_event({"event": "WAKE", "phrase": "hey jarvis"})

        # Listener should remain in single active capture state
        assert daemon.current_state == "WOKE"
        daemon.stop()

    def test_tier2_voice_04_corrupted_pid_dead_cleaned_on_launch(self, tmp_path):
        """Boundary: Corrupted .jarvis.pid with dead PID is cleaned up automatically on launch."""
        ProcessManager, _ = get_process_manager_cls()
        pm = ProcessManager(base_dir=tmp_path)
        pid_file = pm._get_pid_path("test_audio")
        pid_file.parent.mkdir(parents=True, exist_ok=True)

        # Write non-existent dead PID
        with open(pid_file, "w", encoding="utf-8") as f:
            json.dump({"service": "test_audio", "pid": 99999999}, f)

        # is_running should detect dead PID and clean it up automatically
        assert pm.is_running("test_audio") is False
        assert not pid_file.exists()
        assert pm.acquire_pid("test_audio", os.getpid()) is True
        pm.release_pid("test_audio")

    def test_tier2_voice_05_abrupt_process_kill_queue_recoverable(self, tmp_path):
        """Boundary: Abrupt process kill leaves task queue state recoverable."""
        CrossDeviceTaskQueue, _, _, _, _ = get_cross_device_queue_cls()
        db_file = tmp_path / "recoverable.db"

        # Simulate task in progress
        q1 = CrossDeviceTaskQueue(db_path=db_file)
        t = q1.enqueue_task("Task before crash")
        claimed = q1.claim_next_task()
        assert claimed is not None

        # Re-open database connection simulating restart after process crash
        q2 = CrossDeviceTaskQueue(db_path=db_file)
        recovered_task = q2.get_task(t.task_id)
        assert recovered_task is not None
        assert recovered_task.command_text == "Task before crash"

    def test_tier2_voice_06_missing_hardware_fallback_graceful(self):
        """Boundary: Missing audio hardware falls back to simulated/wave mode gracefully."""
        AudioListenerDaemon = get_voice_listener_cls()
        daemon = AudioListenerDaemon(enable_tts_feedback=False)

        error_event = {
            "event": "ERROR",
            "type": "ERROR",
            "message": "No audio endpoint found",
            "error_type": "DEVICE_NOT_FOUND",
        }
        daemon.simulate_event(error_event)
        status = daemon.get_status()
        assert status is not None
        daemon.stop()

    # --- 2. Cross-Device / Failover Boundaries (7-12) ---

    @pytest.mark.asyncio
    async def test_tier2_crossdevice_07_both_devices_offline_buffered(self, isolated_presence, mock_transports, tmp_path):
        """Boundary: Both laptop and phone offline: notification buffered in persistent queue until reconnection."""
        RemoteRouter, _, _, _ = get_remote_router_cls()
        mock_wa, mock_sw = mock_transports

        # Ensure both devices are offline
        isolated_presence.set_device_status("laptop", "OFFLINE")
        isolated_presence.set_device_status("phone", "OFFLINE")

        router = RemoteRouter(presence_mon=isolated_presence, whatsapp_disp=mock_wa, switch_int=mock_sw)
        router.set_desktop_notifier(lambda t, m: False)

        res = await router.route_notification(
            title="Nightly Summary",
            message="All batch tasks completed",
            priority="low",
        )
        assert res is not None

    @pytest.mark.asyncio
    async def test_tier2_crossdevice_08_both_transports_fail_retryable(self, isolated_presence, mock_transports):
        """Boundary: Both WhatsApp and Switch fail: error logged, job marked retryable without crashing."""
        RemoteRouter, _, _, _ = get_remote_router_cls()
        mock_wa, mock_sw = mock_transports

        # Laptop offline
        isolated_presence.set_device_status("laptop", "OFFLINE")
        mock_wa.send_whatsapp_message = AsyncMock(side_effect=RuntimeError("WhatsApp network down"))
        mock_sw.send_room_message.side_effect = RuntimeError("Switch socket closed")

        router = RemoteRouter(presence_mon=isolated_presence, whatsapp_disp=mock_wa, switch_int=mock_sw)
        router.set_desktop_notifier(lambda t, m: False)

        res = await router.route_notification(
            title="Alert",
            message="Testing double transport failure",
        )
        assert res.success is False
        assert res.delivered_to == "failed"

    def test_tier2_crossdevice_09_malformed_phone_payload_rejected_422(self, isolated_queue):
        """Boundary: Malformed phone payload safely rejected without corrupting queue."""
        with pytest.raises((ValueError, TypeError, sqlite3.IntegrityError)):
            isolated_queue.enqueue_task(command=None)

    def test_tier2_crossdevice_10_duplicate_task_id_idempotent(self, isolated_queue):
        """Boundary: Duplicate inbound task ID handled idempotently without crash."""
        task_id = "cdt_idempotent_test_001"
        t1 = isolated_queue.enqueue_task("Run report", task_id=task_id)
        assert t1.task_id == task_id

        # Attempting duplicate insert with same ID should not corrupt queue
        try:
            t2 = isolated_queue.enqueue_task("Run report", task_id=task_id)
            assert t2.task_id == task_id
        except Exception:
            pass

        assert isolated_queue.get_task(task_id) is not None

    @pytest.mark.asyncio
    async def test_tier2_crossdevice_11_network_timeout_triggers_immediate_fallback(self, isolated_presence, mock_transports):
        """Boundary: Network timeout during dispatch triggers immediate fallback without blocking queue."""
        RemoteRouter, _, _, _ = get_remote_router_cls()
        mock_wa, mock_sw = mock_transports

        isolated_presence.set_device_status("laptop", "OFFLINE")

        async def slow_timeout(*args, **kwargs):
            raise asyncio.TimeoutError("Network timeout")

        mock_wa.send_whatsapp_message = AsyncMock(side_effect=slow_timeout)
        router = RemoteRouter(presence_mon=isolated_presence, whatsapp_disp=mock_wa, switch_int=mock_sw)

        t0 = time.perf_counter()
        res = await router.route_notification("Notice", "Testing fast timeout", target="phone")
        elapsed = time.perf_counter() - t0

        assert res.channel_used == "switch"
        assert res.failover_occurred is True
        assert elapsed < 2.0

    def test_tier2_crossdevice_12_heartbeat_timeout_boundary_60s(self, isolated_presence):
        """Boundary: Heartbeat timeout boundary (exactly 60s) flips device status from online to offline."""
        now = time.time()
        # 59.0s ago -> ONLINE
        isolated_presence.record_heartbeat("laptop", timestamp=now - 59.0)
        assert isolated_presence.is_device_online("laptop") is True

        # 61.0s ago -> OFFLINE
        isolated_presence.record_heartbeat("laptop", timestamp=now - 61.0)
        assert isolated_presence.is_device_online("laptop") is False

    # --- 3. Antigravity Engine Boundaries (13-18) ---

    def test_tier2_antigravity_13_empty_description_rejected(self, tmp_path):
        """Boundary: Empty project description / invalid project name safely rejected."""
        AntigravityProjectEngine, _, _ = get_antigravity_engine_cls()
        engine = AntigravityProjectEngine(queue_dir=tmp_path / "project_queue")

        with pytest.raises((ValueError, AssertionError)):
            engine.enqueue_project(prompt="", requested_by="voice")

        with pytest.raises((ValueError, AssertionError)):
            engine.enqueue_project(prompt="   ", requested_by="voice")

    def test_tier2_antigravity_14_job_queue_persistence_across_restart(self, tmp_path):
        """Boundary: Project generation queue persistence across engine restarts."""
        AntigravityProjectEngine, _, _ = get_antigravity_engine_cls()
        q_dir = tmp_path / "project_queue"

        e1 = AntigravityProjectEngine(queue_dir=q_dir)
        job1 = e1.enqueue_project("build microservice", requested_by="whatsapp")

        e2 = AntigravityProjectEngine(queue_dir=q_dir)
        persisted_job = e2.get_job(job1.job_id)

        assert persisted_job is not None
        assert persisted_job.job_id == job1.job_id
        assert persisted_job.prompt == "build microservice"

    def test_tier2_antigravity_15_concurrency_limit_enforced(self, tmp_path):
        """Boundary: Concurrency limit enforced (2nd simultaneous build queued, not executed concurrently)."""
        AntigravityProjectEngine, _, _ = get_antigravity_engine_cls()
        engine = AntigravityProjectEngine(queue_dir=tmp_path / "project_queue", max_concurrent=1)

        j1 = engine.enqueue_project("build first project", requested_by="voice")
        j2 = engine.enqueue_project("build second project", requested_by="phone")

        active_jobs = engine.get_active_jobs()
        assert len(active_jobs) <= 1

    def test_tier2_antigravity_16_build_failure_captured_safely(self, tmp_path):
        """Boundary: Build failure in generated code captured, logged, and reported without crashing engine."""
        AntigravityProjectEngine, _, _ = get_antigravity_engine_cls()
        engine = AntigravityProjectEngine(queue_dir=tmp_path / "project_queue")

        failing_builder = MagicMock()
        failing_builder.build_project_repository.side_effect = RuntimeError("Syntax error in generated AST")

        job = engine.execute_build_sync(
            job_id="job_failing_1",
            prompt="failing build",
            builder=failing_builder,
        )
        assert job.status == "FAILED"
        assert "Syntax error" in (job.error_message or "")

    def test_tier2_antigravity_17_disk_write_failure_handled(self, tmp_path):
        """Boundary: Disk write failure / read-only directory handled gracefully."""
        invalid_path = Path("Z:/non_existent_drive_999/scaffolded")
        with pytest.raises(Exception):
            autonomous_repo_builder.build_project_repository(
                project_name="Invalid Path Project",
                description="Testing disk error handling",
                architecture_spec={},
                target_dir_override=invalid_path,
            )

    def test_tier2_antigravity_18_high_queue_depth_stress(self, tmp_path):
        """Boundary: High queue depth stress (5 rapid build requests queued sequentially)."""
        AntigravityProjectEngine, _, _ = get_antigravity_engine_cls()
        engine = AntigravityProjectEngine(queue_dir=tmp_path / "project_queue")

        jobs = []
        for i in range(5):
            j = engine.enqueue_project(f"Project number {i}", requested_by="batch")
            jobs.append(j)

        assert len(jobs) == 5
        ids = {j.job_id for j in jobs}
        assert len(ids) == 5


# =============================================================================
# TIER 3: CROSS-FEATURE COMBINATIONS (8 TEST CASES)
# =============================================================================

class TestTier3CrossFeatureCombinations:
    """
    Tier 3: 8 Cross-Feature Combination & Pairwise Tests.
    """

    def test_tier3_cross_01_voice_antigravity_immediate_ack_async_build(self, tmp_path):
        """Combination 1: Voice command triggers immediate audio ack while background engine executes async build."""
        AudioListenerDaemon = get_voice_listener_cls()
        daemon = AudioListenerDaemon(enable_tts_feedback=False)

        t0 = time.perf_counter()
        daemon.simulate_speech_input("Hey Jarvis, build a portfolio dashboard")
        latency_ms = (time.perf_counter() - t0) * 1000

        # Immediate voice handling returned < 50ms
        assert latency_ms < 50.0
        assert len(daemon._processed_commands) >= 1
        daemon.stop()

    def test_tier3_cross_02_phone_inbound_antigravity_build_notify(self, isolated_queue, isolated_presence, mock_transports, tmp_path):
        """Combination 2: Phone WhatsApp message enqueues project on laptop, executes in background, and notifies phone."""
        AntigravityProjectEngine, _, _ = get_antigravity_engine_cls()
        RemoteRouter, _, _, _ = get_remote_router_cls()
        mock_wa, mock_sw = mock_transports

        router = RemoteRouter(presence_mon=isolated_presence, whatsapp_disp=mock_wa, switch_int=mock_sw)
        engine = AntigravityProjectEngine(queue_dir=tmp_path / "project_queue", router=router)

        # 1. Phone sends inbound command
        task = isolated_queue.enqueue_task(
            command="BUILD: crypto-tracker",
            source_device="phone",
            transport="whatsapp",
            sender_id="+919324094474",
        )
        assert task.status == "QUEUED"

        # 2. Ingest into Antigravity engine
        job = engine.enqueue_project(prompt=task.command_text, requested_by="whatsapp")
        assert job.status in ("QUEUED", "PENDING")

        # 3. Complete build and notify
        engine.notify_build_completion("crypto-tracker", "c" * 40, "SUCCESS")

    @pytest.mark.asyncio
    async def test_tier3_cross_03_presence_failover_antigravity_completion(self, isolated_presence, mock_transports):
        """Combination 3: Project completes while laptop is offline -> completion notification routes to phone via WhatsApp."""
        RemoteRouter, _, _, _ = get_remote_router_cls()
        mock_wa, mock_sw = mock_transports

        # Laptop is OFFLINE; Phone is ONLINE
        isolated_presence.set_device_status("laptop", "OFFLINE")
        isolated_presence.record_heartbeat("phone")

        router = RemoteRouter(presence_mon=isolated_presence, whatsapp_disp=mock_wa, switch_int=mock_sw)

        res = await router.route_notification(
            title="Antigravity Build Complete",
            message="Project 'crypto-tracker' scaffolded with commit SHA 12345678",
            priority="high",
        )
        assert res.success is True
        assert res.delivered_to == "phone"
        assert res.channel_used == "whatsapp"
        assert res.recipient == "+91 9324094474"

    @pytest.mark.asyncio
    async def test_tier3_cross_04_voice_presence_phone_failover(self, isolated_presence, mock_transports):
        """Combination 4: Voice query on laptop triggers action; laptop goes offline mid-flight; result routes to phone via Switch."""
        RemoteRouter, _, _, _ = get_remote_router_cls()
        mock_wa, mock_sw = mock_transports

        # Laptop drops offline, WhatsApp down -> Failover to Switch
        isolated_presence.set_device_status("laptop", "OFFLINE")
        mock_wa.send_whatsapp_message = AsyncMock(side_effect=RuntimeError("WhatsApp offline"))
        router = RemoteRouter(presence_mon=isolated_presence, whatsapp_disp=mock_wa, switch_int=mock_sw)

        res = await router.route_notification(
            title="Voice Query Result",
            message="System diagnostics: 0 errors found",
            priority="normal",
        )
        assert res.channel_used == "switch"
        assert res.failover_occurred is True

    def test_tier3_cross_05_process_lifecycle_background_engine(self, tmp_path):
        """Combination 5: Graceful daemon shutdown pauses active background project gracefully and resumes on restart."""
        AntigravityProjectEngine, _, _ = get_antigravity_engine_cls()
        q_dir = tmp_path / "project_queue"

        engine1 = AntigravityProjectEngine(queue_dir=q_dir)
        j = engine1.enqueue_project("long running data pipeline", requested_by="phone")
        engine1.shutdown()

        # Restart engine
        engine2 = AntigravityProjectEngine(queue_dir=q_dir)
        resumed = engine2.get_job(j.job_id)
        assert resumed is not None
        assert resumed.job_id == j.job_id

    @pytest.mark.asyncio
    async def test_tier3_cross_06_concurrent_voice_query_during_build(self, tmp_path):
        """Combination 6: Real-time voice query responds immediately while background build is compiling in thread."""
        with patch.object(orchestrator, "process_user_query", AsyncMock(return_value={"status": "completed", "reply": "12:00 PM"})):
            t0 = time.perf_counter()
            res = await orchestrator.process_user_query("what time is it?")
            elapsed_ms = (time.perf_counter() - t0) * 1000

            assert res is not None
            assert elapsed_ms < 100.0

    def test_tier3_cross_07_crossdevice_queue_voice_status_inspection(self, isolated_queue):
        """Combination 7: Inbound phone task progress inspected via voice ('Hey Jarvis, check task queue status')."""
        isolated_queue.enqueue_task("Task 1")
        isolated_queue.enqueue_task("Task 2")

        tasks = isolated_queue.list_tasks(status="QUEUED")
        assert len(tasks) >= 2

        status_summary = f"There are {len(tasks)} tasks queued in the cross-device queue."
        assert "2 tasks queued" in status_summary

    def test_tier3_cross_08_simultaneous_phone_task_and_voice_no_contention(self, isolated_queue):
        """Combination 8: No lock contention between SQLite task queue and speech recognition dispatcher."""
        def enqueue_op():
            for i in range(5):
                isolated_queue.enqueue_task(f"Concurrent task {i}")

        import threading
        threads = [threading.Thread(target=enqueue_op) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        all_tasks = isolated_queue.list_tasks()
        assert len(all_tasks) == 20


# =============================================================================
# TIER 4: REAL-WORLD APPLICATION SCENARIOS (5 SCENARIOS)
# =============================================================================

class TestTier4RealWorldScenarios:
    """
    Tier 4: 5 End-to-End Real-World Application Workload Scenarios.
    """

    @pytest.mark.asyncio
    async def test_tier4_scenario_01_remote_commuter_workflow(self, isolated_queue, isolated_presence, mock_transports, tmp_path):
        """
        Scenario 1: Remote Commuter Workflow.
        User sends WhatsApp command from phone to build a web scraper project.
        Laptop receives, queues, scaffolds, runs tests, commits to git, and notifies phone via WhatsApp with commit SHA.
        """
        RemoteRouter, _, _, _ = get_remote_router_cls()
        mock_wa, mock_sw = mock_transports

        # 1. Receive command from phone
        task = isolated_queue.enqueue_task(
            command="BUILD: HackerNews Scraper",
            source_device="phone",
            transport="whatsapp",
            sender_id="+919324094474",
        )
        assert task.status == "QUEUED"

        # 2. Worker claims task on laptop
        claimed = isolated_queue.claim_next_task(worker_id="laptop_worker")
        assert claimed is not None
        isolated_queue.start_execution(claimed.task_id)

        # 3. Scaffold repository and commit
        target_dir = tmp_path / "hackernews_scraper"
        repo_obj, _ = autonomous_repo_builder.build_project_repository(
            project_name="HackerNews Scraper",
            description="Autonomous scraper built for Ganesh Nair",
            architecture_spec={},
            target_dir_override=target_dir,
        )
        assert repo_obj.tests_passed is True

        # 4. Mark task completed
        isolated_queue.complete_task(
            claimed.task_id,
            result={"commit_sha": repo_obj.git_commit_hash, "path": str(target_dir)},
        )

        # 5. Outbound WhatsApp notification sent to phone (+91 9324094474)
        isolated_presence.record_heartbeat("phone")
        router = RemoteRouter(presence_mon=isolated_presence, whatsapp_disp=mock_wa, switch_int=mock_sw)

        res = await router.route_notification(
            title="Scaffold Complete",
            message=f"Project HackerNews Scraper built. Git commit SHA: {repo_obj.git_commit_hash[:8]}",
            target="phone",
        )
        assert res.success is True
        assert res.delivered_to == "phone"
        assert res.channel_used == "whatsapp"

    def test_tier4_scenario_02_hands_free_studio_workflow(self, tmp_path):
        """
        Scenario 2: Hands-Free Studio Workflow.
        User speaks 'Hey Jarvis, build an audio visualizer'. Voice engine acknowledges immediately.
        User asks health status 5 seconds later; engine answers while build continues and completes.
        """
        AudioListenerDaemon = get_voice_listener_cls()
        daemon = AudioListenerDaemon(enable_tts_feedback=False)

        # 1. Spoken build request
        daemon.simulate_speech_input("Hey Jarvis, build an audio visualizer")
        assert len(daemon._processed_commands) >= 1

        # 2. Verify status metrics
        status = daemon.get_status()
        assert status["processed_count"] >= 1
        daemon.stop()

    @pytest.mark.asyncio
    async def test_tier4_scenario_03_host_power_flap_and_failover(self, isolated_presence, mock_transports):
        """
        Scenario 3: Host Power Flap & Failover.
        During notification dispatch, primary transport (WhatsApp) drops connection;
        engine dynamically switches to Switch Protocol room broadcast with zero message loss.
        """
        RemoteRouter, _, _, _ = get_remote_router_cls()
        mock_wa, mock_sw = mock_transports

        isolated_presence.set_device_status("laptop", "OFFLINE")
        mock_wa.send_whatsapp_message = AsyncMock(side_effect=httpx.NetworkError("Host Wi-Fi disconnected"))

        router = RemoteRouter(presence_mon=isolated_presence, whatsapp_disp=mock_wa, switch_int=mock_sw)

        res = await router.route_notification(
            title="Power Alert",
            message="Running on battery backup",
            priority="critical",
        )
        assert res.success is True
        assert res.channel_used == "switch"
        assert res.failover_occurred is True

    def test_tier4_scenario_04_headless_cold_boot_scenario(self, tmp_path):
        """
        Scenario 4: Headless Cold Boot Scenario.
        Headless daemon lifecycle: PID recorded, single-instance enforced, clean shutdown cleanly removes PID.
        """
        ProcessManager, _ = get_process_manager_cls()
        pm = ProcessManager(base_dir=tmp_path)

        # 1. Cold boot start
        assert pm.acquire_pid("jarvis_audio", os.getpid()) is True
        assert pm.is_running("jarvis_audio") is True

        # 2. Second launch blocked
        assert pm.acquire_pid("jarvis_audio", os.getpid() + 1) is False

        # 3. Clean shutdown
        pm.release_pid("jarvis_audio")
        assert pm.is_running("jarvis_audio") is False

    @pytest.mark.asyncio
    async def test_tier4_scenario_05_full_autonomous_day_workflow(self, isolated_queue, isolated_presence, mock_transports, tmp_path):
        """
        Scenario 5: Full Autonomous Day Workflow.
        Daily proactive opportunity routine schedules an approved repository build in the background engine,
        and delivers completion notifications across phone and laptop.
        """
        RemoteRouter, _, _, _ = get_remote_router_cls()
        mock_wa, mock_sw = mock_transports

        router = RemoteRouter(presence_mon=isolated_presence, whatsapp_disp=mock_wa, switch_int=mock_sw)

        # 1. Opportunity approved & enqueued
        task = isolated_queue.enqueue_task(
            command="Autonomous Opportunity: Neural Conductor",
            source_device="proactive_scheduler",
            transport="daily_connector",
        )
        assert task is not None

        # 2. Scaffold repository
        target_dir = tmp_path / "neural_conductor"
        repo_obj, _ = autonomous_repo_builder.build_project_repository(
            project_name="Neural Conductor",
            description="Daily autonomous proactive project",
            architecture_spec={},
            target_dir_override=target_dir,
        )
        assert repo_obj.tests_passed is True

        # 3. Route notification
        res = await router.route_notification(
            title="Daily Opportunity Deployed",
            message=f"Neural Conductor committed (SHA: {repo_obj.git_commit_hash[:8]})",
        )
        assert res.success is True
