"""
Empirical Adversarial Challenge Suite for Milestone 3 (HUD & Telemetry & Process Stability).
Written by challenger_m3_2.
"""

import hashlib
from html.parser import HTMLParser
import pytest
from fastapi.testclient import TestClient
from jarvis.api.server import app

client = TestClient(app)


class DashboardHTMLAnalyzer(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = {}
        self.classes = {}
        self.canvases = {}
        self.svgs = []
        self.buttons = []

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        tid = attr_dict.get("id")
        tcls = attr_dict.get("class", "")
        if tid:
            self.ids[tid] = {"tag": tag, "attrs": attr_dict}
        if tag == "canvas":
            self.canvases[tid] = attr_dict
        if tag == "svg":
            self.svgs.append(attr_dict)
        if tag == "button":
            self.buttons.append(attr_dict)
        if tcls:
            for c in tcls.split():
                self.classes.setdefault(c, []).append({"tag": tag, "id": tid})


@pytest.fixture(scope="module")
def html_dashboard():
    with open("dashboard/index.html", "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="module")
def html_jarvis_dashboard():
    with open("jarvis/dashboard/index.html", "r", encoding="utf-8") as f:
        return f.read()


def test_file_parity_and_sync(html_dashboard, html_jarvis_dashboard):
    """Verify dashboard/index.html and jarvis/dashboard/index.html are bit-for-bit identical."""
    h1 = hashlib.sha256(html_dashboard.encode("utf-8")).hexdigest()
    h2 = hashlib.sha256(html_jarvis_dashboard.encode("utf-8")).hexdigest()
    assert h1 == h2, f"Dashboard files are not synchronized! {h1} != {h2}"


def test_arc_reactor_and_audio_visualizer(html_dashboard):
    """Verify Arc Reactor and audio visualizer canvas."""
    analyzer = DashboardHTMLAnalyzer()
    analyzer.feed(html_dashboard)

    # 1. Arc Reactor element & classes
    assert "arc-reactor" in analyzer.ids, "Missing #arc-reactor element"
    assert "arc-reactor" in analyzer.classes, "Missing .arc-reactor CSS class"
    assert "reactor-pulse-idle" in html_dashboard
    assert "reactor-pulse-active" in html_dashboard
    assert "reactor-rotate" in html_dashboard

    # 2. Audio Visualizer canvas & animation loop
    assert "audio-visualizer" in analyzer.canvases, "Missing <canvas id='audio-visualizer'>"
    assert "renderWaveform" in html_dashboard, "Missing renderWaveform loop"
    assert "requestAnimationFrame" in html_dashboard, "Missing requestAnimationFrame"


def test_all_8_specialized_agent_cards_present(html_dashboard):
    """Verify all 8 specialized agent cards exist with their respective IDs."""
    analyzer = DashboardHTMLAnalyzer()
    analyzer.feed(html_dashboard)

    expected_agents = [
        "agent-researcher",
        "agent-engineer",
        "agent-academic-tutor",
        "agent-career",
        "agent-productivity",
        "agent-communication",
        "agent-desktop",
        "agent-reviewer",
    ]

    for agent_id in expected_agents:
        assert agent_id in analyzer.ids, f"Missing specialized agent card: #{agent_id}"


def test_pipeline_stages_and_tracker(html_dashboard):
    """
    Verify 6-Stage Execution Pipeline tracker and stages.
    Notes discrepancy between #stage-X vs #pipeline-stage-X.
    """
    analyzer = DashboardHTMLAnalyzer()
    analyzer.feed(html_dashboard)

    assert "pipeline-tracker" in analyzer.ids, "Missing #pipeline-tracker"
    assert "pipeline-status-badge" in analyzer.ids, "Missing #pipeline-status-badge"

    # Verify stages 1 to 6 exist
    stage_ids = [f"stage-{i}" for i in range(1, 7)]
    for sid in stage_ids:
        assert sid in analyzer.ids, f"Missing pipeline stage ID: #{sid}"


def test_smart_home_controls_excised(html_dashboard):
    """Verify smart-home control quickbars and duplicate buttons are completely removed."""
    banned_controls = [
        "PHYSICAL ROOM & OPS CONTROLLER",
        "quickRoomCommand",
        "turn on the AC",
        "turn on the geyser",
        "turn on the projector",
        "turn off lights",
        "movie night",
        "sleep mode",
        "AC 21°C",
        "Geyser (15m Timer)",
    ]
    for banned in banned_controls:
        assert banned not in html_dashboard, f"Found banned smart-home control: {banned}"


def test_chat_console_session_threading(html_dashboard):
    """Verify chat console multi-turn threading and session reset."""
    analyzer = DashboardHTMLAnalyzer()
    analyzer.feed(html_dashboard)

    assert "conversation-id" in analyzer.ids, "Missing #conversation-id element"
    assert "currentConversationId" in html_dashboard, "Missing currentConversationId variable"
    assert "startNewSession" in html_dashboard, "Missing startNewSession function"
    assert "conversation_id: currentConversationId" in html_dashboard, "Chat payload does not thread conversation_id"


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/v1/smarthome/devices"),
        ("POST", "/api/v1/smarthome/climate"),
        ("PUT", "/api/v1/smarthome/lights"),
        ("DELETE", "/api/v1/smarthome/device/1"),
        ("GET", "/smarthome"),
        ("POST", "/smarthome/command"),
        ("GET", "/smart-home/status"),
        ("POST", "/api/v1/smart_home/toggle"),
    ],
)
def test_smart_home_middleware_gating_adversarial(method, path):
    """Stress-test middleware across methods and paths."""
    if method == "GET":
        resp = client.get(path)
    elif method == "POST":
        resp = client.post(path, json={"sample": "data"})
    elif method == "PUT":
        resp = client.put(path, json={"state": "on"})
    elif method == "DELETE":
        resp = client.delete(path)
    else:
        resp = client.request(method, path)

    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "FROZEN"
    assert data.get("connected") is False


def test_chat_multiturn_threading_adversarial():
    """Adversarially test /api/v1/chat with multi-turn conversation_id threading."""
    session_id = "test_adversarial_turn_session_7781"

    # Turn 1
    resp1 = client.post(
        "/api/v1/chat",
        json={"query": "My favorite framework is PyTorch.", "conversation_id": session_id},
    )
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["status"] in ["COMPLETED", "TRIAGED", "PROCESSING"]

    # Turn 2: Unicode & special chars in conversation_id
    unicode_session = "sess_⚡_iron_man_999_日本語"
    resp2 = client.post(
        "/api/v1/chat",
        json={"query": "System telemetry status check", "conversation_id": unicode_session},
    )
    assert resp2.status_code == 200

    # Turn 3: Default fallback when conversation_id is omitted
    resp3 = client.post(
        "/api/v1/chat",
        json={"query": "Check local memory"},
    )
    assert resp3.status_code == 200
