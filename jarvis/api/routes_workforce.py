"""On-demand workforce API: actual workflow components and live discovery."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from jarvis.agents.autonomous_workforce import autonomous_workforce
from jarvis.core.web_recon import web_opportunity_recon
from jarvis.powers.whatsapp_dispatcher import whatsapp_dispatcher

router = APIRouter(prefix="/workforce", tags=["Workforce & Opportunity Discovery"])


class CustomWhatsAppRequest(BaseModel):
    message: str = Field(..., description="Message content to send via WhatsApp")
    phone: Optional[str] = Field(default="+919324094474", description="Recipient phone number")


class RunPipelineRequest(BaseModel):
    target_phone: Optional[str] = Field(default="+919324094474", description="Recipient phone for an optional alert")
    location: Optional[str] = Field(default="India", description="Geographic search term")
    candidate_name: Optional[str] = Field(default="Ganesh", description="Candidate name")


@router.get("/fleet")
async def get_workforce_fleet_status():
    """Returns the real workflow component registry, not a fictitious agent-process count."""
    return autonomous_workforce.get_fleet_status()


@router.get("/hackathons")
async def get_live_hackathons(
    location: str = Query("India", description="Geographic search term"),
    limit: int = Query(5, ge=1, le=20, description="Maximum discovery links to return"),
):
    """Returns live search leads; results are not verified event registrations."""
    hackathons = await web_opportunity_recon.search_live_hackathons(
        query="current hackathons AI software students",
        location=location,
        limit=limit,
    )
    return {
        "status": "discovery_only" if hackathons else "unavailable",
        "message": (
            "Search leads only. Open official pages to verify event status, dates, eligibility and rules."
            if hackathons
            else "Live search returned no usable results. No curated fallback records were inserted."
        ),
        "total": len(hackathons),
        "location_query": location,
        "hackathons": hackathons,
    }


@router.post("/hackathons/run-pipeline")
async def run_hackathon_pipeline(req: RunPipelineRequest = RunPipelineRequest()):
    """Runs live discovery and page-grounded research notes; no auto-submission or notification."""
    try:
        return await autonomous_workforce.run_hackathon_opportunity_pipeline(
            target_phone=req.target_phone or "+919324094474",
            location=req.location or "India",
            candidate_name=req.candidate_name or "Ganesh",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Opportunity research workflow failed: {exc}") from exc


@router.post("/whatsapp/send")
async def send_whatsapp(req: CustomWhatsAppRequest):
    """Explicitly dispatches a custom WhatsApp message; returned status is the provider receipt."""
    try:
        return await whatsapp_dispatcher.send_whatsapp_message(
            message=req.message,
            phone=req.phone,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"WhatsApp dispatch failed: {exc}") from exc
