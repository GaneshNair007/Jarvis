"""Iron Man app-connection fast-path tests (match + execute, spawner-injected)."""

import os
import time
from typing import Any, Dict, List

import numpy as np
import pytest

from jarvis.automation import app_connector
from jarvis.automation.app_connector import (
    match_app_intent,
    launch_app,
    launch_in_console,
    opencode_delegate,
    antigravity_delegate,
)

SR = 16000
BLOCK = 1600


def speech_block() -> bytes:
    t = np.arange(BLOCK) / float(SR)
    return (np.sin(2 * np.pi * 220.0 * t) * 3000.0).astype(np.int16).tobytes()


def silence_block() -> bytes:
    return np.zeros(BLOCK, dtype=np.int16).tobytes()


def feed_utterance(daemon) -> List[Dict[str, Any]]:
    events = []
    for _ in range(8):
        events.extend(daemon.feed(speech_block()))
    for _ in range(8):
        events.extend(daemon.feed(silence_block()))
    return events


class FakeGate:
    def __init__(self, hit: bool = True):
        self.hit = hit
        self.threshold = 0.5
        self.available = True
        self.model_names = ["hey_jarvis"]
        self.unavailable_reason = ""

    def gate(self, block) -> Dict[str, Any]:
        return {
            "wake": self.hit,
            "score": 0.83 if self.hit else 0.12,
            "source": "acoustic",
            "threshold": 0.5,
            "timestamp": time.time(),
        }

    def reset(self) -> None:
        pass


class RecordingSTT:
    def __init__(self, text):
        self.text = text
        self.calls = 0

    def transcribe(self, wav, sample_rate=SR):
        self.calls += 1
        return {"text": self.text, "confidence": 0.91}


class RecordingOrchestrator:
    def __init__(self):
        self.calls: List[str] = []

    async def process_user_query(self, query: str):
        self.calls.append(query)
        return {"task_id": f"tsk_{len(self.calls)}", "status": "COMPLETED", "response": {"message": "orchestrated"}}


# --------------------------------------------------------------------- #
#  Intent matcher: positive cases                                        #
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "text,expected_kind,expected",
    [
        ("open antigravity", "launch", "antigravity"),
        ("launch antigravity", "launch", "antigravity"),
        ("open antigravity ide", "launch", "antigravity_ide"),
        ("open antigravity-ide", "launch", "antigravity_ide"),
        ("start Antigravity.", "launch", "antigravity"),
        ("fire up opencode", "launch", "opencode"),
        ("open open code", "launch", "opencode"),
        ("open Open Code!", "launch", "opencode"),
        ("open chrome", "launch", "chrome"),
        ("open vs code", "launch", "vscode"),
        ("open terminal", "launch", "terminal"),
        ("ask opencode to fix the failing test", "delegate", "opencode"),
        ("tell opencode to refactor daemon.py", "delegate", "opencode"),
        ("tell my opencode to add a hisch test", "delegate", "opencode"),
        ("ask antigravity to audit the boot path", "delegate", "antigravity"),
        ("tell antigravity ide to restructure the sprint", "delegate", "antigravity_ide"),
        ("ask antigravity-ide to plan sprint 4", "delegate", "antigravity_ide"),
        ("run opencode in D:\\jarvis", "opencode_in", "opencode_in"),
    ],
)
def test_intent_matcher_positive(text, expected_kind, expected):
    intent = match_app_intent(text)
    assert intent is not None, f"no intent matched for {text!r}"
    assert intent["kind"] == expected_kind
    if expected_kind == "launch":
        assert intent["app"] == expected
    elif expected_kind == "delegate":
        assert intent["agent"] == expected
        assert intent["task"]
    elif expected_kind == "opencode_in":
        assert intent["path"] == "D:\\jarvis"


@pytest.mark.parametrize(
    "text",
    [
        "what is the weather today",
        "system health",
        "open the pod bay doors",
        "ask john to call me",
        "open",
        "",
        "open antigravity now please",
        "tell me a joke",
        "restart the deployment",
    ],
)
def test_intent_matcher_negative(text):
    assert match_app_intent(text) is None


def test_opencode_task_extraction():
    intent = match_app_intent("ask opencode to fix the flaky wake test")
    assert intent["kind"] == "delegate"
    assert intent["task"] == "fix the flaky wake test"


def test_antigravity_task_extraction():
    intent = match_app_intent("tell antigravity to plan sprint 5")
    assert intent["kind"] == "delegate"
    assert intent["agent"] == "antigravity"
    assert intent["task"] == "plan sprint 5"


# --------------------------------------------------------------------- #
#  Launchers with injected spawner (no real process is started)         #
# --------------------------------------------------------------------- #


class SpawnRecorder:
    def __init__(self):
        self.calls = []

    def __call__(self, argv):
        self.calls.append(list(argv))
        return 4242


def test_launch_app_uses_resolved_executable():
    rec = SpawnRecorder()
    result = launch_app("antigravity", spawner=rec)
    assert result["ok"] is True
    assert result["argv"][0].lower().endswith("antigravity.exe")
    assert rec.calls == [result["argv"]]


def test_launch_unknown_app_fails_honestly():
    result = launch_app("definitely_not_a_real_app_zzz")
    assert result["ok"] is False
    assert "not found" in result["error"]


def test_launch_in_console_starts_visible_terminal():
    rec = SpawnRecorder()
    result = launch_in_console("opencode", args=["D:\\jarvis"], spawner=rec)
    assert result["ok"] is True
    argv = result["argv"]
    assert argv[0].lower().endswith("cmd")
    joined = " ".join(argv)
    assert "start" in joined and "opencode" in joined


