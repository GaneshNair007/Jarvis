"""
JARVIS Venture & Business Ideas REST API Endpoints
Provides search, profiling, and launch blueprint generation from the 200 AI Business Ideas catalog.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from jarvis.agents.venture_scout import venture_scout, BusinessIdea
from jarvis.business.playbook_engine import business_playbook_engine

router = APIRouter(prefix="/ventures", tags=["Venture & Business Scout"])


@router.get("/ideas")
def search_business_ideas(
    query: str = Query("", description="Keywords to search in title, domain, toolkit, or buyer"),
    domain: Optional[str] = Query(None, description="Filter by business domain"),
    limit: int = Query(10, ge=1, le=50, description="Max results"),
):
    """Searches across the 200 curated AI business ideas."""
    results = venture_scout.search_ideas(query=query, domain=domain, limit=limit)
    return {
        "total": len(results),
        "query": query,
        "domain": domain,
        "ideas": [i.model_dump() for i in results],
    }


@router.get("/match")
def match_ideas_for_ganesh(
    limit: int = Query(5, ge=1, le=20, description="Max top matched ideas"),
    preferred_domain: Optional[str] = Query(None, description="Optional preferred industry domain"),
):
    """
    Ranks the 200 business ideas against Ganesh's technical stack:
    Python, FastAPI, Local RTX 4050 ML, Audio/Voice, Agentic Automation, Zero Cost.
    """
    matches = venture_scout.match_ideas_for_profile(
        preferred_domain=preferred_domain,
        limit=limit,
    )
    return {
        "profile": "Ganesh Nair (RTX 4050, Python, FastAPI, Voice/Vision)",
        "total_matched": len(matches),
        "top_opportunities": [m.model_dump() for m in matches],
    }


@router.get("/blueprint/{idea_id}")
def get_idea_blueprint(idea_id: str):
    """Generates an actionable 30-day MVP and pilot execution blueprint for the given idea."""
    try:
        blueprint = venture_scout.generate_launch_blueprint(idea_id)
        return blueprint
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/evaluate/{idea_id}")
def evaluate_idea(idea_id: str):
    """Evaluates business idea against RTX 4050 compute and assigns 105-agent pod."""
    evaluation = business_playbook_engine.evaluate_idea_execution(idea_id)
    if "error" in evaluation:
        raise HTTPException(status_code=404, detail=evaluation["error"])
    return evaluation


@router.post("/grokbot/leads")
def grokbot_lead_followup(payload: Dict[str, Any]):
    """
    Grok Bot Workflow 01: Follow up with leads without chasing.
    Drafts personal, review-ready messages without automatic sending.
    """
    leads = payload.get("leads", [])
    company = payload.get("company_name", "Ganesh AI Ops")
    drafts = business_playbook_engine.run_lead_followup_workflow(leads, company_name=company)
    return {"total_drafts": len(drafts), "drafts": [d.model_dump() for d in drafts]}


@router.post("/grokbot/ad-pulse")
def grokbot_ad_pulse(payload: Dict[str, Any]):
    """
    Grok Bot Workflow 02: Unified daily ad report.
    Source-verified CTR, CPC, CPA, ROAS and spend summary.
    """
    metrics = payload.get("metrics", [])
    ad_pulse = business_playbook_engine.run_ad_pulse_workflow(metrics)
    return ad_pulse.model_dump()


@router.post("/grokbot/ops-sweep")
def grokbot_ops_sweep(payload: Dict[str, Any]):
    """
    Grok Bot Workflow 03: The Weekly Ops Sweep (Lifesaver Workflow).
    Audits overdue tasks, stalled leads, campaign flags, and human decision checkpoints.
    """
    task_board = payload.get("task_board", [])
    crm_leads = payload.get("crm_leads", [])
    ad_reports = payload.get("ad_reports", [])
    sweep = business_playbook_engine.run_weekly_ops_sweep(task_board, crm_leads, ad_reports)
    return sweep.model_dump()

