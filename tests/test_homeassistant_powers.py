"""Tests for Home Assistant Local REST Powers."""

from unittest.mock import MagicMock, patch
import json
import pytest
from jarvis.powers.homeassistant_powers import HomeAssistantPowers


@pytest.fixture
def mock_hass():
    return HomeAssistantPowers(base_url="http://127.0.0.1:8123", token="mock-token-xyz")


def test_homeassistant_check_connection_success(mock_hass):
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({"message": "API running"}).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = mock_hass.check_connection()
        assert res["connected"] is True
        assert res["message"] == "API running"


def test_homeassistant_check_connection_offline(mock_hass):
    with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
        res = mock_hass.check_connection()
        assert res["connected"] is False
        assert "Connection refused" in res["error"]


def test_homeassistant_get_entity_state(mock_hass):
    mock_data = {
        "entity_id": "light.office",
        "state": "on",
        "attributes": {"brightness": 255, "friendly_name": "Office Light"},
        "last_changed": "2026-10-31T12:00:00Z",
    }
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(mock_data).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = mock_hass.get_entity_state("light.office")
        assert res["success"] is True
        assert res["state"] == "on"
        assert res["attributes"]["friendly_name"] == "Office Light"


def test_homeassistant_call_service_with_readback(mock_hass):
    service_resp = MagicMock()
    service_resp.read.return_value = json.dumps([{"entity_id": "light.office", "state": "on"}]).encode("utf-8")
    service_resp.__enter__.return_value = service_resp

    readback_resp = MagicMock()
    readback_resp.read.return_value = json.dumps(
        {
            "entity_id": "light.office",
            "state": "on",
            "attributes": {"friendly_name": "Office Light"},
        }
    ).encode("utf-8")
    readback_resp.__enter__.return_value = readback_resp

    with patch("urllib.request.urlopen", side_effect=[service_resp, readback_resp]):
        res = mock_hass.call_service(
            domain="light",
            service="turn_on",
            service_data={"entity_id": "light.office"},
        )
        assert res["success"] is True
        assert res["verified_state"] == "on"
