"""Iron Man HUD state bridge tests (pure JSON — no GUI required)."""

import json
import time

import pytest

import jarvis.hud.state as hud_state
from jarvis.hud.state import (
    read_hud_state,
    write_hud_state,
    should_show,
    is_stale,
    HUD_STATE_PATH,
)


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    path = tmp_path / "daemon_state.json"
    monkeypatch.setattr(hud_state, "HUD_STATE_PATH", path)
    yield path


def test_roundtrip():
    write_hud_state({"state": "PROCESSING", "source": "test", "wake_count": 3})
    data = read_hud_state()
    assert data["state"] == "PROCESSING"
    assert data["source"] == "test"
    assert data["wake_count"] == 3
    assert "ts" in data


def test_read_missing_returns_empty():
    assert read_hud_state() == {}


def test_read_invalid_json_returns_empty(isolated_state):
    isolated_state.write_text("{not json", encoding="utf-8")
    assert read_hud_state() == {}


def test_read_stale_returns_empty(isolated_state):
    isolated_state.write_text(
        json.dumps({"state": "PROCESSING", "ts": time.time() - 120}),
        encoding="utf-8",
    )
    assert read_hud_state() == {}


def test_is_stale_helper():
    assert is_stale({"ts": time.time()}) is False
    assert is_stale({"ts": time.time() - 999}) is True
    assert is_stale({}) is True
    assert is_stale({"ts": "garbage"}) is True


@pytest.mark.parametrize(
    "state,expected",
    [
        ("LISTENING_FOR_WAKE", False),
        ("IDLE", False),
        ("CAPTURING_COMMAND", True),
        ("PROCESSING", True),
        ("SPEAKING", True),
        ("", False),
        (None, False),
    ],
)
def test_should_show(state, expected):
    assert should_show(state) is expected
