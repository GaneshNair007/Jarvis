"""Tests for truthful on-demand workforce and source-grounded research."""

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from jarvis.agents.autonomous_workforce import autonomous_workforce
from jarvis.agents.hackathon_scout import hackathon_scout_swarm
from jarvis.browser.search_wrapper import SearchResult
from jarvis.core.web_recon import web_opportunity_recon
from jarvis.powers.browser_powers import browser_powers
from jarvis.powers.whatsapp_dispatcher import whatsapp_dispatcher
from jarvis.api.server import app


@pytest.fixture
def client():
    return TestClient(app)


def test_workforce_reports_components_not_fake_agent_processes():
    status = autonomous_workforce.get_fleet_status()
    assert status["registered_components"] == 4
    assert status["active_workers"] == 0
    assert status["execution_mode"] == "on_demand_workflow"
    assert status["status"] == "IDLE"
    assert "not a 105-process agent fleet" in status["message"]


@pytest.mark.asyncio
async def test_web_opportunity_recon_returns_live_discovery_metadata_only(monkeypatch):
    monkeypatch.setattr(
        "jarvis.browser.search_wrapper.WebSearchWrapper.search",
        lambda self, query, max_results=5: [
            SearchResult(
                title="Official AI Agents Hackathon",
                url="https://events.example.org/agents",
                snippet="Official event listing and challenge information.",
            )
        ],
    )
    hackathons = await web_opportunity_recon.search_live_hackathons(
        query="AI agents",
        location="India",
        limit=3,
    )
    assert len(hackathons) == 1
    assert hackathons[0]["title"] == "Official AI Agents Hackathon"
    assert hackathons[0]["verification_status"] == "discovery_only"
    assert "deadline" not in hackathons[0]
    assert "prize_pool" not in hackathons[0]
    assert "recommended_problem" not in hackathons[0]


@pytest.mark.asyncio
async def test_web_opportunity_recon_returns_empty_when_search_is_unavailable(monkeypatch):
    monkeypatch.setattr(
        "jarvis.browser.search_wrapper.WebSearchWrapper.search",
        lambda self, query, max_results=5: [],
    )
    assert await web_opportunity_recon.search_live_hackathons(query="AI agents", location="India") == []


def test_research_note_requires_source_page_and_does_not_invent_facts():
    with pytest.raises(ValueError, match="fetched source_page"):
        web_opportunity_recon.generate_problem_statement_md(
            {"title": "Unknown event", "url": "https://events.example.org/"},
            project_name="JARVIS-demo",
        )

    md_text = web_opportunity_recon.generate_problem_statement_md(
        {
            "title": "Official AI Agents Hackathon",
            "url": "https://events.example.org/agents",
            "snippet": "Search result excerpt.",
            "source_page": {
                "url": "https://events.example.org/agents",
                "title": "Official Challenge Page",
                "headings": ["Eligibility", "Submission"],
                "text_excerpt": (
                    "Eligibility: university students. Submit a working prototype through the event portal."
                ),
            },
        },
        project_name="JARVIS-demo",
    )
    assert "# Hackathon Research Notes: Official AI Agents Hackathon" in md_text
    assert "Eligibility: university students." in md_text
    assert "Registration deadline and timezone: **Not yet verified**" in md_text
    assert "RTX 4050" not in md_text
    assert "50-100 micro-tasks" not in md_text


def test_whatsapp_digest_formatting_does_not_assert_delivery():
    sample = [
        {
            "title": "Official AI Agents Hackathon",
            "url": "https://events.example.org/agents",
            "snippet": "Official source page.",
        }
    ]
    digest = whatsapp_dispatcher.format_hackathon_digest(sample, "Ganesh")
    assert "Hey Ganesh" in digest
    assert "Official AI Agents Hackathon" in digest
    assert "https://events.example.org/agents" in digest


@pytest.mark.asyncio
async def test_workforce_pipeline_uses_real_scout_and_does_not_send_or_fake_code(tmp_path, monkeypatch):
    monkeypatch.setattr(
        hackathon_scout_swarm.scout,
        "scan_opportunities",
        AsyncMock(
            return_value=[
                {
                    "title": "Official AI Hackathon",
                    "url": "https://events.example.org/hackathon",
                    "snippet": "Official search listing.",
                    "source": "duckduckgo_html",
                    "verification_status": "discovery_only",
                }
            ]
        ),
    )
    monkeypatch.setattr(
        browser_powers,
        "read_url",
        lambda url: {
            "status": "completed",
            "url": url,
            "title": "Official AI Hackathon",
            "headings": ["Rules", "Eligibility"],
            "text_excerpt": "Official rules: university teams may submit a working prototype.",
        },
    )
    result = await autonomous_workforce.run_hackathon_opportunity_pipeline(
        target_phone="+919324094474",
        location="India",
        candidate_name="Ganesh",
        output_workspace=tmp_path,
    )

    assert result["status"] == "completed"
    assert result["hackathons_found"] == 1
    assert result["pages_fetched"] == 1
    assert result["notification"]["status"] == "not_requested"
    research_path = tmp_path / "official-ai-hackathon" / "HACKATHON_RESEARCH.md"
    assert research_path.exists()
    assert "university teams may submit a working prototype" in research_path.read_text(encoding="utf-8")
    assert not (tmp_path / "app.py").exists()
    assert not (tmp_path / ".github" / "workflows" / "ci.yml").exists()


def test_fastapi_workforce_endpoints_report_actual_catalog_and_search(monkeypatch, client):
    monkeypatch.setattr(
        "jarvis.browser.search_wrapper.WebSearchWrapper.search",
        lambda self, query, max_results=5: [
            SearchResult(
                title="Official AI Hackathon",
                url="https://events.example.org/hackathon",
                snippet="Official listing.",
            )
        ],
    )
    fleet = client.get("/workforce/fleet")
    assert fleet.status_code == 200
    assert fleet.json()["registered_components"] == 4
    assert fleet.json()["active_workers"] == 0

    hackathons = client.get("/workforce/hackathons?location=India&limit=3")
    assert hackathons.status_code == 200
    assert hackathons.json()["status"] == "discovery_only"
    assert hackathons.json()["total"] == 1

    monkeypatch.setattr(
        whatsapp_dispatcher,
        "send_whatsapp_message",
        AsyncMock(return_value={"status": "ready_for_dispatch", "recipient": "+919324094474"}),
    )
    response = client.post(
        "/workforce/whatsapp/send",
        json={"message": "Explicit test message", "phone": "+919324094474"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ready_for_dispatch"
