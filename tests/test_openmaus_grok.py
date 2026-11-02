"""
Comprehensive Empirical Verification Suite for OpenMausBot & Grok Bot Engine.
Verifies multi-bot roster, Grok persona modes, loopback event streaming,
inline permission broker, and FastAPI endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from jarvis.api.server import app
from jarvis.core.openmaus_grok import (
    OpenMausGrokHarness,
    OpenMausAgentRoster,
    OpenMausPermissionBroker,
    GrokMode,
    GROK_PERSONAS,
    openmaus_harness,
)


@pytest.fixture
def client():
    return TestClient(app)


class TestOpenMausGrokBot:

    def test_grok_persona_modes_exist_and_distinct(self):
        """Verifies that all 4 Grok modes have distinct, character-rich system instructions."""
        assert len(GROK_PERSONAS) == 4
        assert GrokMode.STANDARD in GROK_PERSONAS
        assert GrokMode.FUN in GROK_PERSONAS
        assert GrokMode.THINK in GROK_PERSONAS
        assert GrokMode.CODE in GROK_PERSONAS

        # Check Hitchhiker / Grok tone
        assert "Hitchhiker" in GROK_PERSONAS[GrokMode.STANDARD]
        assert "Banter" in GROK_PERSONAS[GrokMode.FUN]
        assert "Reasoning" in GROK_PERSONAS[GrokMode.THINK]
        assert "Architect" in GROK_PERSONAS[GrokMode.CODE]

    def test_agent_roster_initialization(self):
        """Verifies the 5 core bots inspired by OpenMausBot's sidebar."""
        roster = OpenMausAgentRoster()
        bots = roster.list_bots()
        assert len(bots) >= 5

        bot_ids = [b["bot_id"] for b in bots]
        assert "grok" in bot_ids
        assert "code_bot" in bot_ids
        assert "research_bot" in bot_ids
        assert "sys_bot" in bot_ids
        assert "reflex_bot" in bot_ids

        # Check Grok profile
        grok = roster.get_bot("grok")
        assert grok is not None
        assert grok.name == "Grok"
        assert grok.avatar == "⚡"
        assert "web_search" in grok.allowed_tools

    def test_permission_broker_intercepts_privileged_operations(self):
        """Verifies that safe actions pass while privileged actions trigger permission cards."""
        broker = OpenMausPermissionBroker()

        # 1. Safe action passes immediately
        safe_approved, safe_id = broker.inspect_action("read_document", "readme.txt", agent_id="grok")
        assert safe_approved is True
        assert safe_id is None

        # 2. Privileged action intercepted
        priv_approved, priv_id = broker.inspect_action("execute_shell", "rm -rf /", agent_id="sys_bot")
        assert priv_approved is False
        assert priv_id is not None
        assert priv_id.startswith("perm_")

        # Check pending list
        pending = broker.get_pending()
        assert any(p["decision_id"] == priv_id for p in pending)

        # 3. Resolve approval
        resolved = broker.resolve(priv_id, approved=True)
        assert resolved is True
        assert broker._pending_decisions[priv_id]["status"] == "APPROVED"

    @pytest.mark.asyncio
    async def test_harness_chat_generates_normalized_events_and_response(self):
        """Verifies end-to-end chat turn through OpenMausGrokHarness."""
        harness = OpenMausGrokHarness()
        emitted_events = []
        harness.add_event_listener(lambda e: emitted_events.append(e))

        res = await harness.chat(
            prompt="Hello Grok, explain quantum superposition in one sentence.",
            bot_id="grok",
            mode=GrokMode.FUN,
            channel="#general",
        )

        assert res["status"] == "success"
        assert res["bot_id"] == "grok"
        assert res["bot_name"] == "Grok"
        assert res["mode"] == "fun"
        assert len(res["reply"]) > 0

        # Check normalized event stream (thought and agent_message)
        types = [e.event_type for e in emitted_events]
        assert "thought" in types
        assert "agent_message" in types

    def test_fastapi_grok_endpoints(self, client):
        """Verifies all FastAPI routes for Grok Bot and OpenMausBot roster."""
        # 1. GET /api/v1/grok/roster
        resp_roster = client.get("/api/v1/grok/roster")
        assert resp_roster.status_code == 200
        roster_data = resp_roster.json()
        assert roster_data["total_bots"] >= 5

        # 2. GET /api/v1/grok/channels
        resp_ch = client.get("/api/v1/grok/channels")
        assert resp_ch.status_code == 200
        ch_data = resp_ch.json()
        assert "#general" in ch_data["channels"]

        # 3. POST /api/v1/grok/chat
        resp_chat = client.post(
            "/api/v1/grok/chat",
            json={
                "message": "Give me a quick status update on the matrix.",
                "bot_id": "grok",
                "mode": "standard",
                "channel": "#general",
            },
        )
        assert resp_chat.status_code == 200
        chat_data = resp_chat.json()
        assert chat_data["status"] == "success"
        assert "reply" in chat_data

        # 4. GET /api/v1/grok/events
        resp_ev = client.get("/api/v1/grok/events?limit=10")
        assert resp_ev.status_code == 200
        ev_data = resp_ev.json()
        assert ev_data["total_events"] > 0
