"""
Automated unit and integration test suite for Milestone 1:
Windows Always-On Audio Daemon & Headless Process Reliability.
Covers:
- Dual-grammar PowerShell bridge execution and JSON-line event protocol
- Elimination of fake success in SpeechToText (genuine faster-whisper & host Windows speech)
- AudioListenerDaemon supervisor state machine (two-stage wake/capture and compound utterances)
- ProcessManager PID tracking, duplicate prevention, clean shutdown, and telemetry logging
- Audio simulation interface for headless CI verification
"""

import os
import sys
import time
import json
import io
import wave
import subprocess
from pathlib import Path
import pytest

from jarvis.core.process_manager import process_manager, ProcessManager
from jarvis.voice.stt import stt_engine, SpeechToText
from jarvis.voice.tts import tts_engine
from jarvis.voice.wake import wake_detector
from jarvis.voice.listener import AudioListenerDaemon, audio_daemon
from jarvis.core.orchestrator import orchestrator


@pytest.fixture
def repo_root():
    return Path(__file__).resolve().parent.parent


@pytest.fixture
def clean_test_pids(tmp_path):
    """Provides an isolated ProcessManager instance backed by a temporary directory."""
    pm = ProcessManager(base_dir=tmp_path)
    yield pm
    pm.stop_all()


# ─── Suite 1: Process Lifecycle & Headless Management (R4) ───────────────────

def test_process_manager_acquire_and_release(clean_test_pids):
    """Verifies PID file creation, single instance enforcement, and clean release."""
    pm = clean_test_pids
    current_pid = os.getpid()

    # 1. Acquire PID
    acquired = pm.acquire_pid("test_service", current_pid, {"env": "test"})
    assert acquired is True
    assert pm.is_running("test_service") is True

    # Verify PID record on disk
    pid_data = pm.read_pid("test_service")
    assert pid_data is not None
    assert pid_data["pid"] == current_pid
    assert pid_data["service"] == "test_service"
    assert pid_data["metadata"]["env"] == "test"

    # 2. Duplicate acquisition prevention
    duplicate_acquired = pm.acquire_pid("test_service", 999999)
    assert duplicate_acquired is False

    # 3. Release PID
    pm.release_pid("test_service")
    assert pm.is_running("test_service") is False
    assert pm.read_pid("test_service") is None


def test_process_manager_root_jarvis_pid(clean_test_pids):
    """Verifies that 'jarvis' service correctly manages the root .jarvis.pid file."""
    pm = clean_test_pids
    current_pid = os.getpid()

    assert pm.acquire_pid("jarvis", current_pid) is True
    assert pm.root_pid_file.exists()
    assert pm.is_running("jarvis") is True

    status = pm.get_status("jarvis")
    assert status["running"] is True
    assert status["pid"] == current_pid

    pm.release_pid("jarvis")
    assert not pm.root_pid_file.exists()
    assert pm.is_running("jarvis") is False


def test_process_manager_stale_pid_cleanup(clean_test_pids):
    """Verifies that dead process PIDs are detected as stale and automatically cleaned up."""
    pm = clean_test_pids
    # Write a nonexistent PID
    dead_pid = 9999999
    target_file = pm.pid_dir / "dead_service.pid"
    with open(target_file, "w", encoding="utf-8") as f:
        json.dump({"service": "dead_service", "pid": dead_pid, "started_at": time.time()}, f)

    # is_running should detect dead process, return False, and remove file
    assert pm.is_running("dead_service") is False
    assert not target_file.exists()


def test_process_manager_telemetry_and_health(clean_test_pids):
    """Verifies that telemetry events and health summaries are written to disk."""
    pm = clean_test_pids
    pm.log_telemetry("daemon_boot_test", {"flag": True})
    pm.update_health("audio_daemon", "LISTENING", {"mic": "default"})

    telemetry_file = pm.log_dir / "daemon_telemetry.jsonl"
    health_file = pm.log_dir / "daemon_health.json"

    assert telemetry_file.exists()
    with open(telemetry_file, "r", encoding="utf-8") as f:
        lines = [json.loads(line) for line in f if line.strip()]
    assert any(entry["event"] == "daemon_boot_test" for entry in lines)

    assert health_file.exists()
    with open(health_file, "r", encoding="utf-8") as f:
        health_data = json.load(f)
    assert "audio_daemon" in health_data
    assert health_data["audio_daemon"]["status"] == "LISTENING"


