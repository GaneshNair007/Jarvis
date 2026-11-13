"""Smart-home API backed only by a configured Home Assistant controller.

The legacy SmartHomePowers implementation is an in-memory simulator. It is
kept for unit/demo use, but these public API routes never call it or represent
its simulated state as a physical device.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from jarvis.powers.homeassistant_powers import homeassistant_powers

router = APIRouter(prefix="/api/v1/smarthome", tags=["Smart Home & Room Control"])


class ClimateRequest(BaseModel):
    action: str = Field(default="toggle", description="'on', 'off', or 'toggle'")
    temperature: Optional[int] = Field(default=None, ge=16, le=30)
    mode: Optional[str] = Field(default=None)
    fan_speed: Optional[str] = Field(default=None)


class MediaRequest(BaseModel):
    action: str = Field(default="toggle", description="'on', 'off', or 'toggle'")
    device_id: str = Field(default="media_player.projector_tv")
    input_source: Optional[str] = None
    volume: Optional[int] = Field(default=None, ge=0, le=100)
    mute: Optional[bool] = None


class PlugRequest(BaseModel):
    entity_id: str = Field(..., description="A real Home Assistant switch entity ID")
    state: str = Field(default="toggle", description="'on', 'off', or 'toggle'")
    auto_off_minutes: Optional[int] = Field(default=None, ge=1, le=1440)


class LightRequest(BaseModel):
    entity_id: str = Field(default="light.ambient_rgb")
    state: str = Field(default="toggle", description="'on', 'off', or 'toggle'")
    brightness: Optional[int] = Field(default=None, ge=0, le=100)
    rgb_color: Optional[List[int]] = None
    color_temp: Optional[int] = Field(default=None, ge=2000, le=6500)


class SceneRequest(BaseModel):
    scene: str = Field(..., description="A configured Home Assistant scene entity")


class VoiceCommandRequest(BaseModel):
    transcript: str = Field(..., description="Spoken utterance")


def _require_home_assistant() -> Dict[str, Any]:
    """Require credentials and a successful live Home Assistant health check."""
    if not homeassistant_powers.token:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unavailable",
                "error": "HASS_TOKEN_NOT_CONFIGURED",
                "message": "Physical device control is disabled until HASS_URL and HASS_TOKEN are configured.",
            },
        )
    connection = homeassistant_powers.check_connection()
    if not connection.get("connected"):
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unavailable",
                "error": "HOME_ASSISTANT_UNREACHABLE",
                "message": "Home Assistant failed its live connection check; no device command was sent.",
                "details": connection,
            },
        )
    return connection


def _validate_entity(entity_id: str, expected_domain: str) -> str:
    clean = str(entity_id or "").strip()
    if (
        not clean.startswith(f"{expected_domain}.")
        or len(clean) > 255
        or "/" in clean
        or "\\" in clean
    ):
        raise HTTPException(
            status_code=422,
            detail=f"Expected a Home Assistant {expected_domain} entity ID.",
        )
    return clean


def _service(
    domain: str,
    service: str,
    entity_id: str,
    service_data: Optional[Dict[str, Any]] = None,
    expected_state: Optional[str] = None,
) -> Dict[str, Any]:
    """Invoke a controller service and require a verified state readback."""
    result = homeassistant_powers.call_service(
        domain=domain,
        service=service,
        service_data={"entity_id": entity_id, **(service_data or {})},
        verify_entity_id=entity_id,
        expected_state=expected_state,
    )
    if not result.get("success") or not result.get("verified"):
        raise HTTPException(
            status_code=502,
            detail={
                "status": "failed_verification",
                "error": "HOME_ASSISTANT_STATE_NOT_VERIFIED",
                "message": "The requested device state was not confirmed. Treat the action as unverified.",
                "details": result,
            },
        )
    return {
        **result,
        "status": "success",
        "execution_mode": "home_assistant_live",
        "controller": "home_assistant",
    }


def _resolve_action(entity_id: str, action: str) -> tuple[str, str]:
    """Resolve toggle against a real current state; return service + expected state."""
    _require_home_assistant()
    if action not in {"on", "off", "toggle"}:
        raise HTTPException(status_code=422, detail="Action must be on, off, or toggle.")
    if action == "toggle":
        state = homeassistant_powers.get_entity_state(entity_id)
        if not state.get("success"):
            raise HTTPException(
                status_code=502,
                detail={
                    "status": "unavailable",
                    "error": "DEVICE_STATE_UNAVAILABLE",
                    "details": state,
                },
            )
        action = "off" if state.get("state") not in {"off", "unknown", "unavailable", None} else "on"
    return ("turn_on", "not_off") if action == "on" else ("turn_off", "off")


@router.get("/devices")
async def list_room_devices():
    """Return the real HA entity list, never an in-memory demonstration inventory."""
    if not homeassistant_powers.token:
        return {
            "power_id": "PWR-267",
            "status": "unavailable",
            "execution_mode": "none",
            "device_count": 0,
            "devices": [],
            "message": "No physical controller is connected. Configure HASS_URL and HASS_TOKEN to discover devices.",
        }
    connection = homeassistant_powers.check_connection()
    if not connection.get("connected"):
        return {
            "power_id": "PWR-267",
            "status": "unavailable",
            "execution_mode": "none",
            "device_count": 0,
            "devices": [],
            "message": "Home Assistant is unreachable. No simulated device inventory is being shown.",
            "error": connection.get("error"),
        }
    result = homeassistant_powers.list_entities()
    if not result.get("success"):
        raise HTTPException(status_code=502, detail=result)
    entities = result.get("entities", [])
    return {
        "power_id": "PWR-267",
        "status": "connected",
        "execution_mode": "home_assistant_live",
        "controller": "home_assistant",
        "device_count": len(entities),
        "devices": entities,
    }


@router.get("/devices/{entity_id}")
async def get_device(entity_id: str):
    """Read one real entity state from Home Assistant."""
    _require_home_assistant()
    if "." not in entity_id:
        raise HTTPException(status_code=422, detail="Expected a domain.entity_id value.")
    domain, _ = entity_id.split(".", 1)
    entity_id = _validate_entity(entity_id, domain)
    result = homeassistant_powers.get_entity_state(entity_id)
    if not result.get("success"):
        raise HTTPException(status_code=502, detail=result)
    return {**result, "execution_mode": "home_assistant_live"}


@router.post("/climate")
async def control_ac(req: ClimateRequest):
    entity_id = _validate_entity(os.getenv("JARVIS_HA_CLIMATE_ENTITY", "climate.ac"), "climate")
    service, expected = _resolve_action(entity_id, req.action)
    result = _service("climate", service, entity_id, expected_state=expected)
    if req.action != "off":
        if req.temperature is not None:
            result = _service(
                "climate", "set_temperature", entity_id,
                {"temperature": req.temperature}, expected_state="not_off"
            )
        if req.mode is not None:
            if req.mode not in {"cool", "heat", "fan_only", "dry", "auto"}:
                raise HTTPException(status_code=422, detail="Unsupported HVAC mode.")
            result = _service(
                "climate", "set_hvac_mode", entity_id,
                {"hvac_mode": req.mode}, expected_state="not_off"
            )
        if req.fan_speed is not None:
            if req.fan_speed not in {"low", "medium", "high", "auto"}:
                raise HTTPException(status_code=422, detail="Unsupported fan mode.")
            result = _service(
                "climate", "set_fan_mode", entity_id,
                {"fan_mode": req.fan_speed}, expected_state="not_off"
            )
    return {**result, "entity_id": entity_id}


@router.post("/media")
async def control_projector_tv(req: MediaRequest):
    entity_id = _validate_entity(
        os.getenv("JARVIS_HA_MEDIA_ENTITY", req.device_id), "media_player"
    )
    service, expected = _resolve_action(entity_id, req.action)
    result = _service("media_player", service, entity_id, expected_state=expected)
    if req.input_source:
        result = _service("media_player", "select_source", entity_id, {"source": req.input_source})
    if req.volume is not None:
        result = _service("media_player", "volume_set", entity_id, {"volume_level": req.volume / 100.0})
    if req.mute is not None:
        result = _service("media_player", "volume_mute", entity_id, {"is_volume_muted": req.mute})
    return {**result, "entity_id": entity_id}


@router.post("/plug")
async def control_smart_plug(req: PlugRequest):
    entity_id = _validate_entity(req.entity_id, "switch")
    if req.auto_off_minutes is not None:
        raise HTTPException(
            status_code=501,
            detail={
                "status": "unavailable",
                "error": "AUTO_OFF_AUTOMATION_NOT_CONFIGURED",
                "message": "No verified Home Assistant auto-off automation is configured; no timer is claimed.",
            },
        )
    service, expected = _resolve_action(entity_id, req.state)
    return _service("switch", service, entity_id, expected_state=expected)


@router.post("/lights")
async def control_smart_lights(req: LightRequest):
    entity_id = _validate_entity(req.entity_id, "light")
    service, expected = _resolve_action(entity_id, req.state)
    data: Dict[str, Any] = {}
    if req.brightness is not None:
        data["brightness"] = round(req.brightness * 255 / 100)
    if req.rgb_color is not None:
        if len(req.rgb_color) != 3 or any(not 0 <= value <= 255 for value in req.rgb_color):
            raise HTTPException(status_code=422, detail="rgb_color must contain three values from 0 to 255.")
        data["rgb_color"] = req.rgb_color
    if req.color_temp is not None:
        data["color_temp_kelvin"] = req.color_temp
    return _service("light", service, entity_id, data, expected_state=expected)


@router.post("/scene")
async def trigger_room_scene(req: SceneRequest):
    """Disable multi-device scenes until each affected entity can be verified."""
    raise HTTPException(
        status_code=501,
        detail={
            "status": "unavailable",
            "error": "SCENE_READBACK_NOT_IMPLEMENTED",
            "message": "Scene activation is disabled until every affected entity has verified state readback.",
            "requested_scene": req.scene,
        },
    )


@router.post("/voice")
async def parse_smart_room_voice(req: VoiceCommandRequest):
    """Disable voice-to-device dispatch until it uses the verified HA service path."""
    raise HTTPException(
        status_code=501,
        detail={
            "status": "unavailable",
            "error": "VOICE_DEVICE_DISPATCH_NOT_IMPLEMENTED",
            "message": "Voice-to-device dispatch is disabled on this endpoint; no device command was sent.",
            "transcript": req.transcript,
        },
    )
