"""
Acoustic Wake Gate verification (Sprint 2 P0).

Proves the openWakeWord-backed wake gate is wired into the VoiceDaemon:
  1. Gate hit  -> wake accepted, Whisper runs once for command extraction.
  2. Ambient speech with NO gate hit -> Whisper never runs (the low-power path).
  3. Gate unavailable -> fail-closed to the legacy transcription wake path.
  4. Gate disabled (constructor) -> byte-for-byte legacy behavior, gate untouched.
  5. Real openWakeWord smoke test (honestly skipped if models can't load).

Uses injected fake gates/fakes for determinism - no mocking of the daemon's
state machine itself: every test drives the real feed() block pipeline.
"""

import os
import time
from typing import Any, Dict, List

import numpy as np
import pytest

from jarvis.voice.daemon import VoiceDaemon
from jarvis.voice.wake import AcousticWakeGate


# --------------------------------------------------------------------- #
#  Audio helpers: 16 kHz int16 PCM blocks with a config-vetoable gate    #
# --------------------------------------------------------------------- #

@pytest.fixture(autouse=True)
def legacy_gate_env(monkeypatch):
    """Tests inject gates explicitly; keep the env default deterministic."""
    monkeypatch.setenv("JARVIS_ACOUSTIC_GATE", "on")


SR = VoiceDaemon.SAMPLE_RATE          # 16000
BLOCK_FRAMES = VoiceDaemon.BLOCK_FRAMES  # 1600


def speech_block() -> bytes:
    t = np.arange(BLOCK_FRAMES) / float(SR)
    return (np.sin(2 * np.pi * 220.0 * t) * 3000.0).astype(np.int16).tobytes()


def silence_block() -> bytes:
    return np.zeros(BLOCK_FRAMES, dtype=np.int16).tobytes()


