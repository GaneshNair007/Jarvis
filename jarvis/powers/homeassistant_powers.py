"""JARVIS Home Assistant Local REST Powers (PWR-238 to PWR-252).

Provides authenticated local REST API integration with Home Assistant (e.g. http://127.0.0.1:8123),
entity status querying, service invocation with state-transition readback verification,
without offline simulation; service success requires state readback.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
import urllib.error
import urllib.request
import json

from jarvis.core.logger import get_logger
from jarvis.core.audit import audit_ledger

logger = get_logger("powers.homeassistant")


class HomeAssistantPowers:
    """Implementations for local Home Assistant REST API interactions."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        token: Optional[str] = None,
    ):
        self.base_url = (base_url or os.getenv("HASS_URL", "http://127.0.0.1:8123")).rstrip("/")
        self.token = token or os.getenv("HASS_TOKEN", "")

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def check_connection(self) -> Dict[str, Any]:
        """PWR-238A: Checks connectivity and API availability for local Home Assistant."""
        if not self.token:
            return {
                "power_id": "PWR-238",
                "connected": False,
                "configured": False,
                "base_url": self.base_url,
                "error": "HASS_TOKEN is not configured.",
                "suggestion": "Set HASS_URL and HASS_TOKEN before enabling physical device control.",
            }
        url = f"{self.base_url}/api/"
        req = urllib.request.Request(url, headers=self._headers(), method="GET")
        try:
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {
                    "power_id": "PWR-238",
                    "connected": True,
                    "base_url": self.base_url,
                    "message": data.get("message", "API running"),
                }
        except Exception as e:
            logger.debug(f"Home Assistant connection check failed ({self.base_url}): {e}")
            return {
                "power_id": "PWR-238",
                "connected": False,
                "base_url": self.base_url,
                "error": str(e),
                "suggestion": "Ensure Home Assistant is running on local network and HASS_TOKEN is configured.",
            }

    def get_entity_state(self, entity_id: str) -> Dict[str, Any]:
        """PWR-238: Queries current state and attributes of a specific Home Assistant entity."""
        if not self.token:
            return {
                "power_id": "PWR-238",
                "success": False,
                "entity_id": entity_id,
                "error": "HASS_TOKEN is not configured.",
            }
        url = f"{self.base_url}/api/states/{entity_id}"
        req = urllib.request.Request(url, headers=self._headers(), method="GET")
        try:
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {
                    "power_id": "PWR-238",
                    "success": True,
                    "entity_id": entity_id,
                    "state": data.get("state"),
                    "attributes": data.get("attributes", {}),
                    "last_changed": data.get("last_changed"),
                }
        except urllib.error.HTTPError as he:
            return {
                "power_id": "PWR-238",
                "success": False,
                "entity_id": entity_id,
                "error": f"HTTP {he.code}: {he.reason}",
            }
        except Exception as e:
            return {
                "power_id": "PWR-238",
                "success": False,
                "entity_id": entity_id,
                "error": f"Connection failed: {e}",
            }

    def list_entities(self, domain_filter: Optional[str] = None) -> Dict[str, Any]:
        """PWR-239: Queries all available entity states from Home Assistant."""
        if not self.token:
            return {
                "power_id": "PWR-239",
                "success": False,
                "count": 0,
                "entities": [],
                "error": "HASS_TOKEN is not configured.",
            }
        url = f"{self.base_url}/api/states"
        req = urllib.request.Request(url, headers=self._headers(), method="GET")
        try:
            with urllib.request.urlopen(req, timeout=4) as resp:
                states: List[Dict[str, Any]] = json.loads(resp.read().decode("utf-8"))
                if domain_filter:
                    states = [s for s in states if s.get("entity_id", "").startswith(f"{domain_filter}.")]
                return {
                    "power_id": "PWR-239",
                    "success": True,
                    "count": len(states),
                    "entities": [
                        {
                            "entity_id": s.get("entity_id"),
                            "state": s.get("state"),
                            "friendly_name": s.get("attributes", {}).get("friendly_name"),
                        }
                        for s in states
                    ],
                }
        except Exception as e:
            return {
                "power_id": "PWR-239",
                "success": False,
                "count": 0,
                "entities": [],
                "error": str(e),
            }

    def call_service(
        self,
        domain: str,
        service: str,
        service_data: Optional[Dict[str, Any]] = None,
        verify_entity_id: Optional[str] = None,
        expected_state: Optional[str] = None,
    ) -> Dict[str, Any]:
        """PWR-240: Calls a Home Assistant service and verifies state readback."""
        payload_data = service_data or {}
        target_entity = verify_entity_id or payload_data.get("entity_id")

        if not self.token:
            return {
                "power_id": "PWR-240",
                "success": False,
                "verified": False,
                "domain": domain,
                "service": service,
                "error": "HASS_TOKEN is not configured; no device command was sent.",
            }
        if not target_entity:
            return {
                "power_id": "PWR-240",
                "success": False,
                "verified": False,
                "domain": domain,
                "service": service,
                "error": "A target entity is required for state readback verification.",
            }

        url = f"{self.base_url}/api/services/{domain}/{service}"
        body_bytes = json.dumps(payload_data).encode("utf-8")
        req = urllib.request.Request(url, data=body_bytes, headers=self._headers(), method="POST")

        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                result_states = json.loads(resp.read().decode("utf-8"))

            readback = self.get_entity_state(target_entity)
            if not readback.get("success"):
                audit_ledger.record(
                    actor="HomeAssistantPowers",
                    action=f"CALL_SERVICE_{domain.upper()}_{service.upper()}",
                    target=str(target_entity),
                    payload=payload_data,
                    result="FAILED_VERIFICATION",
                )
                return {
                    "power_id": "PWR-240",
                    "success": False,
                    "verified": False,
                    "domain": domain,
                    "service": service,
                    "error": "Home Assistant accepted the request but state readback failed.",
                    "details": readback,
                }

            readback_state = readback.get("state")
            state_matches = (
                expected_state is None
                or (expected_state == "not_off" and readback_state not in {"off", "unknown", "unavailable", None})
                or readback_state == expected_state
            )
            if not state_matches:
                audit_ledger.record(
                    actor="HomeAssistantPowers",
                    action=f"CALL_SERVICE_{domain.upper()}_{service.upper()}",
                    target=str(target_entity),
                    payload=payload_data,
                    result="FAILED_VERIFICATION",
                )
                return {
                    "power_id": "PWR-240",
                    "success": False,
                    "verified": False,
                    "domain": domain,
                    "service": service,
                    "expected_state": expected_state,
                    "verified_state": readback_state,
                    "error": "Home Assistant state did not match the expected state.",
                }

            audit_ledger.record(
                actor="HomeAssistantPowers",
                action=f"CALL_SERVICE_{domain.upper()}_{service.upper()}",
                target=str(target_entity),
                payload=payload_data,
                result="SUCCESS",
            )
            return {
                "power_id": "PWR-240",
                "success": True,
                "verified": True,
                "domain": domain,
                "service": service,
                "service_data": payload_data,
                "verified_state": readback_state,
                "result_states_count": len(result_states) if isinstance(result_states, list) else 0,
            }
        except Exception as e:
            logger.warning(f"Error calling Home Assistant service {domain}.{service}: {e}")
            return {
                "power_id": "PWR-240",
                "success": False,
                "verified": False,
                "domain": domain,
                "service": service,
                "error": str(e),
            }


homeassistant_powers = HomeAssistantPowers()
