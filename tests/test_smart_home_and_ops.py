"""Tests for Smart Home Room Control and Grok-style Ops Workflows.

Verifies:
- ElevenLabs TTS fallback & synthesis
- BroadLink IR AC & Projector control
- Wi-Fi Smart Plugs & Geyser safety shutoff
- Wi-Fi Smart Lighting & RGB control
- Room Scenes (work_mode, movie_night, sleep_mode, morning_wake)
- Natural voice command dispatch
- Opportunity Radar, Daily Pulse, and Weekly Ops Sweep
"""

import pytest
from fastapi.testclient import TestClient
from jarvis.api.server import app
from jarvis.powers.smart_home_powers import smart_home_powers
from jarvis.routines.ops_workflows import opportunity_radar, daily_system_pulse, weekly_ops_sweep
from jarvis.voice.tts import tts_engine


@pytest.fixture
def client():
    return TestClient(app)


# ==========================================
# 1. Voice & TTS Tests
# ==========================================


def test_tts_synthesize_wav():
    """Verifies TTS generates non-empty audio bytes with graceful fallback."""
    wav = tts_engine.synthesize_to_wav("Jarvis online.")
    assert isinstance(wav, bytes)
    assert len(wav) > 0


def test_tts_elevenlabs_graceful_fallback(monkeypatch):
    """Verifies that missing or invalid ElevenLabs API key cleanly falls back."""
    monkeypatch.setattr(tts_engine, "elevenlabs_api_key", "invalid_dummy_key")
    # Calling synthesize_elevenlabs will fail network/auth and return None
    res = tts_engine.synthesize_elevenlabs("Testing fallback")
    assert res is None

    # Full synthesize_to_wav must still succeed via fallback
    wav = tts_engine.synthesize_to_wav("Fallback check")
    assert isinstance(wav, bytes)
    assert len(wav) > 0


# ==========================================
# 2. Smart Home Room Control Tests
# ==========================================


def test_smart_home_devices_query():
    devices = smart_home_powers.get_all_devices()
    assert devices["power_id"] == "PWR-267"
    assert "climate.ac" in devices["devices"]
    assert "media.projector_tv" in devices["devices"]
    assert "switch.geyser" in devices["devices"]


def test_climate_ac_control():
    res = smart_home_powers.control_climate(action="on", temperature=22, mode="cool")
    assert res["power_id"] == "PWR-257"
    assert res["state"] == "on"
    assert res["target_temperature"] == 22
    assert res["mode"] == "cool"
    assert "22" in res["feedback"]


def test_media_projector_control():
    res = smart_home_powers.control_media(action="on", input_source="HDMI1", volume=40)
    assert res["power_id"] == "PWR-259"
    assert res["state"] == "on"
    assert res["input_source"] == "HDMI1"
    assert res["volume"] == 40


def test_plug_geyser_safety_timer():
    res = smart_home_powers.control_plug("switch.geyser", state="on", auto_off_minutes=15)
    assert res["power_id"] == "PWR-258"
    assert res["state"] == "on"
    assert res["timer_active"] is True
    assert "15-minute auto-off" in res["feedback"]


def test_light_control_rgb():
    res = smart_home_powers.control_lights("light.ambient_rgb", state="on", brightness=50, rgb_color=[0, 229, 255])
    assert res["power_id"] == "PWR-256"
    assert res["state"] == "on"
    assert res["brightness"] == 50
    assert res["rgb_color"] == [0, 229, 255]


def test_scene_activations():
    # Movie Night
    movie_res = smart_home_powers.activate_scene("movie_night")
    assert movie_res["status"] == "active"
    assert "Movie Night Scene" in movie_res["feedback"]
    assert smart_home_powers.device_states["media.projector_tv"]["state"] == "on"

    # Sleep Mode
    sleep_res = smart_home_powers.activate_scene("sleep_mode")
    assert sleep_res["status"] == "active"
    assert smart_home_powers.device_states["switch.geyser"]["state"] == "off"
    assert smart_home_powers.device_states["media.projector_tv"]["state"] == "off"


def test_voice_command_dispatch():
    ac_turn = smart_home_powers.process_voice_command("Jarvis, turn on the AC at 21 degrees")
    assert ac_turn["power_id"] == "PWR-257"
    assert ac_turn["target_temperature"] == 21

    geyser_turn = smart_home_powers.process_voice_command("Hey Jarvis, turn on the geyser")
    assert geyser_turn["power_id"] == "PWR-258"
    assert geyser_turn["state"] == "on"

    movie_turn = smart_home_powers.process_voice_command("It's movie time")
    assert movie_turn["power_id"] == "PWR-260"
    assert movie_turn["status"] == "active"


