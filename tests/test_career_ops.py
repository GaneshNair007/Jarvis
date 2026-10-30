"""Automated Test Suite for Career-Ops Integration (PWR-328 to PWR-337).

Validates:
- PWR-328: Career service status and profile loading
- PWR-329: Job scan and ATS fit score calculation
- PWR-330: Tailored ATS resume generation
- PWR-331: Cover-letter generation with STAR alignment
- PWR-332: Deep company research dossier
- PWR-333: Contact finder and outreach drafts
- PWR-334: Application email drafting
- PWR-335: Application pipeline analytics and funnel tracking
- PWR-336: Interview prep, STAR scenarios, and toxic workplace red-flag detection
- PWR-337: Total compensation and salary-gap counter-offer analysis
- Career REST API endpoints (/api/v1/career/*)
"""

import pytest
from fastapi.testclient import TestClient

from jarvis.api.server import app
from jarvis.career.models import UserCareerProfile
from jarvis.career.service import CareerOpsService, career_service
from jarvis.powers.career_powers import career_powers
from jarvis.core.orchestrator import orchestrator


@pytest.fixture
def client():
    return TestClient(app)


def test_pwr_328_service_status():
    """Validates service layer initialization and profile status."""
    status = career_powers.get_service_status()
    assert status["power_id"] == "PWR-328"
    assert status["status"] == "healthy"
    assert status["candidate_name"] == "Ganesh Nair"
    assert status["max_concurrency"] == 3


def test_pwr_329_job_scan_fit_scoring():
    """Validates job description parsing and ATS fit score scoring."""
    sample_desc = (
        "Seeking Principal Systems Engineer experienced in Python, FastAPI, distributed systems, "
        "concurrency, Docker, and vector search with Qdrant and SQLite FTS5."
    )
    result = career_powers.scan_job_listing(
        job_title="Principal AI Systems Architect",
        company_name="DeepTech AI",
        description=sample_desc,
        job_url="https://jobs.example.com/deeptech/101"
    )

    assert result["power_id"] == "PWR-329"
    assert result["company_name"] == "DeepTech AI"
    assert result["global_score"] >= 70.0
    assert "Python" in result["matched_skills"]
    assert "FastAPI" in result["matched_skills"]
    assert "Strong Fit" in result["recommendation"] or "Moderate Fit" in result["recommendation"]


def test_pwr_330_tailored_ats_resume(tmp_path):
    """Validates generation of ATS tailored resume."""
    svc = CareerOpsService(cv_path=str(tmp_path / "cv.md"))
    (tmp_path / "cv.md").write_text("# Candidate\n## Experience\n- Lead engineer\n", encoding="utf-8")

    result = career_powers.generate_tailored_resume(
        job_title="Lead Distributed Engineer",
        company_name="ScaleAI Labs",
        target_keywords=["Distributed Systems", "SQLite FTS5", "FastAPI"]
    )

    assert result["power_id"] == "PWR-330"
    assert result["ats_score"] > 80.0
    assert "Distributed Systems" in result["included_keywords"]
    assert result["file_path"].endswith(".txt") or result["file_path"].endswith(".md")


def test_pwr_331_cover_letter():
    """Validates STAR tailored cover letter creation."""
    result = career_powers.generate_cover_letter(
        job_title="Principal Platform Architect",
        company_name="CloudMatrix",
        key_challenges=["Low latency retrieval", "High concurrency"]
    )

    assert result["power_id"] == "PWR-331"
    assert "CloudMatrix" in result["content"]
    assert len(result["star_points"]) >= 3


def test_pwr_332_company_research():
    """Validates company research brief compilation."""
    result = career_powers.research_company_brief(company_name="Anthropic")
    assert result["power_id"] == "PWR-332"
    assert result["company_name"] == "Anthropic"
    assert len(result["tech_stack"]) >= 3
    assert result["glassdoor_rating"] is not None


def test_pwr_333_find_contacts():
    """Validates discovery of hiring contacts and outreach drafts."""
    result = career_powers.find_company_contacts(
        company_name="Stripe",
        role_title="Infrastructure Architect"
    )

    assert result["power_id"] == "PWR-333"
    assert result["contacts_found"] >= 2
    recruiter = result["contacts"][0]
    assert "Recruiter" in recruiter["title"]
    assert "Stripe" in recruiter["outreach_draft"]


