"""Tests for live-only hackathon discovery and source-grounded research notes."""

from unittest.mock import AsyncMock

import pytest

from jarvis.agents.hackathon_scout import AnalystAgent, ArchitectAgent, HackathonScoutSwarm
from jarvis.browser.search_wrapper import SearchResult
from jarvis.core.obscura_browser import obscura_browser
from jarvis.core.notifier import opportunity_notifier
from jarvis.powers.browser_powers import browser_powers


@pytest.mark.asyncio
async def test_obscura_browser_uses_live_search_results_only(monkeypatch):
    monkeypatch.setattr(
        "jarvis.browser.search_wrapper.WebSearchWrapper.search",
        lambda self, query, max_results=5: [
            SearchResult(
                title="Official AI Hackathon",
                url="https://events.example.org/hackathon",
                snippet="Official event listing.",
            )
        ],
    )

    results = await obscura_browser.search_opportunities("AI hackathon", limit=4)

    assert len(results) == 1
    assert results[0]["title"] == "Official AI Hackathon"
    assert results[0]["source"] == "duckduckgo_html"
    assert results[0]["verification_status"] == "discovery_only"


@pytest.mark.asyncio
async def test_obscura_browser_does_not_fabricate_offline_fallback(monkeypatch):
    monkeypatch.setattr(
        "jarvis.browser.search_wrapper.WebSearchWrapper.search",
        lambda self, query, max_results=5: [],
    )
    results = await obscura_browser.search_opportunities("AI hackathon India", limit=5)
    assert results == []


def test_analyst_agent_does_not_invent_scores_or_technology():
    raw = [
        {
            "title": "Global AI Autonomous Agent Challenge",
            "url": "https://events.example.org/agents",
            "snippet": "Build multi-agent Python pipelines.",
        }
    ]

    evaluated = AnalystAgent().evaluate_opportunities(raw)

    assert len(evaluated) == 1
    assert evaluated[0]["analysis_status"] == "not_ranked"
    assert evaluated[0]["relevance_score"] is None
    assert evaluated[0]["recommended_tech"] == []


def test_architect_requires_fetched_page_before_creating_notes(tmp_path):
    architect = ArchitectAgent(workspace_root=tmp_path)
    with pytest.raises(ValueError, match="fetched source page"):
        architect.scaffold_top_opportunity(
            {
                "title": "Autonomous Desktop AI Assistant",
                "url": "https://events.example.org/assistant",
                "snippet": "A search result only.",
            }
        )
    assert list(tmp_path.iterdir()) == []


def test_architect_writes_source_grounded_research_not_a_fake_app(tmp_path):
    architect = ArchitectAgent(workspace_root=tmp_path)
    opportunity = {
        "title": "Autonomous Desktop AI Assistant",
        "url": "https://events.example.org/assistant",
        "snippet": "Official challenge page.",
        "source_page": {
            "status": "completed",
            "url": "https://events.example.org/assistant",
            "title": "Official Challenge",
            "headings": ["Eligibility", "Submission"],
            "text_excerpt": "Eligibility: university students. Submission: working prototype and demo.",
        },
    }

    research_path = architect.scaffold_top_opportunity(opportunity)
    project_dir = research_path.parent

    assert research_path.name == "HACKATHON_RESEARCH.md"
    content = research_path.read_text(encoding="utf-8")
    assert "Eligibility: university students." in content
    assert "Registration deadline and timezone: **Not yet verified**" in content
    assert not (project_dir / "main.py").exists()
    assert not (project_dir / "requirements.txt").exists()


@pytest.mark.asyncio
async def test_full_scout_cycle_fetches_page_and_does_not_send_by_default(tmp_path, monkeypatch):
    swarm = HackathonScoutSwarm()
    swarm.architect.workspace_root = tmp_path
    monkeypatch.setattr(
        swarm.scout,
        "scan_opportunities",
        AsyncMock(
            return_value=[
                {
                    "title": "Official AI Hackathon",
                    "url": "https://events.example.org/hackathon",
                    "snippet": "Search discovery snippet.",
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
            "text_excerpt": "Official rules: teams of two to four. Final submission by the published portal deadline.",
        },
    )
    send = AsyncMock(side_effect=AssertionError("No notification was requested"))
    monkeypatch.setattr(swarm.dispatcher, "notify_user", send)

    result = await swarm.execute_autonomous_scout_cycle(
        search_query="AI hackathons",
        send_notification=False,
    )

    assert result["status"] == "completed"
    assert result["total_discovered"] == 1
    assert result["pages_fetched"] == 1
    assert len(result["research_notes"]) == 1
    assert result["notification"]["status"] == "not_requested"
    assert send.await_count == 0
    assert (tmp_path / "official-ai-hackathon" / "HACKATHON_RESEARCH.md").exists()


@pytest.mark.asyncio
async def test_scout_cycle_fails_when_source_page_cannot_be_fetched(tmp_path, monkeypatch):
    swarm = HackathonScoutSwarm()
    swarm.architect.workspace_root = tmp_path
    monkeypatch.setattr(
        swarm.scout,
        "scan_opportunities",
        AsyncMock(
            return_value=[
                {
                    "title": "Unavailable event",
                    "url": "https://events.example.org/unavailable",
                    "snippet": "Search result only.",
                }
            ]
        ),
    )
    monkeypatch.setattr(
        browser_powers,
        "read_url",
        lambda url: {"status": "unavailable", "url": url, "text_excerpt": ""},
    )

    result = await swarm.execute_autonomous_scout_cycle(search_query="AI hackathons")

    assert result["status"] == "unavailable"
    assert result["pages_fetched"] == 0
    assert result["research_notes"] == []
    assert not list(tmp_path.iterdir())
