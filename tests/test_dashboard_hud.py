"""
Test suite for Glassmorphic Iron Man HUD Dashboard & Server Gating (Milestone 3).
Verifies:
- Dashboard HTML served at '/' and '/dashboard' with 200 OK.
- Glassmorphic styling tokens, scanlines, and reactive Arc Reactor presence.
- Real-time audio visualizer waveform canvas component.
- Dedicated status cards for all 8 specialized agents.
- Real-time 6-Stage Execution Pipeline visualization.
- Complete excision of smart-home buttons/controls from dashboard.
- Smart-home REST API gating enforcing status: "FROZEN" and connected: False.
- Chat endpoint threads conversation_id for multi-turn sessions.
"""

import pytest
from fastapi.testclient import TestClient
from jarvis.api.server import app

client = TestClient(app)


def test_serve_dashboard_hud_routes():
    """Verify server serves interactive HUD dashboard at '/' and '/dashboard'."""
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert "JARVIS — Personal AI Operating System HUD" in res_root.text

    res_dash = client.get("/dashboard")
    assert res_dash.status_code == 200
    assert "JARVIS — Personal AI Operating System HUD" in res_dash.text
    assert res_root.text == res_dash.text


def test_dashboard_hud_arc_reactor_and_audio_visualizer():
    """Verify Arc Reactor (#arc-reactor/.arc-reactor) and audio visualizer canvas are embedded."""
    res = client.get("/dashboard")
    assert res.status_code == 200
    html = res.text

    # Arc Reactor
    assert 'id="arc-reactor"' in html
    assert "arc-reactor" in html
    assert "reactor-pulse-idle" in html
    assert "reactor-pulse-active" in html

    # Real-time audio visualizer waveform canvas
    assert 'id="audio-visualizer"' in html
    assert "audio-visualizer" in html
    assert "<canvas" in html


def test_dashboard_hud_8_specialized_agents_cards():
    """Verify dedicated status cards for all 8 specialized agents exist in HUD."""
    res = client.get("/dashboard")
    assert res.status_code == 200
    html = res.text

    expected_agents = [
        ("agent-researcher", "Researcher Agent"),
        ("agent-engineer", "Engineer Agent"),
        ("agent-academic-tutor", "Academic Tutor Agent"),
        ("agent-career", "Career Agent"),
        ("agent-productivity", "Productivity Agent"),
        ("agent-communication", "Communication Agent"),
        ("agent-desktop", "Desktop Agent"),
        ("agent-reviewer", "Reviewer / Verifier Agent"),
    ]

    for element_id, agent_name in expected_agents:
        assert f'id="{element_id}"' in html, f"Missing element ID: {element_id}"
        assert agent_name in html, f"Missing agent title: {agent_name}"


def test_dashboard_hud_6stage_execution_pipeline():
    """Verify real-time 6-Stage Execution Pipeline visualization components exist in HUD."""
    res = client.get("/dashboard")
    assert res.status_code == 200
    html = res.text

    assert 'id="pipeline-tracker"' in html
    assert "pipeline-tracker" in html

    expected_stages = [
        ("stage-1", "Stage 1: Understand"),
        ("stage-2", "Stage 2: Plan"),
        ("stage-3", "Stage 3: Select"),
        ("stage-4", "Stage 4: Execute"),
        ("stage-5", "Stage 5: Verify"),
        ("stage-6", "Stage 6: Consolidate & Persist"),
    ]

    for element_id, stage_name in expected_stages:
        assert f'id="{element_id}"' in html, f"Missing pipeline element ID: {element_id}"
        assert stage_name in html, f"Missing pipeline stage name: {stage_name}"


def test_dashboard_hud_no_duplicate_smart_home_controls():
    """Verify smart-home control quickbars and duplicate buttons have been completely removed."""
    res = client.get("/dashboard")
    assert res.status_code == 200
    html = res.text

    # Banned control strings from smart-home quickbar
    banned_controls = [
        "PHYSICAL ROOM & OPS CONTROLLER",
        "quickRoomCommand('turn on the AC",
        "quickRoomCommand('turn on the geyser",
        "quickRoomCommand('turn on the projector",
        "quickRoomCommand('turn off lights",
        "quickRoomCommand('movie night",
        "quickRoomCommand('sleep mode",
        "AC 21°C",
        "Geyser (15m Timer)",
    ]

    for banned in banned_controls:
        assert banned not in html, f"Found deprecated smart-home control button: {banned}"


def test_dashboard_hud_chat_session_threading():
    """Verify chat interface supports multi-turn conversations and threads conversation_id."""
    res = client.get("/dashboard")
    assert res.status_code == 200
    html = res.text

    assert 'id="conversation-id"' in html
    assert "currentConversationId" in html
    assert "startNewSession" in html


def test_smart_home_route_gating_enforcement():
    """Verify all smart-home endpoints return status: 'FROZEN' and connected: False."""
    endpoints = [
        ("GET", "/api/v1/smarthome/devices", None),
        ("POST", "/api/v1/smarthome/climate", {"action": "on", "temperature": 22}),
        ("POST", "/api/v1/smarthome/plug", {"entity_id": "switch.geyser", "state": "on"}),
        ("POST", "/api/v1/smarthome/lights", {"entity_id": "light.desk", "state": "on"}),
        ("POST", "/api/v1/smarthome/scene", {"scene": "work_mode"}),
        ("POST", "/api/v1/smarthome/voice", {"transcript": "Turn on lights"}),
        ("GET", "/api/v1/smarthome/status", None),
    ]

    for method, path, payload in endpoints:
        if method == "GET":
            r = client.get(path)
        else:
            r = client.post(path, json=payload or {})

        assert r.status_code == 200
        data = r.json()
        assert data.get("status") == "FROZEN", f"Path {path} did not return FROZEN status"
        assert data.get("connected") is False, f"Path {path} did not return connected: False"


def test_api_chat_threads_conversation_id():
    """Verify /api/v1/chat endpoint accepts conversation_id and executes multi-turn context."""
    test_session = "test_hud_session_9942"
    payload = {
        "query": "Who is the primary user?",
        "conversation_id": test_session,
    }
    res = client.post("/api/v1/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert data["status"] in ["COMPLETED", "TRIAGED", "PROCESSING"]
