"""
JARVIS GSoC Preparation & Open-Source Contributor REST API Endpoints
Provides organization discovery, starter issue match, pitch drafting, and profile readiness audits.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from jarvis.agents.gsoc_scout import gsoc_scout, GSoCOrgSpec, GSoCIssueSpec

router = APIRouter(prefix="/gsoc", tags=["GSoC Contributor Scout & Open Source"])


@router.get("/organizations")
def get_curated_organizations(
    language: Optional[str] = Query(None, description="Filter organizations by primary programming language (e.g. Python, Go)"),
):
    """Lists premier Google Summer of Code (GSoC) organizations aligned with Ganesh's stack."""
    orgs = gsoc_scout.list_curated_organizations(language_filter=language)
    return {
        "total": len(orgs),
        "language_filter": language,
        "organizations": [o.model_dump() for o in orgs],
    }


@router.get("/issues")
def get_starter_issues(
    org: Optional[str] = Query(None, description="Filter issues by organization or repository"),
    complexity: Optional[str] = Query(None, description="Complexity filter ('Beginner', 'Intermediate')"),
    limit: int = Query(10, ge=1, le=50, description="Max results"),
):
    """Discovers high-probability 'good first issue' opportunities across top open-source repositories."""
    issues = gsoc_scout.search_starter_issues(org_name=org, complexity=complexity, limit=limit)
    return {
        "total": len(issues),
        "org_filter": org,
        "complexity_filter": complexity,
        "issues": [i.model_dump() for i in issues],
    }


@router.post("/pitch/{issue_id}")
def generate_contribution_pitch(
    issue_id: str,
    candidate_name: str = Query("Ganesh Nair", description="Candidate name"),
):
    """Generates an elite, mentor-aligned contribution proposal pitch for an issue."""
    try:
        pitch = gsoc_scout.draft_contribution_pitch(issue_id, candidate_name=candidate_name)
        return pitch
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/profile-audit")
def audit_profile_readiness(
    username: str = Query("GaneshNair007", description="GitHub username to evaluate"),
):
    """Audits GitHub profile readiness against Google Summer of Code (GSoC) selection rubrics."""
    audit = gsoc_scout.audit_github_profile_readiness(username=username)
    return audit
