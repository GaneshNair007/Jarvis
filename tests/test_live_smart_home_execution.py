"""Regression tests for real smart-home execution and truthful status reporting."""

from unittest.mock import patch

from jarvis.powers.smart_home_powers import SmartHomePowers


def test_ac_command_reports_unavailable_when_home_assistant_is_offline():
    powers = SmartHomePowers()
    unavailable = {
        "success": False,
        "status": "unavailable",
        "error": "Connection refused",
    }

    with patch(
        "jarvis.powers.smart_home_powers.homeassistant_powers.control_climate",
        return_value=unavailable,
    ):
        result = powers.process_voice_command("turn on my AC")

    assert result["success"] is False
    assert result["status"] == "unavailable"
    assert "Connection refused" in result["feedback"]


def test_ac_command_requires_verified_hardware_state():
    powers = SmartHomePowers()
    verified = {
        "success": True,
        "status": "success",
        "verified": True,
        "entity_id": "climate.bedroom_ac",
        "state": "cool",
        "message": "AC on confirmed by Home Assistant",
    }

    with patch(
        "jarvis.powers.smart_home_powers.homeassistant_powers.control_climate",
        return_value=verified,
    ):
        result = powers.process_voice_command("turn on my AC")

    assert result["success"] is True
    assert result["verified"] is True
    assert result["entity_id"] == "climate.bedroom_ac"


def test_ac_never_uses_in_memory_device_state_as_success():
    powers = SmartHomePowers()

    with patch(
        "jarvis.powers.smart_home_powers.homeassistant_powers.control_climate",
        return_value={
            "success": False,
            "status": "needs_configuration",
            "error": "No climate entity found",
        },
    ):
        result = powers.process_voice_command("turn on my AC")

    assert result["success"] is False
    assert result["status"] == "needs_configuration"
    assert powers.device_states["climate.ac"]["state"] == "off"
