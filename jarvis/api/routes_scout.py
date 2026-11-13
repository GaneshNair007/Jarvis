"""Live hackathon discovery routes. Search leads are not verified event registrations."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from jarvis.agents.hackathon_scout import hackathon_scout_swarm
from jarvis.core.notifier import opportunity_notifier
from jarvis.core.obscura_browser import obscura_browser

router = APIRouter(prefix="/api/v1/scout", tags=["Hackathon & Opportunity Scout"])


class TriggerScoutRequest(BaseModel):
    target_phone: str = Field(default="+91 9324094474")
    query: str = Field(default="current AI hackathons India")


class DirectWhatsAppNotificationRequest(BaseModel):
    target_phone: str = Field(default="+91 9324094474")
    message: str


@router.post("/trigger")
async def trigger_autonomous_scout(body: TriggerScoutRequest):
    """Runs live discovery, fetches source pages, and writes research notes only."""
    try:
        return await hackathon_scout_swarm.execute_autonomous_scout_cycle(
            target_phone=body.target_phone,
            search_query=body.query,
            send_notification=False,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Scout workflow failed: {exc}") from exc


@router.get("/opportunities")
async def get_latest_opportunities():
    """Returns live discovery leads with explicit unavailable status when the provider fails."""
    opps = await obscura_browser.search_opportunities("current AI hackathons India", limit=5)
    analyzed = hackathon_scout_swarm.analyst.evaluate_opportunities(opps)
    return {
        "status": "discovery_only" if analyzed else "unavailable",
        "count": len(analyzed),
        "opportunities": analyzed,
    }


@router.post("/send-whatsapp")
async def send_direct_whatsapp_alert(body: DirectWhatsAppNotificationRequest):
    """Explicitly requests a WhatsApp send and returns the provider's dispatch status."""
    return await opportunity_notifier.send_whatsapp_message(
        phone_number=body.target_phone,
        message=body.message,
    )
