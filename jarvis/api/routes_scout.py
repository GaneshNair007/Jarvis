"""
JARVIS Autonomous Hackathon & Opportunity Scout API Routes
Provides REST endpoints to trigger the 4-agent workforce, retrieve analyzed
problem statements, and dispatch WhatsApp alert cards to Ganesh (+91 9324094474).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from jarvis.agents.hackathon_scout import hackathon_scout_swarm
from jarvis.core.notifier import opportunity_notifier

router = APIRouter(prefix="/api/v1/scout", tags=["Hackathon & Opportunity Scout Swarm"])


class TriggerScoutRequest(BaseModel):
    target_phone: str = Field(default="+91 9324094474", description="Recipient phone number for WhatsApp digest")
    query: str = Field(default="AI Agent Hackathons 2026 GSoC India", description="Search & discovery query")


class DirectWhatsAppNotificationRequest(BaseModel):
    target_phone: str = Field(default="+91 9324094474")
    message: str


@router.post("/trigger")
async def trigger_autonomous_scout(body: TriggerScoutRequest):
    """
    Triggers the 4-Agent Autonomous Workforce:
    1. ScoutAgent discovers hackathons & GSoC challenges via Obscura browser.
    2. AnalystAgent filters and scores problem statements.
    3. ArchitectAgent scaffolds repositories and writes PROBLEM_STATEMENT.md.
    4. DispatcherAgent formats and sends WhatsApp digest to user.
    """
    try:
        result = await hackathon_scout_swarm.execute_autonomous_scout_cycle(
            target_phone=body.target_phone,
            search_query=body.query,
        )
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Autonomous scout cycle failed: {exc}")


@router.get("/opportunities")
async def get_latest_opportunities():
    """Returns curated opportunities and active hackathon targets."""
    from jarvis.core.obscura_browser import obscura_browser

    opps = await obscura_browser.search_opportunities("AI hackathon India 2026 GSoC", limit=5)
    analyzed = hackathon_scout_swarm.analyst.evaluate_opportunities(opps)
    return {
        "status": "success",
        "count": len(analyzed),
        "opportunities": analyzed,
    }


@router.post("/send-whatsapp")
async def send_direct_whatsapp_alert(body: DirectWhatsAppNotificationRequest):
    """Dispatches a direct WhatsApp alert or simulated notification to Ganesh."""
    res = await opportunity_notifier.send_whatsapp_message(
        phone_number=body.target_phone,
        message=body.message,
    )
    return res
