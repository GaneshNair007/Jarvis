"""
JARVIS Opportunities & Autonomous Pipeline API Routes
=====================================================
Exposes REST endpoints for:
  - Daily proactive briefings (morning career & midday hackathon)
  - Listing pending opportunities awaiting Ganesh's approval
  - Single-tap authenticated approval triggering the 5-step autonomous build & submit engine
  - Execution history and Merkle evidence
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from jarvis.config import settings
from jarvis.core.daily_connector import daily_opportunity_connector
from jarvis.core.logger import get_logger

logger = get_logger("api.opportunities")

router = APIRouter(prefix="/api/v1/opportunities", tags=["Opportunities & Autonomous Pipelines"])


class OpportunityApprovalRequest(BaseModel):
    user_id: str = Field(default="ganesh", description="Operator identity")
    approval_token: Optional[str] = Field(default=None, description="Cryptographic approval token if issued")
    confirm: bool = Field(default=True, description="Approval confirmation")


class DailyBriefingTriggerRequest(BaseModel):
    briefing_type: str = Field(default="hackathon", description="'career' or 'hackathon'")
    voice_speak: bool = Field(default=False, description="Speak aloud over host speakers")
    dispatch_whatsapp: bool = Field(default=False, description="Send WhatsApp alert")
    dispatch_switch: bool = Field(default=False, description="Send Switch room message")


@router.get("/pending")
async def list_pending_opportunities():
    """Lists all proactive opportunities currently awaiting operator approval."""
    pending = daily_opportunity_connector.get_pending_opportunities()
    return {
        "total_pending": len(pending),
        "opportunities": pending,
    }


@router.post("/daily-briefing")
async def trigger_daily_briefing(req: DailyBriefingTriggerRequest):
    """
    Manually triggers proactive daily briefing for testing or on-demand scout.
    """
    if req.briefing_type == "career":
        opp, trust_res = await daily_opportunity_connector.generate_morning_career_briefing(
            voice_speak=req.voice_speak,
            dispatch_whatsapp=req.dispatch_whatsapp,
            dispatch_switch=req.dispatch_switch,
        )
    else:
        opp, trust_res = await daily_opportunity_connector.generate_midday_hackathon_briefing(
            voice_speak=req.voice_speak,
            dispatch_whatsapp=req.dispatch_whatsapp,
            dispatch_switch=req.dispatch_switch,
        )

    return {
        "status": "BRIEFING_DELIVERED",
        "opp_id": opp.opp_id,
        "opp_type": opp.opp_type,
        "title": opp.title,
        "spoken_greeting": opp.spoken_greeting,
        "evidence_id": trust_res.evidence[0].evidence_id if trust_res.evidence else None,
    }


@router.post("/{opp_id}/approve")
async def approve_and_execute_opportunity(
    opp_id: str,
    req: OpportunityApprovalRequest,
):
    """
    Operator approves opportunity. Autonomously executes the 5-step pipeline:
      1. Consults 3-4 frontier LLMs (Claude, GPT-4o, DeepSeek, Gemini with Hydra failover).
      2. Synthesizes deep research (research.md).
      3. Scaffolds a new Git repository (git init, README, LICENSE, CI).
      4. Develops project code and verifies passing tests.
      5. Fills application form and generates submission package for Ganesh.
    """
    if not req.confirm:
        return {"opp_id": opp_id, "status": "REJECTED", "message": "Approval declined by user."}

    logger.info(f"API approval received for opportunity '{opp_id}' by user '{req.user_id}'.")
    summary, trust_res = await daily_opportunity_connector.execute_approved_opportunity(
        opp_id=opp_id,
        approval_token=req.approval_token,
    )

    return {
        "status": "SUCCESS",
        "opp_id": opp_id,
        "execution_summary": summary,
        "evidence_count": len(trust_res.evidence),
        "evidence": [e.to_dict() for e in trust_res.evidence],
    }


@router.get("/history")
async def get_opportunity_execution_history():
    """Returns history of all autonomously scaffolded projects and applications."""
    return {
        "total_executions": len(daily_opportunity_connector.execution_history),
        "executions": daily_opportunity_connector.execution_history,
    }

