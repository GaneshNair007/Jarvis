"""
Always-On Voice Daemon Verification Suite.

Proves the full "Hey Jarvis" loop with REAL audio:
  SAPI speech synthesis -> PCM segmentation -> faster-whisper transcription
  -> wake phrase detection -> command extraction -> orchestrator execution
  -> Evidence recording.

No mocked wake word, no stubbed STT, no fake transcripts.
"""

import time

import pytest

from jarvis.voice.daemon import VoiceDaemon


class RecordingOrchestrator:
    """Captures commands routed through the daemon."""

    def __init__(self):
        self.calls = []

    async def process_user_query(self, query: str):
        self.calls.append(query)
        return {
            "task_id": f"tsk_{len(self.calls)}",
            "status": "COMPLETED",
            "response": {"message": "System health nominal. CPU 12 percent."},
        }


class RecordingTTS:
    """Captures spoken replies instead of playing them."""

    def __init__(self):
        self.spoken = []
        self.cancelled = False

    def speak_live(self, text, async_mode=True):
        self.spoken.append(text)
        return True

    def cancel_speech(self):
        self.cancelled = True


def _sapi_pcm(text: str):
    """Synthesizes real spoken audio and returns raw 16 kHz mono PCM bytes.

    SAPI outputs 22.05 kHz; the daemon's microphone path captures at 16 kHz,
    so the synthesized audio is resampled to match the real mic pipeline.
    """
    pytest.importorskip("win32com.client")
    import io
    import wave

    import numpy as np

    from jarvis.voice.tts import tts_engine

    wav_bytes = tts_engine.synthesize_to_wav(text)
    assert wav_bytes[:4] == b"RIFF", "TTS produced invalid WAV"

    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        source_rate = wf.getframerate()
        frames = wf.readframes(wf.getnframes())
    assert len(frames) > 16000, "TTS produced less than 1s of audio"

    samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32)
    target_len = max(1, int(round(len(samples) * 16000 / source_rate)))
    resampled = np.interp(
        np.linspace(0.0, 1.0, target_len),
        np.linspace(0.0, 1.0, len(samples)),
        samples,
    )
    return resampled.astype(np.int16).tobytes()


def _feed_speech(daemon: VoiceDaemon, pcm: bytes, block_ms: int = 100):
    """Feeds speech blocks followed by silence to flush the utterance."""
    block_bytes = VoiceDaemon.SAMPLE_RATE * 2 * block_ms // 1000
    events = []
    for i in range(0, len(pcm), block_bytes):
        events.extend(daemon.feed(pcm[i : i + block_bytes]))
    silence_block = bytes(block_bytes)
    idle_rounds = int((VoiceDaemon.SILENCE_END_SEC * 1000 / block_ms) + 3)
    for _ in range(idle_rounds):
        events.extend(daemon.feed(silence_block))
    return events


def _make_daemon():
    orch = RecordingOrchestrator()
    tts = RecordingTTS()
    daemon = VoiceDaemon(
        orchestrator=orch,
        tts=tts,
        speak_replies=True,
        wake_phrases=["hey jarvis", "jarvis", "ok jarvis"],
    )
    daemon.state = "LISTENING_FOR_WAKE"
    return daemon, orch, tts


def test_wake_phrase_extraction():
    """Wake phrase stripping yields clean command text."""
    daemon, _, _ = _make_daemon()
    assert daemon._strip_wake("Hey Jarvis, what is the system health") == "what is the system health"
    assert daemon._strip_wake("Jarvis. system health report") == "system health report"
    assert daemon._strip_wake("hello computer") == ""


