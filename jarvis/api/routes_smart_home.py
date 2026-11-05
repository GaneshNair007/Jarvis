"""JARVIS Smart Home & Room Control REST API Routes.

Endpoints for BroadLink IR/RF AC and Projector control, Wi-Fi smart plugs (Geyser),
smart lighting, synchronized room scenes, and natural voice command dispatch.
Reference: Ayman William Stage 01 Smart Room Architecture.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from jarvis.powers.smart_home_powers import smart_home_powers

router = APIRouter(prefix="/api/v1/smarthome", tags=["Smart Home & Room Control"])


class ClimateRequest(BaseModel):
    action: str = Field(default="toggle", description="'on', 'off', or 'toggle'")
    temperature: Optional[int] = Field(default=None, description="Target temp in Celsius (16-30)")
    mode: Optional[str] = Field(default=None, description="'cool', 'heat', 'fan', 'dry', 'auto'")
    fan_speed: Optional[str] = Field(default=None, description="'low', 'medium', 'high', 'auto'")


class MediaRequest(BaseModel):
    action: str = Field(default="toggle", description="'on', 'off', or 'toggle'")
    device_id: str = Field(default="media.projector_tv")
    input_source: Optional[str] = Field(default=None, description="'HDMI1', 'HDMI2', 'PC'")
    volume: Optional[int] = Field(default=None, description="0 to 100")
    mute: Optional[bool] = Field(default=None)


class PlugRequest(BaseModel):
    entity_id: str = Field(..., description="e.g. 'switch.geyser' or 'switch.workstation'")
    state: str = Field(default="toggle", description="'on', 'off', or 'toggle'")
    auto_off_minutes: Optional[int] = Field(default=None, description="Safety timer in minutes")


class LightRequest(BaseModel):
    entity_id: str = Field(default="light.ambient_rgb")
    state: str = Field(default="toggle", description="'on', 'off', or 'toggle'")
    brightness: Optional[int] = Field(default=None, description="0 to 100")
    rgb_color: Optional[List[int]] = Field(default=None, description="[R, G, B] 0-255")
    color_temp: Optional[int] = Field(default=None, description="2000K to 6500K")


class SceneRequest(BaseModel):
    scene: str = Field(..., description="'work_mode', 'movie_night', 'sleep_mode', 'morning_wake'")


class VoiceCommandRequest(BaseModel):
    transcript: str = Field(..., description="Spoken utterance, e.g. 'Turn on the AC', 'Movie night'")


@router.get("/devices")
async def list_room_devices():
    """Returns all registered room devices and current states."""
    return smart_home_powers.get_all_devices()


@router.get("/devices/{entity_id}")
async def get_device(entity_id: str):
    """Returns specific device state."""
    res = smart_home_powers.get_device_status(entity_id)
    if "error" in res:
        raise HTTPException(status_code=404, detail=res["error"])
    return res


@router.post("/climate")
async def control_ac(req: ClimateRequest):
    """Controls Room AC via BroadLink IR."""
    return smart_home_powers.control_climate(
        action=req.action,
        temperature=req.temperature,
        mode=req.mode,
        fan_speed=req.fan_speed,
    )


@router.post("/media")
async def control_projector_tv(req: MediaRequest):
    """Controls Projector / TV via BroadLink IR."""
    return smart_home_powers.control_media(
        action=req.action,
        device_id=req.device_id,
        input_source=req.input_source,
        volume=req.volume,
        mute=req.mute,
    )


@router.post("/plug")
async def control_smart_plug(req: PlugRequest):
    """Controls Wi-Fi Smart Plug (Geyser / Workstation) with safety timer."""
    return smart_home_powers.control_plug(
        entity_id=req.entity_id,
        state=req.state,
        auto_off_minutes=req.auto_off_minutes,
    )


@router.post("/lights")
async def control_smart_lights(req: LightRequest):
    """Controls Wi-Fi Smart Lighting brightness, color, and power."""
    return smart_home_powers.control_lights(
        entity_id=req.entity_id,
        state=req.state,
        brightness=req.brightness,
        rgb_color=req.rgb_color,
        color_temp=req.color_temp,
    )


@router.post("/scene")
async def trigger_room_scene(req: SceneRequest):
    """Activates multi-device synchronized room scene."""
    return smart_home_powers.activate_scene(req.scene)


@router.post("/voice")
async def parse_smart_room_voice(req: VoiceCommandRequest):
    """Parses natural voice utterances into smart room actions."""
    return smart_home_powers.process_voice_command(req.transcript)