# ==========================================
# 3. Operational Workflows Tests
# ==========================================


def test_opportunity_radar():
    res = opportunity_radar.run()
    assert res["workflow"] == "opportunity_radar"
    assert "items" in res
    assert "total_tracked" in res
    assert "Strictly read-only" in res["policy"]


def test_daily_system_pulse():
    pulse = daily_system_pulse.run()
    assert pulse["workflow"] == "daily_system_pulse"
    assert "metrics" in pulse
    assert "cpu_percent" in pulse["metrics"]
    assert len(pulse["executive_summary"]) == 5


def test_weekly_ops_sweep():
    sweep = weekly_ops_sweep.run()
    assert sweep["workflow"] == "weekly_ops_sweep"
    assert len(sweep["top_three_weekly_priorities"]) == 3


# ==========================================
# 4. REST API Endpoint Tests
# ==========================================


def test_api_smarthome_endpoints(client, monkeypatch):
    """Public smart-home routes use Home Assistant and never the simulator."""
    from jarvis.api import routes_smart_home

    ha = routes_smart_home.homeassistant_powers
    monkeypatch.setattr(ha, "token", "test-token")
    monkeypatch.setattr(ha, "check_connection", lambda: {"connected": True})
    monkeypatch.setattr(
        ha,
        "list_entities",
        lambda domain_filter=None: {
            "success": True,
            "entities": [{"entity_id": "climate.ac", "state": "off", "friendly_name": "Room AC"}],
            "count": 1,
        },
    )
    monkeypatch.setattr(
        ha,
        "get_entity_state",
        lambda entity_id: {
            "success": True,
            "entity_id": entity_id,
            "state": "off",
            "attributes": {},
        },
    )

    def fake_service(domain, service, service_data=None, verify_entity_id=None, expected_state=None):
        verified_state = "off" if expected_state == "off" else "on"
        return {
            "power_id": "PWR-240",
            "success": True,
            "verified": True,
            "domain": domain,
            "service": service,
            "verified_state": verified_state,
            "service_data": service_data or {},
        }

    monkeypatch.setattr(ha, "call_service", fake_service)

    devices = client.get("/api/v1/smarthome/devices")
    assert devices.status_code == 200
    assert devices.json()["status"] == "connected"
    assert devices.json()["execution_mode"] == "home_assistant_live"
    assert devices.json()["devices"][0]["entity_id"] == "climate.ac"

    climate = client.post(
        "/api/v1/smarthome/climate",
        json={"action": "on", "temperature": 23},
    )
    assert climate.status_code == 200
    assert climate.json()["verified"] is True
    assert climate.json()["execution_mode"] == "home_assistant_live"

    plug = client.post(
        "/api/v1/smarthome/plug",
        json={"entity_id": "switch.geyser", "state": "on"},
    )
    assert plug.status_code == 200
    assert plug.json()["verified"] is True

    timer = client.post(
        "/api/v1/smarthome/plug",
        json={"entity_id": "switch.geyser", "state": "on", "auto_off_minutes": 15},
    )
    assert timer.status_code == 501
    assert "AUTO_OFF_AUTOMATION_NOT_CONFIGURED" in str(timer.json())

    scene = client.post("/api/v1/smarthome/scene", json={"scene": "work_mode"})
    assert scene.status_code == 501

    voice = client.post("/api/v1/smarthome/voice", json={"transcript": "turn on projector"})
    assert voice.status_code == 501


def test_api_smarthome_reports_unavailable_without_controller(client, monkeypatch):
    from jarvis.api import routes_smart_home

    monkeypatch.setattr(routes_smart_home.homeassistant_powers, "token", "")
    devices = client.get("/api/v1/smarthome/devices")
    assert devices.status_code == 200
    assert devices.json()["status"] == "unavailable"
    assert devices.json()["execution_mode"] == "none"
    assert devices.json()["device_count"] == 0

    climate = client.post("/api/v1/smarthome/climate", json={"action": "on"})
    assert climate.status_code == 503


def test_api_ops_endpoints(client):
    r1 = client.get("/api/v1/ops/opportunity-radar")
    assert r1.status_code == 200
    assert r1.json()["workflow"] == "opportunity_radar"

    r2 = client.get("/api/v1/ops/daily-pulse")
    assert r2.status_code == 200
    assert r2.json()["workflow"] == "daily_system_pulse"

    r3 = client.get("/api/v1/ops/weekly-sweep")
    assert r3.status_code == 200
    assert r3.json()["workflow"] == "weekly_ops_sweep"
