"""
Unit & Integration Tests for JARVIS Autonomous Multi-Agent Workforce & WhatsApp Dispatch
Verifies:
1. 105-agent fleet roster and division census.
2. Web opportunity perception & hackathon ranking for Ganesh.
3. Problem statement synthesis and AST project scaffolding.
4. WhatsApp digest formatting and multi-channel dispatch to +91 9324094474.
5. End-to-end pipeline execution with Merkle audit verification.
6. FastAPI workforce endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from jarvis.agents.autonomous_workforce import autonomous_workforce
from jarvis.core.web_recon import web_opportunity_recon
from jarvis.powers.whatsapp_dispatcher import whatsapp_dispatcher
from jarvis.security.ten_layer_shield import jarvis_security_suite
from jarvis.api.server import app


@pytest.fixture
def client():
    return TestClient(app)


class TestAutonomousWorkforceAndWhatsApp:
    def test_105_agent_fleet_roster_and_divisions(self):
        """Verifies fleet census of 105 specialized micro-agents across 5 divisions."""
        fleet = autonomous_workforce.get_fleet_status()
        assert fleet["total_agents"] == 105
        divs = fleet["divisions"]
        assert divs["RECONNAISSANCE"] == 20
        assert divs["ANALYSIS"] == 20
        assert divs["SCAFFOLDING"] == 30
        assert divs["DEVOPS"] == 20
        assert divs["DISPATCH"] == 15
        assert fleet["status"] == "ALL_SYSTEMS_OPERATIONAL"

    @pytest.mark.asyncio
    async def test_web_opportunity_recon_hackathon_ranking(self):
        """Verifies hackathon search returns scored, domain-relevant competitions."""
        hackathons = await web_opportunity_recon.search_live_hackathons(
            query="AI agents",
            location="India",
            limit=3,
        )
        assert len(hackathons) >= 2
        top = hackathons[0]
        assert "title" in top
        assert "url" in top
        assert "recommended_problem" in top
        assert top["match_score"] >= 0.85

    def test_problem_statement_synthesis(self):
        """Verifies automated synthesis of submission-grade PROBLEM_STATEMENT.md."""
        hackathon = {
            "title": "Smart India Hackathon 2026",
            "organization": "AICTE",
            "domain": "Autonomous AI Agents",
            "recommended_problem": "Local Multi-Agent Desktop OS",
        }
        md_text = web_opportunity_recon.generate_problem_statement_md(hackathon, "JARVIS-SIH")
        assert "# Problem Statement Analysis & Solution Architecture" in md_text
        assert "Ganesh Nair" in md_text
        assert "10-Layer Zero-Leak Security Shield" in md_text
        assert "RTX 4050" in md_text

    def test_whatsapp_digest_formatting(self):
        """Verifies WhatsApp digest contains Ganesh's greeting, markdown formatting, and action prompts."""
        sample_hackathons = [
            {
                "title": "Smart India Hackathon 2026",
                "location": "India",
                "domain": "AI/ML",
                "prize_pool": "₹1,00,000",
                "deadline": "End of Month",
                "url": "https://sih.gov.in",
                "recommended_problem": "Autonomous Desktop Assistant",
            }
        ]
        digest = whatsapp_dispatcher.format_hackathon_digest(sample_hackathons, "Ganesh")
        assert "Hey Ganesh" in digest
        assert "*JARVIS OPPORTUNITY ALERT*" in digest
        assert "Smart India Hackathon 2026" in digest
        assert "https://sih.gov.in" in digest

    @pytest.mark.asyncio
    async def test_whatsapp_dispatcher_send_and_receipt(self):
        """Verifies WhatsApp message dispatch produces signed receipt and wa.me direct fallback."""
        receipt = await whatsapp_dispatcher.send_whatsapp_message(
            message="Hey Ganesh, test verification alert from JARVIS workforce.",
            phone="+919324094474",
        )
        assert receipt["recipient"] == "+919324094474"
        assert receipt["status"] in ("delivered", "ready_for_dispatch", "queued")
        assert "https://wa.me/919324094474" in receipt["direct_link"]
        assert receipt["message_length"] > 0

    @pytest.mark.asyncio
    async def test_full_autonomous_hackathon_workforce_pipeline(self, tmp_path):
        """Verifies complete end-to-end pipeline: Recon -> Analysis -> Scaffolding -> Dispatch -> Audit."""
        output_dir = tmp_path / "test_hackathon_project"
        result = await autonomous_workforce.run_hackathon_opportunity_pipeline(
            target_phone="+919324094474",
            location="India",
            candidate_name="Ganesh",
            output_workspace=output_dir,
        )

        assert result["status"] == "COMPLETED"
        assert result["candidate_name"] == "Ganesh"
        assert result["target_phone"] == "+919324094474"
        assert result["hackathons_found"] > 0

        # Verify generated filesystem artifacts
        assert (output_dir / "PROBLEM_STATEMENT.md").exists()
        assert (output_dir / "app.py").exists()
        assert (output_dir / ".github" / "workflows" / "ci.yml").exists()

        # Verify WhatsApp dispatch receipt
        wa = result["whatsapp_dispatch"]
        assert wa["recipient"] == "+919324094474"

        # Verify Merkle security audit logged
        assert jarvis_security_suite.layer9_audit.verify_integrity() is True

    def test_fastapi_workforce_endpoints(self, client):
        """Verifies workforce REST API endpoints."""
        # 1. Fleet census
        r1 = client.get("/workforce/fleet")
        assert r1.status_code == 200
        d1 = r1.json()
        assert d1["total_agents"] == 105

        # 2. Hackathons query
        r2 = client.get("/workforce/hackathons?location=India&limit=3")
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["total"] >= 1

        # 3. WhatsApp dispatch endpoint
        r3 = client.post(
            "/workforce/whatsapp/send",
            json={
                "message": "Hey Ganesh, API endpoint dispatch check.",
                "phone": "+919324094474",
            },
        )
        assert r3.status_code == 200
        d3 = r3.json()
        assert d3["recipient"] == "+919324094474"