def test_silence_produces_no_events():
    """Silence never triggers wake or command execution."""
    daemon, orch, _ = _make_daemon()
    silence = bytes(VoiceDaemon.SAMPLE_RATE * 2 // 10)  # 100 ms of zeros
    for _ in range(30):
        events = daemon.feed(silence)
        assert events == []
    assert orch.calls == []
    assert daemon.wake_count == 0


def test_noise_below_threshold_ignored():
    """Sub-threshold noise does not start an utterance buffer."""
    daemon, orch, _ = _make_daemon()
    import struct

    quiet = b"".join(struct.pack("<h", 50 if i % 2 == 0 else -50) for i in range(1600))
    for _ in range(20):
        daemon.feed(quiet)
    assert daemon._utterance_active is False
    assert orch.calls == []


def test_end_to_end_hey_jarvis_wake_and_command():
    """REAL audio: SAPI speech -> whisper -> wake + command -> execution + evidence."""
    daemon, orch, tts = _make_daemon()

    spoken_pcm = _sapi_pcm("Hey Jarvis, what is the system health")
    events = _feed_speech(daemon, spoken_pcm)

    # Real whisper must transcribe the wake phrase
    assert daemon.wake_count == 1, f"Wake phrase not detected. last_transcript={daemon.last_transcript!r}"

    # Command extracted from same utterance and executed through orchestrator
    assert len(orch.calls) == 1, f"Expected 1 orchestrator call, got {orch.calls}"
    command = orch.calls[0].lower()
    assert "health" in command or "system" in command, f"Command not extracted: {command!r}"

    # Reply spoken back
    assert len(tts.spoken) == 1
    assert "CPU" in tts.spoken[0]

    # First Law: wake and command both produced Evidence
    sources = [e["source"] for e in daemon.evidence_log]
    assert "voice_daemon.wake" in sources
    assert "voice_daemon.command" in sources

    # Event stream contains executed command
    assert any(e.get("type") == "command_executed" for e in events)

    health = daemon.health()
    assert health["wake_count"] == 1
    assert health["command_count"] == 1
    assert health["evidence_count"] >= 2


def test_two_stage_wake_then_command_capture():
    """Wake-only utterance arms capture; the next utterance becomes the command."""
    daemon, orch, tts = _make_daemon()

    wake_pcm = _sapi_pcm("Hey Jarvis")
    events = _feed_speech(daemon, wake_pcm)

    assert daemon.wake_count == 1, f"Wake failed: {daemon.last_transcript!r}"
    assert daemon.state == "CAPTURING_COMMAND", "Daemon must arm command capture after wake-only"
    assert any(e.get("type") == "wake_detected" for e in events)
    assert orch.calls == [], "No command should execute from wake-only utterance"

    command_pcm = _sapi_pcm("system health report")
    _feed_speech(daemon, command_pcm)

    assert len(orch.calls) == 1, f"Command capture failed: {daemon.last_transcript!r}"
    assert "health" in orch.calls[0].lower()
    assert daemon.state in ("SPEAKING", "LISTENING_FOR_WAKE")


def test_non_wake_speech_ignored():
    """Speech without wake phrase does not trigger execution."""
    daemon, orch, _ = _make_daemon()

    pcm = _sapi_pcm("the weather is quite pleasant today")
    _feed_speech(daemon, pcm)

    assert daemon.wake_count == 0
    assert orch.calls == []


def test_barge_in_cancels_speech():
    """A loud utterance during SPEAKING cancels TTS and returns to listening."""
    daemon, _, tts = _make_daemon()
    daemon.state = "SPEAKING"

    import struct

    loud = b"".join(struct.pack("<h", 8000 if i % 2 == 0 else -8000) for i in range(1600))
    events = daemon.feed(loud)

    assert tts.cancelled is True
    assert daemon.state == "LISTENING_FOR_WAKE"
    assert any(e.get("type") == "barge_in" for e in events)


def test_failed_orchestrator_returns_honest_error():
    """Orchestrator failures produce evidence-backed failure events, never fake success."""
    daemon, _, _ = _make_daemon()

    class FailingOrchestrator:
        async def process_user_query(self, query: str):
            raise RuntimeError("model router offline")

    daemon._orchestrator = FailingOrchestrator()

    pcm = _sapi_pcm("Hey Jarvis, system health")
    events = _feed_speech(daemon, pcm)

    assert any(e.get("type") == "command_failed" for e in events)
    assert daemon.error_count >= 1
    fail_evidence = [e for e in daemon.evidence_log if e["source"] == "voice_daemon.command"]
    assert fail_evidence and fail_evidence[-1]["data"].get("status") == "error"


def test_daemon_lifecycle_start_stop_without_microphone():
    """Daemon thread starts and stops cleanly with no physical mic attached."""
    daemon = VoiceDaemon(speak_replies=False)
    health = daemon.start(use_microphone=False)

    assert health["running"] is True
    assert health["state"] == "LISTENING_FOR_WAKE"
    assert health["microphone_open"] is False
    assert daemon.running is True
    time.sleep(0.3)

    stopped = daemon.stop()
    assert stopped["running"] is False
    assert stopped["state"] == "IDLE"
    assert daemon.running is False


def test_health_status_reports_real_telemetry():
    """Health snapshot exposes wake/command/evidence counters for the API."""
    daemon, orch, _ = _make_daemon()
    pcm = _sapi_pcm("Hey Jarvis, system health")
    _feed_speech(daemon, pcm)

    health = daemon.health()
    for key in (
        "running",
        "state",
        "wake_phrases",
        "wake_count",
        "command_count",
        "error_count",
        "last_transcript",
        "evidence_count",
        "stt_backend",
        "tts_backend",
    ):
        assert key in health, f"Missing health field: {key}"
    assert health["stt_backend"] == "faster-whisper"
    assert health["tts_backend"] == "windows_sapi"
    assert health["wake_count"] >= 1


def test_processing_state_ignores_audio_blocks():
    """Audio arriving while PROCESSING is discarded, not corrupted into events."""
    daemon, _, _ = _make_daemon()
    daemon.state = "PROCESSING"

    import struct

    loud = b"".join(struct.pack("<h", 9000 if i % 2 == 0 else -9000) for i in range(1600))
    for _ in range(10):
        assert daemon.feed(loud) == []
    assert daemon._utterance_active is False


def test_resample_linear_preserves_duration_and_shape():
    """44.1 kHz PCM resamples to 16 kHz with correct length and waveform."""
    import numpy as np

    from jarvis.voice.daemon import _resample_linear

    src_rate = 44100
    duration = 0.5
    t = np.arange(int(src_rate * duration)) / src_rate
    tone = (np.sin(2 * np.pi * 440 * t) * 12000).astype(np.int16)
    out = _resample_linear(tone.tobytes(), src_rate, 16000)

    out_samples = np.frombuffer(out, dtype=np.int16)
    expected_len = int(round(len(tone) * 16000 / src_rate))
    assert abs(len(out_samples) - expected_len) <= 2
    # 440 Hz tone must survive: dominant frequency still ~440 Hz.
    spectrum = np.abs(np.fft.rfft(out_samples.astype(np.float64)))
    freqs = np.fft.rfftfreq(len(out_samples), d=1 / 16000)
    dominant = freqs[int(np.argmax(spectrum))]
    assert abs(dominant - 440) < 25, f"dominant freq drifted to {dominant:.1f} Hz"
    # Same-rate passthrough must be byte-identical.
    assert _resample_linear(tone.tobytes(), 16000, 16000) == tone.tobytes()


def test_probe_input_devices_returns_measured_classification():
    """Probe records real audio from every input device and classifies it."""
    from jarvis.voice.daemon import probe_input_devices

    results = probe_input_devices(duration_sec=0.4)
    assert results, "probe found no input devices"
    valid = {"live", "silent", "glitch", "error"}
    for entry in results:
        assert entry["status"] in valid, f"bad status {entry['status']}"
        assert entry["name"], "device entry missing name"
        if entry["status"] in ("live", "silent", "glitch"):
            assert entry["mean"] >= 0
            assert "clipped_frac" in entry
            assert "nonzero_window_frac" in entry
    # This machine's Realtek mic must be measured, not assumed: whatever the
    # hardware reports, a "live" claim requires sustained non-clipped signal.
    for entry in results:
        if entry["status"] == "live":
            assert entry["mean"] >= 100.0
            assert entry["clipped_frac"] < 0.01
            assert entry["nonzero_window_frac"] >= 0.75


def test_select_input_device_prefers_live_shared_mode_device():
    """Selection logic: injected live probe result wins over default fallback."""
    from jarvis.voice.daemon import select_input_device

    probe = [
        {"index": 3, "name": "WDM-KS Glitchy", "hostapi": "Windows WDM-KS", "status": "glitch", "mean": 18000.0},
        {"index": 7, "name": "WDM-KS Dropouts", "hostapi": "Windows WDM-KS", "status": "glitch", "mean": 240.0},
        {"index": 1, "name": "Microphone Array", "hostapi": "MME", "status": "silent", "mean": 0.2},
        {"index": 5, "name": "Good Mic", "hostapi": "Windows WASAPI", "status": "live", "mean": 320.0},
    ]
    chosen = select_input_device(explicit=None, probe=probe)
    assert chosen["device"] == 5
    assert chosen["live"] is True
    assert chosen["source"] == "probe"

    # All-silent probe must fall back honestly (live=False), never claim live.
    silent_probe = [
        {"index": 1, "name": "Mic", "hostapi": "MME", "status": "silent", "mean": 0.2},
        {"index": 2, "name": "Glitch", "hostapi": "Windows WDM-KS", "status": "glitch", "mean": 18000.0},
    ]
    fallback = select_input_device(explicit=None, probe=silent_probe)
    assert fallback["live"] is False
    assert fallback["source"] == "default_fallback"
    assert fallback["probe_summary"]["live"] == 0
    assert fallback["probe_summary"]["silent"] == 1
    assert fallback["probe_summary"]["glitch"] == 1

    # Explicit device (or JARVIS_MIC_DEVICE env) bypasses probing.
    import sounddevice as sd

    input_idxs = [i for i, d in enumerate(sd.query_devices()) if d.get("max_input_channels", 0) >= 1]
    assert input_idxs, "no input devices on this machine"
    forced = select_input_device(explicit=input_idxs[0], probe=[])
    assert forced["device"] == input_idxs[0]
    assert forced["source"] == "explicit"


def test_start_with_microphone_opens_probed_device_and_reports_telemetry():
    """Real mic start: device is probed/selected and health exposes mic facts."""
    daemon = VoiceDaemon(speak_replies=False, probe_devices=True, mic_device=None)
    health = daemon.start(use_microphone=True)
    try:
        assert health["running"] is True
        assert health["microphone_open"] is True
        assert health["mic_device"] is not None
        assert health["mic_device_name"], "selected device must carry a name"
        assert health["mic_source"] in ("probe", "default_fallback", "explicit")
        assert isinstance(health["mic_live"], bool)
        assert health["mic_capture_rate"] >= 8000
        # Evidence records what was actually opened (First Law).
        start_records = [e for e in daemon.evidence_log if e["source"] == "voice_daemon.started"]
        assert start_records and start_records[-1]["data"]["microphone"] is True
        assert start_records[-1]["data"]["mic"]["device"] == health["mic_device"]
    finally:
        daemon.stop()
    assert daemon.running is False
