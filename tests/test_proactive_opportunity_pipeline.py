"""
Comprehensive Test Suite for Proactive Daily Connection & Autonomous Opportunity Pipeline
==========================================================================================
Verifies:
  1. Morning & Midday proactive briefings with spoken voice greetings & approval tokens.
  2. Multi-LLM frontier research & Hydra dynamic failover across Claude, GPT-4o, DeepSeek, Gemini.
  3. Autonomous repository creation, AST code development, test passing verification & git commit.
  4. Autonomous form filling & Playwright DOM script generation mapped to Ganesh's canonical profile.
  5. Full end-to-end single-tap approval execution loop.
  6. REST API endpoints for opportunities and approvals.
"""

import pytest
import shutil
from pathlib import Path
from fastapi.testclient import TestClient

from jarvis.api.server import app
from jarvis.core.daily_connector import daily_opportunity_connector
from jarvis.core.multi_llm_researcher import multi_llm_researcher
from jarvis.core.autonomous_repo_builder import autonomous_repo_builder
from jarvis.core.autonomous_applier import autonomous_applier


@pytest.fixture
def test_client():
    return TestClient(app)


@pytest.mark.asyncio
async def test_morning_career_briefing_generation():
    """Verifies 08:00 morning briefing formats polite voice greeting and approval gate."""
    opp, trust_res = await daily_opportunity_connector.generate_morning_career_briefing(
        voice_speak=False,
        dispatch_whatsapp=False,
        dispatch_switch=False,
    )
    assert opp.opp_type == "job"
    assert "Hello sir" in opp.spoken_greeting
    assert "LinkedIn" in opp.spoken_greeting
    assert "Ganesh" in opp.whatsapp_text
    assert opp.status == "PENDING_APPROVAL"
    assert opp.approval_token is not None
    assert trust_res.success is True
    assert len(trust_res.evidence) >= 1
    assert trust_res.evidence[0].source == "daily_connector"


@pytest.mark.asyncio
async def test_midday_hackathon_briefing_generation():
    """Verifies 12:00 midday briefing formats hackathon reconnaissance and action instructions."""
    opp, trust_res = await daily_opportunity_connector.generate_midday_hackathon_briefing(
        voice_speak=False,
        dispatch_whatsapp=False,
        dispatch_switch=False,
    )
    assert opp.opp_type == "hackathon"
    assert "Hello sir" in opp.spoken_greeting
    assert "hackathon" in opp.spoken_greeting.lower()
    assert "3 to 4 frontier LLMs" in opp.spoken_greeting
    assert opp.status == "PENDING_APPROVAL"
    assert opp.approval_token is not None
    assert trust_res.success is True
    assert len(trust_res.evidence) >= 1


@pytest.mark.asyncio
async def test_multi_llm_research_and_hydra_failover(tmp_path):
    """Verifies multi-model research queries 4 frontier perspectives and synthesizes research.md."""
    researcher = multi_llm_researcher
    pkg, trust_res = await researcher.conduct_multi_llm_research(
        topic="Switch-JARVIS Neural War Room",
        guidelines="Terminal agent bridge to collaborative team channels with rate-limit failover.",
        output_filename="test_research.md",
    )
    assert len(pkg.perspectives) == 4
    roles = [p.perspective for p in pkg.perspectives]
    assert any("Chief Architect" in r for r in roles)
    assert any("Product Strategist" in r for r in roles)
    assert any("Systems" in r for r in roles)
    assert any("Multimodal" in r for r in roles)
    assert Path(pkg.markdown_report_path).exists()
    assert trust_res.success is True
    assert trust_res.evidence[0].verified is True