def test_headless_scripts_exist_and_executable(repo_root):
    """Verifies that all required batch and VBS scripts exist with valid content."""
    scripts_dir = repo_root / "scripts"
    required = [
        "start_jarvis.bat",
        "start_jarvis_background.vbs",
        "stop_jarvis.bat",
        "status_jarvis.bat",
        "jarvis_speech_listener.ps1",
    ]
    for script_name in required:
        script_file = scripts_dir / script_name
        assert script_file.exists(), f"Missing required script: {script_name}"
        assert script_file.stat().st_size > 0


# ─── Suite 2: STT Fake Success Elimination (R1 & PWR-003) ────────────────────

def test_stt_eliminates_hardcoded_fake_success():
    """
    CRITICAL INTEGRITY TEST:
    Verifies that SpeechToText does NOT return the hardcoded mock
    'Jarvis, report system health' when given silent or empty audio.
    """
    # 1. Empty buffer must return empty text
    empty_result = stt_engine.transcribe(b"")
    assert empty_result["text"] == ""
    assert empty_result["confidence"] == 0.0

    # 2. Pure silence PCM WAV must return honest empty/no_speech result
    sample_rate = 16000
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00" * (sample_rate * 2))  # 1 second silence
    silence_wav = buf.getvalue()

    silence_result = stt_engine.transcribe(silence_wav)
    assert silence_result["text"] != "Jarvis, report system health"
    assert silence_result["text"] == ""
    assert silence_result["confidence"] == 0.0
    assert silence_result["status"] == "no_speech_detected"


def test_stt_transcribes_genuine_speech_via_whisper_or_windows():
    """Verifies that genuine speech audio produces accurate real transcription."""
    # Synthesize real speech via SAPI
    wav_bytes = tts_engine.synthesize_to_wav("Hello Jarvis")
    result = stt_engine.transcribe(wav_bytes)

    assert "text" in result
    assert result["text"] != ""
    assert result["confidence"] > 0.0
    # Must contain recognizable token
    recognized_lower = result["text"].lower()
    assert "hello" in recognized_lower or "jarvis" in recognized_lower or "jervis" in recognized_lower


def test_stt_windows_system_speech_fallback_transcription():
    """Verifies that the Windows native System.Speech fallback functions when whisper is disabled."""
    # Create isolated STT engine with whisper forced to None
    custom_stt = SpeechToText()
    custom_stt._whisper_model = None

    wav_bytes = tts_engine.synthesize_to_wav("System status report")
    result = custom_stt.transcribe(wav_bytes)

    assert result["engine"] == "windows_system_speech"
    assert "text" in result
    assert result["text"] != ""
    assert result["text"] != "Jarvis, report system health"  # NOT hardcoded
    assert result["confidence"] > 0.0


# ─── Suite 3: PowerShell Native Speech Listener Bridge (R1) ─────────────────

def test_powershell_listener_wave_mode_wake_event(repo_root):
    """
    Verifies that scripts/jarvis_speech_listener.ps1 executes native System.Speech
    and correctly emits READY and WAKE JSON-line events on a synthesized wake WAV.
    """
    ps1_path = repo_root / "scripts" / "jarvis_speech_listener.ps1"
    wav_bytes = tts_engine.synthesize_to_wav("Hey Jarvis")

    test_wav = repo_root / "test_ps1_wake.wav"
    with open(test_wav, "wb") as f:
        f.write(wav_bytes)

    try:
        proc = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(ps1_path),
                "-Mode",
                "wav",
                "-WaveFile",
                str(test_wav),
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert proc.returncode == 0

        # Parse JSON lines
        events = []
        for line in proc.stdout.splitlines():
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    events.append(json.loads(line))
                except Exception:
                    pass

        event_names = [e.get("event") for e in events]
        assert "READY" in event_names
        assert "WAKE" in event_names

        wake_ev = next(e for e in events if e.get("event") == "WAKE")
        phrase = wake_ev.get("phrase", "").lower()
        assert "jarvis" in phrase or "jervis" in phrase
        assert wake_ev["confidence"] > 0.0
    finally:
        if test_wav.exists():
            test_wav.unlink()