def test_opencode_delegate_builds_headless_invocation():
    rec = SpawnRecorder()
    result = opencode_delegate("fix the flaky test", workdir="D:\\jarvis", auto_approve=True, spawner=rec)
    assert result["ok"] is True
    assert result["log"].endswith(".log")
    assert "opencode" in result["log"].replace("\\", "/") or "opencode" in result["log"].replace("/", "\\")
    joined = " ".join(rec.calls[0])
    assert "run" in joined and "--auto" in joined
    assert "fix the flaky test" in joined
    assert result["auto_approve"] is True


def test_antigravity_delegate_launches_and_preloads(monkeypatch):
    rec = SpawnRecorder()
    monkeypatch.setattr(app_connector, "set_clipboard", lambda text: True)
    result = antigravity_delegate("plan sprint 5", spawner=rec)
    assert result["ok"] is True
    assert result["clipboard"] is True
    assert "Ctrl+V" in result["handoff"]
    assert rec.calls and rec.calls[0][0].lower().endswith("antigravity.exe")


def test_antigravity_project_folder_arg_included():
    rec = SpawnRecorder()
    import os as _os

    launch_app("antigravity", args=[r"D:\jarvis"], spawner=rec)
    assert rec.calls[0][-1] == r"D:\jarvis"


# --------------------------------------------------------------------- #
#  End-to-end: wake -> app intent executes WITHOUT the orchestrator      #
# --------------------------------------------------------------------- #


def test_wake_with_open_command_launches_app_not_orchestrator(tmp_path, monkeypatch):
    import jarvis.hud.state as hud_state

    monkeypatch.setattr(hud_state, "HUD_STATE_PATH", tmp_path / "daemon_state.json")
    launched = {}

    def fake_launch_app(app, args=None, spawner=None):
        launched["app"] = app
        return {"ok": True, "app": app, "pid": 4242}

    monkeypatch.setattr(app_connector, "launch_app", fake_launch_app)

    from jarvis.voice.daemon import VoiceDaemon

    gate = FakeGate(hit=True)
    stt = RecordingSTT("hey jarvis open antigravity")
    orch = RecordingOrchestrator()
    daemon = VoiceDaemon(stt=stt, orchestrator=orch, speak_replies=False, gate=gate)
    daemon.state = "LISTENING_FOR_WAKE"

    feed_utterance(daemon)

    assert launched == {"app": "antigravity"}, "app launcher must be the executor"
    assert orch.calls == [], "orchestrator must not be invoked for app intents"
    assert daemon.command_count == 1
    sources = [e.get("source") for e in daemon.evidence_log]
    assert "voice_daemon.app_task" in sources
    assert daemon.last_reply == "Opened antigravity."


def test_wake_with_tell_delegate_opencode(tmp_path, monkeypatch):
    import jarvis.hud.state as hud_state

    monkeypatch.setattr(hud_state, "HUD_STATE_PATH", tmp_path / "daemon_state.json")
    delegated = {}

    def fake_delegate(task, workdir=None, auto_approve=True, spawner=None):
        delegated.update({"task": task, "auto_approve": auto_approve})
        return {"ok": True, "pid": 7777, "log": str(tmp_path / "oc.log")}

    monkeypatch.setattr(app_connector, "opencode_delegate", fake_delegate)

    from jarvis.voice.daemon import VoiceDaemon

    gate = FakeGate(hit=True)
    stt = RecordingSTT("hey jarvis tell opencode to fix the flaky test")
    orch = RecordingOrchestrator()
    daemon = VoiceDaemon(stt=stt, orchestrator=orch, speak_replies=False, gate=gate)
    daemon.state = "LISTENING_FOR_WAKE"

    feed_utterance(daemon)

    assert delegated["task"] == "fix the flaky test"
    assert delegated["auto_approve"] is True
    assert orch.calls == []
    assert daemon.last_reply == "OpenCode is on it."


def test_wake_app_intents_off_falls_through_to_orchestrator(tmp_path, monkeypatch):
    import jarvis.hud.state as hud_state

    monkeypatch.setattr(hud_state, "HUD_STATE_PATH", tmp_path / "daemon_state.json")
    monkeypatch.setenv("JARVIS_APP_INTENTS", "off")

    from jarvis.voice.daemon import VoiceDaemon

    gate = FakeGate(hit=True)
    stt = RecordingSTT("hey jarvis open antigravity")
    orch = RecordingOrchestrator()
    daemon = VoiceDaemon(stt=stt, orchestrator=orch, speak_replies=False, gate=gate)
    daemon.state = "LISTENING_FOR_WAKE"

    feed_utterance(daemon)

    assert orch.calls == ["open antigravity"], "env off must restore orchestrator routing"


def test_hud_state_file_written_through_wake_cycle(tmp_path, monkeypatch):
    import jarvis.hud.state as hud_state

    state_file = tmp_path / "daemon_state.json"
    monkeypatch.setattr(hud_state, "HUD_STATE_PATH", state_file)
    monkeypatch.setattr(
        app_connector, "launch_app", lambda app, args=None, spawner=None: {"ok": True, "app": app, "pid": 1}
    )

    from jarvis.voice.daemon import VoiceDaemon

    gate = FakeGate(hit=True)
    stt = RecordingSTT("hey jarvis open antigravity")
    daemon = VoiceDaemon(stt=stt, orchestrator=RecordingOrchestrator(), speak_replies=False, gate=gate)
    daemon.state = "LISTENING_FOR_WAKE"

    feed_utterance(daemon)

    import json

    data = json.loads(state_file.read_text(encoding="utf-8"))
    # final stage of the cycle: wake -> PROCESSING -> SPEAKING -> (timer fires later)
    assert data["state"] == "SPEAKING"
    assert data["wake_count"] == 1
    assert data["last_command"] == "open antigravity"
    assert data["command_count"] == 1
    assert data["ts"] > 0