def feed_utterance(daemon: VoiceDaemon, events: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Feeds one speech utterance (8 blocks) + trailing silence (8 blocks)."""
    events = events if events is not None else []
    for _ in range(8):
        events.extend(daemon.feed(speech_block()))
    for _ in range(8):
        events.extend(daemon.feed(silence_block()))
    return events


# --------------------------------------------------------------------- #
#  Fakes                                                                #
# --------------------------------------------------------------------- #

class FakeGate:
    """Deterministic acoustic gate: returns a fixed verdict."""

    def __init__(self, available: bool = True, hit: bool = False, score: float = None):
        self.available = available
        self.hit = hit
        self.threshold = 0.5
        self.model_names: List[str] = ["hey_jarvis"] if available else []
        self.unavailable_reason = "" if available else "model load failed"
        self.calls = 0
        self.reset_calls = 0
        self._score = score if score is not None else (0.83 if hit else 0.12)

    def gate(self, block: bytes) -> Dict[str, Any]:
        self.calls += 1
        return {
            "wake": self.hit,
            "score": self._score,
            "source": "acoustic" if self.available else "acoustic_unavailable",
            "threshold": self.threshold,
            "timestamp": time.time(),
        }

    def reset(self) -> None:
        self.reset_calls += 1


class RecordingSTT:
    """Always returns a fixed transcript; counts transcription calls."""

    def __init__(self, text: str):
        self.text = text
        self.calls = 0

    def transcribe(self, wav: bytes, sample_rate: int = SR) -> Dict[str, Any]:
        self.calls += 1
        return {"text": self.text, "confidence": 0.91}


class MustNotTranscribe:
    """Fails the test if Whisper is invoked (proves the gate skipped STT)."""

    def __init__(self):
        self.calls = 0

    def transcribe(self, wav: bytes, sample_rate: int = SR) -> Dict[str, Any]:
        self.calls += 1
        raise AssertionError("Whisper ran on gated ambient speech")


class RecordingOrchestrator:
    def __init__(self):
        self.calls: List[str] = []

    async def process_user_query(self, query: str):
        self.calls.append(query)
        return {
            "task_id": f"tsk_{len(self.calls)}",
            "status": "COMPLETED",
            "response": {"message": "Weather is clear. CPU nominal."},
        }


# --------------------------------------------------------------------- #
#  1. Gate hit: wake accepted, Whisper used for command extraction      #
# --------------------------------------------------------------------- #

def test_gate_hit_runs_whisper_and_executes_command():
    gate = FakeGate(hit=True)
    stt = RecordingSTT("hey jarvis what is the weather")
    orch = RecordingOrchestrator()
    daemon = VoiceDaemon(
        stt=stt, orchestrator=orch, speak_replies=False, gate=gate,
        acoustic_gate_enabled=True,
    )
    daemon.state = "LISTENING_FOR_WAKE"

    feed_utterance(daemon)

    # Whisper ran exactly once (for the wake utterance) and the post-wake
    # command reached the orchestrator stripped of the wake phrase.
    assert stt.calls == 1
    assert orch.calls == ["what is the weather"]
    assert daemon.wake_count == 1
    assert daemon.acoustic_wake_count == 1
    assert daemon.command_count == 1

    # Every hit frame left a First-Law receipt, plus the wake decision itself.
    frames = [e for e in daemon.evidence_log if e.get("source") == "voice_daemon.acoustic_wake_frame"]
    assert frames, "acoustic frame hit must be recorded as evidence"
    assert frames[0]["data"]["score"] >= 0.5
    wakes = [e for e in daemon.evidence_log if e.get("source", "").startswith("voice_daemon.wake")]
    assert wakes
    assert wakes[0]["data"]["source"] == "transcription+acoustic"


def test_gate_hit_wake_then_command_capture():
    """'hey jarvis' alone -> CAPTURING_COMMAND; next utterance is the command."""
    gate = FakeGate(hit=True)
    stt = RecordingSTT("hey jarvis")
    orch = RecordingOrchestrator()
    daemon = VoiceDaemon(
        stt=stt, orchestrator=orch, speak_replies=False, gate=gate,
        acoustic_gate_enabled=True,
    )
    daemon.state = "LISTENING_FOR_WAKE"

    events = feed_utterance(daemon)
    wake_events = [e for e in events if e.get("type") == "wake_detected"]
    assert len(wake_events) == 1
    assert wake_events[0]["source"] == "transcription"
    assert daemon.state == "CAPTURING_COMMAND"
    calls_after_wake = gate.calls

    # The command utterance is captured WITHOUT re-running the acoustic gate.
    stt.text = "what is the weather"
    events.extend(feed_utterance(daemon))
    assert orch.calls == ["what is the weather"]
    assert gate.calls == calls_after_wake, "gate must not run while capturing a command"
    assert daemon.state == "LISTENING_FOR_WAKE"
    assert daemon.acoustic_wake_count == 1


# --------------------------------------------------------------------- #
#  2. Ambient speech with no gate hit: Whisper must never run           #
# --------------------------------------------------------------------- #

def test_ambient_speech_gated_before_whisper():
    gate = FakeGate(hit=False)
    stt = MustNotTranscribe()
    orch = RecordingOrchestrator()
    daemon = VoiceDaemon(
        stt=stt, orchestrator=orch, speak_replies=False, gate=gate,
        acoustic_gate_enabled=True,
    )
    daemon.state = "LISTENING_FOR_WAKE"

    feed_utterance(daemon)

    assert stt.calls == 0, "gated ambient speech must not reach Whisper"
    assert daemon.gated_utterance_count == 1
    assert daemon.wake_count == 0
    assert daemon.acoustic_wake_count == 0
    assert daemon.state == "LISTENING_FOR_WAKE"
    # Gate scored every listening block (speech AND trailing silence): the
    # measured behavior is that the wake verdict lands on post-phrase frames.
    assert gate.calls == 16


# --------------------------------------------------------------------- #
#  2b. Cooldown: the gate may not double-fire after a wake              #
# --------------------------------------------------------------------- #

def test_wake_cooldown_suppresses_acoustic_repeat():
    """After a wake+command, the acoustic gate is suppressed for a window;
    the legacy transcription path still hears the wake phrase (by design)."""
    gate = FakeGate(hit=True)
    stt = RecordingSTT("hey jarvis what is the weather")
    orch = RecordingOrchestrator()
    daemon = VoiceDaemon(
        stt=stt, orchestrator=orch, speak_replies=False, gate=gate,
        acoustic_gate_enabled=True,
    )
    daemon.state = "LISTENING_FOR_WAKE"

    feed_utterance(daemon)  # wake + command executed, cooldown armed
    assert daemon.wake_count == 1
    assert daemon.acoustic_wake_count == 1
    calls_after_wake = gate.calls

    # Second wake utterance arrives inside the cooldown window.
    feed_utterance(daemon)

    assert gate.calls == calls_after_wake, "cooldown must silence gate scoring"
    assert daemon.acoustic_wake_count == 1, "acoustic wake must not double-fire"
    assert daemon.wake_count == 2, "transcription path still hears the wake phrase"
    assert len(orch.calls) == 2


# --------------------------------------------------------------------- #
#  3. Gate unavailable: fail-closed to legacy transcription wake        #
# --------------------------------------------------------------------- #

def test_gate_unavailable_falls_back_to_transcription_wake():
    gate = FakeGate(available=False, hit=False)
    stt = RecordingSTT("hey jarvis what is the weather")
    orch = RecordingOrchestrator()
    daemon = VoiceDaemon(
        stt=stt, orchestrator=orch, speak_replies=False, gate=gate,
        acoustic_gate_enabled=True,
    )
    daemon.state = "LISTENING_FOR_WAKE"

    feed_utterance(daemon)

    # Legacy path intact: Whisper on every utterance, phrase match wakes.
    assert stt.calls == 1
    assert orch.calls == ["what is the weather"]
    assert daemon.wake_count == 1
    assert daemon.acoustic_wake_count == 0


# --------------------------------------------------------------------- #
#  4. Gate disabled: pure legacy, gate object untouched                 #
# --------------------------------------------------------------------- #

def test_gate_disabled_is_pure_legacy(monkeypatch):
    monkeypatch.setenv("JARVIS_ACOUSTIC_GATE", "off")
    gate = FakeGate(hit=True)
    stt = RecordingSTT("hey jarvis system status")
    orch = RecordingOrchestrator()
    daemon = VoiceDaemon(
        stt=stt, orchestrator=orch, speak_replies=False, gate=gate,
        acoustic_gate_enabled=None,  # env resolves to off
    )
    daemon.state = "LISTENING_FOR_WAKE"

    feed_utterance(daemon)

    assert daemon._gate_enabled is False
    assert gate.calls == 0, "disabled gate is never touched"
    assert stt.calls == 1
    assert orch.calls == ["system status"]


# --------------------------------------------------------------------- #
#  5. Health reports acoustic state honestly                            #
# --------------------------------------------------------------------- #

def test_health_reports_acoustic_fields():
    gate = FakeGate(hit=False)
    daemon = VoiceDaemon(gate=gate, speak_replies=False)
    daemon.state = "LISTENING_FOR_WAKE"

    h = daemon.health()
    assert h["acoustic_gate_enabled"] is True
    assert isinstance(h["acoustic_gate_installed"], bool)
    assert h["acoustic_gate_armed"] is True
    assert h["acoustic_gate_engine"] == "openwakeword-onnx"
    assert h["acoustic_gate_threshold"] == 0.5
    assert h["acoustic_wake_count"] == 0
    assert h["gated_utterance_count"] == 0
    assert h["last_acoustic_score"] == 0.0

    # Unloaded-but-enabled daemon must not fake an armed gate.
    daemon2 = VoiceDaemon(speak_replies=False)
    h2 = daemon2.health()
    assert h2["acoustic_gate_armed"] is False
    assert h2["acoustic_gate_engine"] is None

    # Failed gate must surface its reason.
    from types import SimpleNamespace
    dead = SimpleNamespace(
        available=False,
        unavailable_reason="model load failed",
        reset=lambda: None,
        gate=lambda b: {},
        threshold=0.5,
        model_names=[],
    )
    daemon3 = VoiceDaemon(gate=dead, speak_replies=False)
    h3 = daemon3.health()
    assert h3["acoustic_gate_armed"] is False
    assert h3["acoustic_gate_unavailable_reason"] == "model load failed"


# --------------------------------------------------------------------- #
#  6. Frame accumulation math (no model dependency)                     #
# --------------------------------------------------------------------- #

class FrameRecordingModel:
    def __init__(self, score=0.4):
        self.frames = []
        self.score = score

    def predict(self, frame: np.ndarray) -> Dict[str, float]:
        self.frames.append(int(np.asarray(frame).size))
        return {"hey_jarvis": self.score}

    def reset(self) -> None:
        self.frames.append(-1)


def test_frame_accumulation_and_threshold():
    gate = AcousticWakeGate.__new__(AcousticWakeGate)  # construct without model load
    gate.available = True
    gate.threshold = 0.5
    gate.model_names = ["hey_jarvis"]
    gate._pending = bytearray()
    gate.last_score = 0.0
    gate._model = FrameRecordingModel(score=0.4)

    event = gate.gate(speech_block())  # 1600 samples = 3200 bytes
    assert event["source"] == "acoustic"
    assert event["wake"] is False
    assert abs(event["score"] - 0.4) < 1e-6
    # 3200 bytes pending, frame consumes 2560 -> 1 frame scored so far
    assert gate._model.frames == [1280]

    event = gate.gate(speech_block())  # second block completes another frame
    assert gate._model.frames == [1280, 1280]
    assert event["wake"] is False

    # Above threshold triggers a wake
    gate._model.score = 0.9
    event = gate.gate(speech_block())
    assert event["wake"] is True
    assert event["score"] == 0.9

    # Unavailable gate reports honestly
    gate.available = False
    event = gate.gate(speech_block())
    assert event["source"] == "acoustic_unavailable"
    assert event["wake"] is False


# --------------------------------------------------------------------- #
#  7. Real openWakeWord model smoke (honest skip when unavailable)       #
# --------------------------------------------------------------------- #

def test_real_openwakeword_model_smoke():
    import importlib.util
    if importlib.util.find_spec("openwakeword") is None:
        pytest.skip("openwakeword not installed on this host")
    if os.getenv("JARVIS_SKIP_REAL_WAKE", "").strip() in ("1", "true", "yes"):
        pytest.skip("JARVIS_SKIP_REAL_WAKE set")

    from jarvis.voice.wake import get_acoustic_gate
    gate = get_acoustic_gate()
    if not gate.available:
        pytest.skip(f"openWakeWord models could not load: {gate.unavailable_reason}")

    event = gate.gate(silence_block())
    assert event["source"] == "acoustic"
    assert event["wake"] in (True, False)
    assert 0.0 <= float(event["score"]) <= 1.0
    assert event["threshold"] == gate.threshold
    gate.reset()
