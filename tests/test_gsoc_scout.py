"""
Unit and Integration Tests for JARVIS GSoC Contributor Scout & Open-Source Preparation Engine
Verifies curated organizations, starter issues matching, pitch proposal generation,
GitHub profile readiness audits, and FastAPI REST endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from jarvis.agents.gsoc_scout import gsoc_scout, GSoCOrgSpec, GSoCIssueSpec
from jarvis.api.server import app

client = TestClient(app)


def test_gsoc_curated_organizations():
    """Verifies curated open-source organizations list is well-formed and scored."""
    orgs = gsoc_scout.list_curated_organizations()
    assert len(orgs) >= 6
    org_ids = [o.org_id for o in orgs]
    assert "psf" in org_ids
    assert "cncf" in org_ids
    assert "lf_ai" in org_ids
    assert "owasp" in org_ids

    # Check PSF details
    psf = next(o for o in orgs if o.org_id == "psf")
    assert "Python" in psf.primary_languages
    assert psf.ganesh_stack_fit >= 0.90


def test_gsoc_organization_filter_by_language():
    """Verifies filtering by language (Python, Go)."""
    python_orgs = gsoc_scout.list_curated_organizations(language_filter="Python")
    assert len(python_orgs) >= 4
    assert all(any("python" in l.lower() for l in o.primary_languages) for o in python_orgs)

    go_orgs = gsoc_scout.list_curated_organizations(language_filter="Go")
    assert len(go_orgs) >= 1
    assert any("cncf" == o.org_id for o in go_orgs)


def test_gsoc_starter_issues_search():
    """Verifies retrieval of starter issues and fit scoring."""
    issues = gsoc_scout.search_starter_issues(limit=5)
    assert len(issues) >= 4
    first = issues[0]
    assert first.fit_score >= 0.90
    assert first.url.startswith("https://github.com/")

    # Filter by org
    psf_issues = gsoc_scout.search_starter_issues(org_name="sympy")
    assert len(psf_issues) >= 1
    assert "sympy" in psf_issues[0].repo_name.lower()


def test_gsoc_pitch_generation():
    """Verifies that pitch contains GSoC-aligned root cause, approach, and timeline."""
    pitch = gsoc_scout.draft_contribution_pitch("psf_sympy_01", candidate_name="Ganesh Nair")
    assert pitch["issue_id"] == "psf_sympy_01"
    assert "Ganesh Nair" in pitch["candidate_name"]
    md = pitch["pitch_markdown"]
    assert "### Proposed Resolution" in md
    assert "1. Analysis of Root Cause" in md
    assert "2. Proposed Technical Approach" in md
    assert "3. Deliverables & PR Timeline" in md
    assert "GaneshNair007" in md


def test_gsoc_profile_audit():
    """Verifies profile rubric score, grade, and actionable recommendations."""
    audit = gsoc_scout.audit_github_profile_readiness("GaneshNair007")
    assert audit["username"] == "GaneshNair007"
    assert audit["overall_gsoc_readiness_score"] >= 85.0
    assert "A" in audit["readiness_grade"]
    assert len(audit["rubric_breakdown"]) >= 5
    assert "sympy" in audit["recommended_next_action"].lower()


def test_fastapi_gsoc_endpoints():
    """Verifies REST endpoints for organizations, issues, pitch, and profile audit."""
    # 1. GET /gsoc/organizations
    r1 = client.get("/gsoc/organizations")
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["total"] >= 6

    # 2. GET /gsoc/issues
    r2 = client.get("/gsoc/issues?limit=3")
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["total"] == 3

    # 3. POST /gsoc/pitch/lf_onnx_01
    r3 = client.post("/gsoc/pitch/lf_onnx_01?candidate_name=Ganesh%20Nair")
    assert r3.status_code == 200
    d3 = r3.json()
    assert d3["issue_id"] == "lf_onnx_01"
    assert "onnx" in d3["repo_name"].lower()

    # 4. GET /gsoc/profile-audit
    r4 = client.get("/gsoc/profile-audit?username=GaneshNair007")
    assert r4.status_code == 200
    d4 = r4.json()
    assert d4["overall_gsoc_readiness_score"] >= 85.0
