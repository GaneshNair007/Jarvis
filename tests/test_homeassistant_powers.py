"""Tests for Home Assistant REST powers and honest state verification."""

import json
from unittest.mock import MagicMock, patch

import pytest

from jarvis.powers.homeassistant_powers import HomeAssistantPowers


@pytest.fixture
def mock_hass():
    return HomeAssistantPowers(base_url="http://127.0.0.1:8123", token="mock-token-xyz")


def _response(payload):
    response = MagicMock()
    response.read.return_value = json.dumps(payload).encode("utf-8")
    response.__enter__.return_value = response
    return response


def test_homeassistant_requires_token_before_network_access():
    hass = HomeAssistantPowers(base_url="http://127.0.0.1:8123", token="")
    with patch("urllib.request.urlopen") as urlopen:
        result = hass.check_connection()
        assert result["connected"] is False
        assert result["configured"] is False
        urlopen.assert_not_called()


def test_homeassistant_check_connection_success(mock_hass):
    with patch("urllib.request.urlopen", return_value=_response({"message": "API running"})):
        result = mock_hass.check_connection()
    assert result["connected"] is True
    assert result["message"] == "API running"


def test_homeassistant_check_connection_offline(mock_hass):
    with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
        result = mock_hass.check_connection()
    assert result["connected"] is False
    assert "Connection refused" in result["error"]


def test_homeassistant_get_entity_state(mock_hass):
    data = {
        "entity_id": "light.office",
        "state": "on",
        "attributes": {"brightness": 255, "friendly_name": "Office Light"},
        "last_changed": "2026-10-31T12:00:00Z",
    }
    with patch("urllib.request.urlopen", return_value=_response(data)):
        result = mock_hass.get_entity_state("light.office")
    assert result["success"] is True
    assert result["state"] == "on"
    assert result["attributes"]["friendly_name"] == "Office Light"


def test_homeassistant_call_service_requires_token_and_does_not_send():
    hass = HomeAssistantPowers(base_url="http://127.0.0.1:8123", token="")
    with patch("urllib.request.urlopen") as urlopen:
        result = hass.call_service("light", "turn_on", {"entity_id": "light.office"})
    assert result["success"] is False
    assert result["verified"] is False
    urlopen.assert_not_called()


def test_homeassistant_call_service_requires_successful_readback(mock_hass):
    with patch(
        "urllib.request.urlopen",
        side_effect=[
            _response([{"entity_id": "light.office", "state": "on"}]),
            _response({"entity_id": "light.office", "state": "off", "attributes": {}}),
        ],
    ):
        result = mock_hass.call_service(
            domain="light",
            service="turn_on",
            service_data={"entity_id": "light.office"},
            expected_state="on",
        )
    assert result["success"] is False
    assert result["verified"] is False
    assert result["verified_state"] == "off"


def test_homeassistant_call_service_with_readback(mock_hass):
    with patch(
        "urllib.request.urlopen",
        side_effect=[
            _response([{"entity_id": "light.office", "state": "on"}]),
            _response({"entity_id": "light.office", "state": "on", "attributes": {}}),
        ],
    ):
        result = mock_hass.call_service(
            domain="light",
            service="turn_on",
            service_data={"entity_id": "light.office"},
            expected_state="on",
        )
    assert result["success"] is True
    assert result["verified"] is True
    assert result["verified_state"] == "on"