def test_pwr_334_draft_application_email():
    """Validates formal submission email drafting."""
    result = career_powers.draft_application_email(
        recipient_name="Sarah Connor",
        company_name="Cyberdyne Systems",
        role_title="AI Safety Architect"
    )

    assert result["power_id"] == "PWR-334"
    assert "Application: AI Safety Architect" in result["subject"]
    assert "Cyberdyne Systems" in result["body"]
    assert "Sarah Connor" in result["body"]


def test_pwr_335_pipeline_analytics():
    """Validates tracking and funnel pattern analytics."""
    # Ensure at least one application recorded
    career_powers.service.pipeline_analytics.record_application(
        company_name="Meta",
        job_title="Research Scientist",
        fit_score=88.5,
        status="screening"
    )

    stats = career_powers.analyze_application_pipeline()
    assert stats["power_id"] == "PWR-335"
    assert stats["total_applications"] >= 1
    assert "funnel" in stats
    assert "conversion_rates" in stats
    assert len(stats["insights"]) >= 1


def test_pwr_336_interview_prep_and_red_flags():
    """Validates interview preparation, STAR questions, and red-flag checking."""
    result = career_powers.interview_prep_and_red_flags(
        role_title="Principal AI Engineer",
        company_name="Apex Global",
        job_description="High-pressure startup environment wearing many hats, rockstar required."
    )

    assert result["power_id"] == "PWR-336"
    assert len(result["star_questions"]) >= 3
    assert len(result["questions_to_ask_team"]) >= 3
    assert any("wearing many hats" in flag for flag in result["red_flag_warnings"])


def test_pwr_337_offer_analysis_and_negotiation():
    """Validates total compensation gap calculation and counter-offer drafting."""
    result = career_powers.analyze_offer_and_salary_gap(
        company_name="NextGen Systems",
        role_title="Principal Systems Architect",
        base_salary=210000.0,
        bonus=25000.0,
        equity_annual_val=40000.0
    )

    assert result["power_id"] == "PWR-337"
    assert result["total_comp"] == 275000.0
    assert result["gap"] > 0
    assert "negotiation_script" in result
    assert "NextGen Systems" in result["negotiation_script"]


def test_career_rest_api_endpoints(client):
    """Validates FastAPI REST endpoints for Career-Ops."""
    # 1. GET /api/v1/career/status
    res = client.get("/api/v1/career/status")
    assert res.status_code == 200
    assert res.json()["power_id"] == "PWR-328"

    # 2. POST /api/v1/career/scan
    res = client.post("/api/v1/career/scan", json={
        "job_title": "Staff Engineer",
        "company_name": "Acme",
        "description": "Python, FastAPI, distributed architectures."
    })
    assert res.status_code == 200
    assert res.json()["power_id"] == "PWR-329"

    # 3. GET /api/v1/career/pipeline
    res = client.get("/api/v1/career/pipeline")
    assert res.status_code == 200
    assert res.json()["power_id"] == "PWR-335"

    # 4. POST /api/v1/career/offer-analysis
    res = client.post("/api/v1/career/offer-analysis", json={
        "company_name": "Acme",
        "role_title": "Staff Engineer",
        "base_salary": 200000.0,
        "bonus": 20000.0,
        "equity_annual_val": 30000.0
    })
    assert res.status_code == 200
    assert res.json()["power_id"] == "PWR-337"


def test_orchestrator_career_slash_commands():
    """Validates that orchestrator handles career slash commands instantly without LLM latency."""
    import asyncio
    res = asyncio.run(orchestrator.process_user_query("/job-scan Lead AI Architect at ScaleTech"))
    assert res["status"] == "COMPLETED"
    assert res["tier"] == "BYPASS"
    assert res["response"]["power_id"] == "PWR-329"

    res_pipe = asyncio.run(orchestrator.process_user_query("/pipeline"))
    assert res_pipe["status"] == "COMPLETED"
    assert res_pipe["response"]["power_id"] == "PWR-335"
