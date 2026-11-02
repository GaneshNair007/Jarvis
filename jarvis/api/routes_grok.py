"""
OpenMausBot & Grok Bot API Endpoints for Project JARVIS.
Exposes multi-bot roster, Grok persona chat, normalized event streaming, and permission broker resolution.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from jarvis.core.openmaus_grok import openmaus_harness, GrokMode

router = APIRouter(prefix="/api/v1/grok", tags=["grok_openmaus"])


class GrokChatRequest(BaseModel):
    message: str = Field(..., description="User query or instruction for Grok")
    bot_id: str = Field(default="grok", description="Target bot: grok, code_bot, research_bot, sys_bot, reflex_bot")
    mode: Optional[str] = Field(default="standard", description="standard, fun, think, code")
    channel: str = Field(default="#general", description="Target conversation channel")


class PermissionResolutionRequest(BaseModel):
    approved: bool


@router.post("/chat")
async def grok_chat(req: GrokChatRequest):
    """Executes a chat or task request through Grok Bot or selected OpenMausBot agent."""
    try:
        mode_enum = GrokMode(req.mode.lower()) if req.mode else GrokMode.STANDARD
    except ValueError:
        mode_enum = GrokMode.STANDARD

    res = await openmaus_harness.chat(
        prompt=req.message,
        bot_id=req.bot_id,
        mode=mode_enum,
        channel=req.channel,
    )
    return res


@router.get("/roster")
async def get_bot_roster():
    """Lists all active bots in the OpenMausBot sidebar roster."""
    return {
        "status": "online",
        "total_bots": len(openmaus_harness.roster.bots),
        "bots": openmaus_harness.roster.list_bots(),
    }


@router.get("/channels")
async def get_channels():
    """Lists all active multi-agent channels."""
    return {
        "channels": openmaus_harness.channels,
    }


@router.get("/events")
async def get_recent_events(limit: int = 50):
    """Retrieves the normalized agent event stream (thoughts, tool calls, messages)."""
    events = [e.to_dict() for e in openmaus_harness.event_history[-limit:]]
    return {
        "total_events": len(events),
        "events": events,
    }


@router.get("/permissions")
async def get_pending_permissions():
    """Lists pending high-privilege actions held by the inline permission broker."""
    return {
        "pending": openmaus_harness.broker.get_pending(),
    }


@router.post("/permissions/{decision_id}/resolve")
async def resolve_permission(decision_id: str, body: PermissionResolutionRequest):
    """Approves or denies an action intercepted by the inline permission broker."""
    success = openmaus_harness.broker.resolve(decision_id, approved=body.approved)
    if not success and decision_id not in openmaus_harness.broker._pending_decisions:
        raise HTTPException(status_code=404, detail="Decision ID not found")
    return {
        "decision_id": decision_id,
        "status": "APPROVED" if body.approved else "DENIED",
    }
