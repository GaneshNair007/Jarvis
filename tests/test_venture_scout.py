"""
Unit Tests for JARVIS Venture Scout & AI Business Idea Matching Engine
Verifies:
  1. Loading of all 200 curated AI Business Ideas (Ayman William catalog).
  2. Idea filtering and keyword search.
  3. Fit scoring tailored to Ganesh's RTX 4050 compute and Python/agentic stack.
  4. 30-Day launch blueprint synthesis.
"""

import pytest
from jarvis.agents.venture_scout import venture_scout, VentureScout, BusinessIdea


class TestVentureScout:
    def test_200_business_ideas_loaded(self):
        """Verifies complete ingestion of all 200 business ideas from Ayman William catalog."""
        assert len(venture_scout.ideas) == 200
        first_idea = venture_scout.ideas[0]
        assert first_idea.number == 1
        assert first_idea.domain != ""
        assert first_idea.title != ""
        assert first_idea.target_buyer != ""

    def test_search_ideas_by_domain_and_query(self):
        """Verifies filtering by domain and keyword."""
        results = venture_scout.search_ideas(query="content", limit=5)
        assert len(results) > 0
        assert any("content" in f"{i.title} {i.domain}".lower() for i in results)

    def test_match_ideas_for_ganesh_profile(self):
        """Verifies fit scoring boosts ideas matching RTX 4050 hardware and Python stack."""
        matches = venture_scout.match_ideas_for_profile(
            skills=["python", "fastapi", "voice", "local llm"],
            has_gpu=True,
            limit=5,
        )
        assert len(matches) == 5
        top = matches[0]
        assert top.fit_score >= 0.70
        assert top.fit_score <= 1.0

    def test_generate_launch_blueprint(self):
        """Verifies generation of structured 30-day launch blueprint."""
        first_idea = venture_scout.ideas[0]
        blueprint = venture_scout.generate_launch_blueprint(first_idea.idea_id)
        assert "title" in blueprint
        assert "milestones" in blueprint
        assert len(blueprint["milestones"]) >= 4
        assert "technical_stack_recommendation" in blueprint
        assert "target_buyer" in blueprint

    def test_ventures_api_endpoints(self):
        """Verifies FastAPI REST endpoints for business idea scouting."""
        from fastapi.testclient import TestClient
        from jarvis.api.server import app
        client = TestClient(app)

        res = client.get("/ventures/ideas?limit=5")
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 5
        assert len(data["ideas"]) == 5

        match_res = client.get("/ventures/match?limit=3")
        assert match_res.status_code == 200
        match_data = match_res.json()
        assert match_data["total_matched"] == 3

    def test_fastapi_ventures_endpoints(self):
        """Verifies REST endpoints for ideas, match, and blueprints."""
        from fastapi.testclient import TestClient
        from jarvis.api.server import app

        c = TestClient(app)
        # 1. GET /ventures/ideas
        r1 = c.get("/ventures/ideas?limit=5")
        assert r1.status_code == 200
        d1 = r1.json()
        assert d1["total"] == 5
        assert len(d1["ideas"]) == 5

        # 2. GET /ventures/match
        r2 = c.get("/ventures/match?limit=3")
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["total_matched"] == 3
        assert len(d2["top_opportunities"]) == 3

        # 3. GET /ventures/blueprint/IDEA-001
        r3 = c.get("/ventures/blueprint/IDEA-001")
        assert r3.status_code == 200
        d3 = r3.json()
        assert d3["idea_id"] == "IDEA-001"
        assert len(d3["30_day_milestone_plan"]) == 4