def test_autonomous_repo_builder_creates_verified_git_repo(tmp_path):
    """Verifies autonomous repository builder initializes Git, writes modules and verifies tests."""
    target_repo_dir = tmp_path / "test-neural-room"
    repo_obj, trust_res = autonomous_repo_builder.build_project_repository(
        project_name="Test Neural Room",
        description="Autonomous multi-agent test repository",
        architecture_spec={"style": "micro-kernel"},
        candidate_name="Ganesh Nair",
        target_dir_override=target_repo_dir,
    )
    assert repo_obj.tests_passed is True
    assert (target_repo_dir / ".git").exists()
    assert (target_repo_dir / "README.md").exists()
    assert (target_repo_dir / "LICENSE").exists()
    assert (target_repo_dir / "main.py").exists()
    assert (target_repo_dir / "tests" / "test_core.py").exists()
    assert (target_repo_dir / ".github" / "workflows" / "ci.yml").exists()
    assert len(repo_obj.git_commit_hash) >= 7
    assert trust_res.success is True


def test_autonomous_applier_generates_accurate_submission():
    """Verifies form submission package uses Ganesh's master profile."""
    pkg, trust_res = autonomous_applier.generate_hackathon_submission_package(
        hackathon_title="Flip the Switch Hackathon",
        hackathon_url="https://www.wemakedevs.org/hackathons/switch",
        project_name="Neural War Room",
        project_slug="neural-war-room",
        repo_local_path="data/scaffolded_projects/neural-war-room",
        git_commit_hash="abc1234def",
        research_summary="Autonomous multi-agent consensus system.",
    )
    assert pkg.applicant_name == "Ganesh Nair"
    assert pkg.applicant_email == "nairganesh134@gmail.com"
    assert "9324094474" in pkg.applicant_phone
    assert pkg.fields_mapped["repository_url"] == "https://github.com/GaneshNair007/neural-war-room"
    assert Path(pkg.playwright_script_path).exists()
    assert trust_res.success is True


@pytest.mark.asyncio
async def test_full_autonomous_approval_execution_loop():
    """Verifies end-to-end execution of the 5-step autonomous lifecycle upon Ganesh's approval."""
    # 1. Generate briefing
    opp, _ = await daily_opportunity_connector.generate_midday_hackathon_briefing(
        voice_speak=False,
        dispatch_whatsapp=False,
        dispatch_switch=False,
    )
    assert opp.status == "PENDING_APPROVAL"

    # 2. Ganesh confirms/approves
    summary, trust_res = await daily_opportunity_connector.execute_approved_opportunity(
        opp_id=opp.opp_id,
        approval_token=opp.approval_token,
    )
    assert summary["status"] == "COMPLETED"
    assert len(summary["steps_completed"]) == 5
    assert summary["repository"]["tests_passed"] is True
    assert summary["submission"]["applicant"] == "Ganesh Nair"
    assert trust_res.success is True
    assert len(trust_res.evidence) >= 3


def test_opportunities_api_endpoints(test_client):
    """Verifies FastAPI opportunity endpoints for listing, triggering briefing, and executing approval."""
    # 1. Trigger daily briefing
    res_briefing = test_client.post(
        "/api/v1/opportunities/daily-briefing",
        json={"briefing_type": "hackathon", "voice_speak": False, "dispatch_whatsapp": False, "dispatch_switch": False},
    )
    assert res_briefing.status_code == 200
    opp_id = res_briefing.json()["opp_id"]

    # 2. List pending opportunities
    res_pending = test_client.get("/api/v1/opportunities/pending")
    assert res_pending.status_code == 200
    opps = res_pending.json()["opportunities"]
    assert any(o["opp_id"] == opp_id for o in opps)

    # 3. Approve opportunity
    res_approve = test_client.post(
        f"/api/v1/opportunities/{opp_id}/approve",
        json={"user_id": "ganesh", "confirm": True},
    )
    assert res_approve.status_code == 200
    data = res_approve.json()
    assert data["status"] == "SUCCESS"
    assert data["execution_summary"]["status"] == "COMPLETED"
    assert len(data["evidence"]) >= 1

    # 4. History
    res_hist = test_client.get("/api/v1/opportunities/history")
    assert res_hist.status_code == 200
    assert res_hist.json()["total_executions"] >= 1

