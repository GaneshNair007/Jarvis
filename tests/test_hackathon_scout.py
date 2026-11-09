"""
Verification Suite for JARVIS Obscura Browser & Autonomous Hackathon Scout Swarm
"""

import pytest
from pathlib import Path
from jarvis.core.obscura_browser import obscura_browser
from jarvis.core.notifier import opportunity_notifier
from jarvis.agents.hackathon_scout import (
    ScoutAgent,
    AnalystAgent,
    ArchitectAgent,
    DispatcherAgent,
    hackathon_scout_swarm,
)


class TestObscuraAndHackathonScout:
    @pytest.mark.asyncio
    async def test_obscura_browser_search_and_fallback(self):
        """Verifies Obscura search returns structured opportunities with titles, URLs, and snippets."""
        results = await obscura_browser.search_opportunities("AI agent hackathon 2026", limit=4)
        assert len(results) >= 2
        for r in results:
            assert "title" in r
            assert "url" in r
            assert "snippet" in r

    def test_analyst_agent_scoring(self):
        """Verifies analyst agent prioritizes high-relevance AI/Systems opportunities."""
        raw = [
            {
                "title": "Global AI Autonomous Agent Challenge",
                "snippet": "Build multi-agent Python FastAPI pipelines with PyTorch GPU acceleration.",
            },
            {"title": "Beginner HTML Static Webpage Design Contest", "snippet": "Create static CSS stylesheets."},
        ]
        analyst = AnalystAgent()
        evaluated = analyst.evaluate_opportunities(raw)
        assert evaluated[0]["title"] == "Global AI Autonomous Agent Challenge"
        assert evaluated[0]["relevance_score"] > evaluated[1]["relevance_score"]
        assert evaluated[0]["feasibility"] == "HIGH"

    def test_architect_agent_scaffolding(self, tmp_path):
        """Verifies architect agent generates PROBLEM_STATEMENT.md and scaffolded repo files."""
        architect = ArchitectAgent(workspace_root=tmp_path)
        opp = {
            "title": "Autonomous Desktop AI Assistant",
            "url": "https://devpost.com/software/jarvis",
            "mode": "Remote / India",
            "relevance_score": 96,
        }
        proj_dir = architect.scaffold_top_opportunity(opp)
        assert proj_dir.exists()
        assert (proj_dir / "PROBLEM_STATEMENT.md").exists()
        assert (proj_dir / "README.md").exists()
        assert (proj_dir / "requirements.txt").exists()
        assert (proj_dir / "main.py").exists()

        problem_content = (proj_dir / "PROBLEM_STATEMENT.md").read_text(encoding="utf-8")
        assert "Autonomous Desktop AI Assistant" in problem_content
        assert "RTX 4050" in problem_content

    @pytest.mark.asyncio
    async def test_notifier_whatsapp_formatting_and_dispatch(self):
        """Verifies WhatsApp formatter creates structured executive message and delivers receipt."""
        opps = [
            {
                "title": "Google Summer of Code 2026",
                "deadline": "April 2026",
                "mode": "Remote",
                "tags": ["Open Source", "Google", "Python"],
                "url": "https://summerofcode.withgoogle.com",
            }
        ]
        msg = opportunity_notifier.format_whatsapp_hackathon_digest(opps, "Ganesh", "India")
        assert "Hey Ganesh" in msg
        assert "Google Summer of Code 2026" in msg
        assert "+91 9324094474" in opportunity_notifier.DEFAULT_TARGET_PHONE

        dispatch_res = await opportunity_notifier.send_whatsapp_message(
            phone_number="+91 9324094474",
            message=msg,
        )
        assert dispatch_res["status"] in ("sent", "simulated_success")
        assert dispatch_res["recipient"] == "+919324094474"

    @pytest.mark.asyncio
    async def test_full_hackathon_swarm_cycle(self, tmp_path):
        """Verifies end-to-end execution of the 4-agent swarm."""
        swarm = hackathon_scout_swarm
        swarm.architect.workspace_root = tmp_path
        res = await swarm.execute_autonomous_scout_cycle(
            target_phone="+91 9324094474",
            search_query="AI Hackathons 2026",
        )
        assert res["status"] == "success"
        assert res["total_discovered"] > 0
        assert len(res["opportunities"]) > 0
        assert "notification" in res