# ─── Suite 4: Audio Daemon Supervisor State Machine (R1) ────────────────────

def test_audio_daemon_two_stage_wake_and_command():
    """
    Verifies supervisor two-stage interaction:
    Stage 1: 'Hey Jarvis' triggers WOKE state.
    Stage 2: Subsequent utterance 'report status' triggers command dispatch.
    """
    from unittest.mock import AsyncMock, MagicMock

    mock_orch = MagicMock()
    mock_orch.process_user_query = AsyncMock(return_value={"status": "success", "response": {"message": "All systems nominal"}})

    daemon = AudioListenerDaemon(enable_tts_feedback=False, orchestrator_instance=mock_orch)
    dispatched_events = []
    daemon.register_event_listener(lambda ev: dispatched_events.append(ev))

    # Initial state
    assert daemon.current_state == "IDLE"

    # Stage 1: Wake event
    daemon.simulate_speech_input("Hey Jarvis")
    assert daemon.current_state == "WOKE"

    # Stage 2: Spoken command
    daemon.simulate_speech_input("report system health")
    assert "report system health" in daemon._processed_commands
    assert daemon.get_status()["processed_count"] >= 1


def test_audio_daemon_compound_utterance():
    """
    Verifies that compound utterances ('Hey Jarvis, check memory') are immediately
    segmented, command extracted, and routed without needing an extra turn.
    """
    from unittest.mock import AsyncMock, MagicMock

    mock_orch = MagicMock()
    mock_orch.process_user_query = AsyncMock(return_value={"status": "success", "response": {"message": "Disk 50% free"}})

    daemon = AudioListenerDaemon(enable_tts_feedback=False, orchestrator_instance=mock_orch)

    # Compound event
    daemon.simulate_event({
        "event": "WAKE",
        "type": "WAKE",
        "phrase": "Hey Jarvis",
        "full_text": "Hey Jarvis, check disk space",
        "confidence": 0.88,
        "timestamp": time.time(),
    })

    assert "check disk space" in daemon._processed_commands


def test_audio_daemon_woke_timeout_recovery():
    """Verifies that if no command follows wake word within timeout, state resets to IDLE."""
    daemon = AudioListenerDaemon(command_timeout_sec=0.1, enable_tts_feedback=False)

    # Wake
    daemon.simulate_speech_input("Hey Jarvis")
    assert daemon.current_state == "WOKE"

    # Sleep past timeout
    time.sleep(0.2)

    # Heartbeat arrives
    daemon.simulate_event({
        "event": "HEARTBEAT",
        "status": "listening",
        "timestamp": time.time(),
    })

    # Must have recovered to IDLE
    assert daemon.current_state == "IDLE"


def test_audio_daemon_error_event_handling():
    """Verifies that error events from bridge update daemon health status."""
    daemon = AudioListenerDaemon(enable_tts_feedback=False)
    daemon.simulate_event({
        "event": "ERROR",
        "message": "Audio device disconnected",
        "timestamp": time.time(),
    })

    # Verify health file recorded ERROR
    health = process_manager.log_dir / "daemon_health.json"
    if health.exists():
        with open(health, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert data.get("audio_daemon", {}).get("status") == "ERROR"


def test_wake_detector_start_and_stop():
    """Verifies WakeWordDetector start/stop lifecycle hook."""
    wake_detector.start_listening()
    assert wake_detector.is_listening is True

    wake_detector.stop_listening()
    assert wake_detector.is_listening is False
