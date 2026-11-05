"""
JARVIS Cross-Device Relay REST API.

Phone flow:
  1. Open http://<laptop>:8000/relay on the phone
  2. On the laptop, POST /api/v1/relay/pair to mint a 6-digit code
  3. Enter the code on the phone (exchanges it for a device token)
  4. Send commands from the phone; every reply is TrustResult-backed
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, Field

from jarvis.core.relay import RelayAuthError, device_relay

router = APIRouter(tags=["Cross-Device Relay"])

RELAY_PAGE = Path(__file__).resolve().parent / "relay_page.html"


class PairRequest(BaseModel):
    ttl_sec: int = Field(default=300, ge=30, le=900)


class ExchangeRequest(BaseModel):
    code: str = Field(min_length=4, max_length=12)
    device_name: str = Field(default="phone", max_length=64)


class CommandRequest(BaseModel):
    command: str = Field(min_length=1, max_length=2000)


def _bearer(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip()


@router.get("/relay", response_class=HTMLResponse)
async def relay_page():
    """Phone-friendly relay UI (pair once, then chat with the laptop)."""
    if not RELAY_PAGE.exists():
        raise HTTPException(status_code=404, detail="relay page missing")
    return FileResponse(RELAY_PAGE, media_type="text/html")


@router.post("/api/v1/relay/pair")
async def pair_device(req: PairRequest = PairRequest()):
    """Mints a short-lived 6-digit pairing code (run this on the laptop)."""
    return device_relay.create_pairing_code(ttl_sec=req.ttl_sec)


@router.post("/api/v1/relay/exchange")
async def exchange_code(req: ExchangeRequest):
    """Trades a pairing code for a persistent device token (phone step)."""
    try:
        return device_relay.exchange_code(req.code, device_name=req.device_name)
    except RelayAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc))


@router.post("/api/v1/relay/command")
async def relay_command(
    req: CommandRequest,
    authorization: Optional[str] = Header(default=None),
):
    """Executes a phone-initiated command on this machine (Bearer token)."""
    token = _bearer(authorization)
    trust = await device_relay.execute_command(token, req.command)
    payload = trust.to_dict()
    if trust.verdict != "success":
        ev_status = (trust.evidence.data or {}).get("status") if trust.evidence else None
        # 401 = auth/pairing rejection, 502 = command executed but failed upstream.
        raise HTTPException(status_code=401 if ev_status == "rejected" else 502, detail=payload)
    return payload


@router.get("/api/v1/relay/status")
async def relay_status(authorization: Optional[str] = Header(default=None)):
    """Host + voice daemon status for a paired device (Bearer token)."""
    token = _bearer(authorization)
    try:
        device = device_relay.authenticate(token)
    except RelayAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    return {"device": device, "relay": device_relay.status()}


@router.get("/api/v1/relay/devices")
async def relay_devices():
    """Laptop-side view of paired devices (no auth: local network only)."""
    return {"devices": device_relay.list_devices()}
