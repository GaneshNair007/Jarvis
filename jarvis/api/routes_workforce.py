"""
JARVIS Autonomous Workforce & WhatsApp Dispatch API Endpoints
Provides REST interfaces for fleet management (105 agents), live hackathon hunting,
problem statement synthesis, and direct WhatsApp notifications for Ganesh Nair.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from jarvis.agents.autonomous_workforce import autonomous_workforce
from jarvis.core.web_recon import web_opportunity_recon
from jarvis.powers.whatsapp_dispatcher import whatsapp_dispatcher

router = APIRouter(prefix="/workforce", tags=["Autonomous Workforce & Dispatch"])


class CustomWhatsAppRequest(BaseModel):
    message: str = Field(..., description="Message content to send via WhatsApp")
    phone: Optional[str] = Field(default="+919324094474", description="Recipient phone number")


class RunPipelineRequest(BaseModel):
    target_phone: Optional[str] = Field(default="+919324094474", description="Recipient phone for hackathon alert")
    location: Optional[str] = Field(default="India", description="Geographic scope for hackathons")
    candidate_name: Optional[str] = Field(default="Ganesh", description="Candidate name")


@router.get("/fleet")
async def get_workforce_fleet_status():
    """Returns census and operational status of all 105 autonomous workforce subagents."""
    return autonomous_workforce.get_fleet_status()


@router.get("/hackathons")
async def get_live_hackathons(
    location: str = Query("India", description="Filter hackathons by location"),
    limit: int = Query(5, ge=1, le=20, description="Max hackathons to return"),
):
    """Scrapes, aggregates, and ranks live hackathon opportunities for Ganesh."""
    hackathons = await web_opportunity_recon.search_live_hackathons(
        location=location,
        limit=limit,
    )
    return {
        "total": len(hackathons),
        "location": location,
        "hackathons": hackathons,
    }


@router.post("/hackathons/run-pipeline")
async def run_hackathon_pipeline(req: RunPipelineRequest = RunPipelineRequest()):
    """
    Mobilizes the 105-agent swarm across 5 divisions:
    Discovers hackathons -> Authors PROBLEM_STATEMENT.md -> Scaffolds Git repo -> Dispatches WhatsApp alert.
    """
    try:
        result = await autonomous_workforce.run_hackathon_opportunity_pipeline(
            target_phone=req.target_phone or "+919324094474",
            location=req.location or "India",
            candidate_name=req.candidate_name or "Ganesh",
        )
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Autonomous pipeline execution failed: {exc}")


@router.post("/whatsapp/send")
async def send_whatsapp(req: CustomWhatsAppRequest):
    """Dispatches a custom WhatsApp message to operator (+91 9324094474)."""
    try:
        receipt = await whatsapp_dispatcher.send_whatsapp_message(
            message=req.message,
            phone=req.phone,
        )
        return receipt
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"WhatsApp dispatch failed: {exc}")
