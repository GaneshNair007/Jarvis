"""JARVIS Home Assistant Local REST Powers (PWR-238 to PWR-252).

Provides authenticated local REST API integration with Home Assistant (e.g. http://127.0.0.1:8123),
entity status querying, service invocation with state-transition readback verification,
and offline fallback handling.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
import urllib.error
import urllib.request
import json

from jarvis.config import settings
from jarvis.core.logger import get_logger
from jarvis.core.audit import audit_ledger

logger = get_logger("powers.homeassistant")


class HomeAssistantPowers:
    """Implementations for local Home Assistant REST API interactions."""

    def _frozen_response(self, power_id: str = "PWR-238") -> Dict[str, Any]:
        return {
            "power_id": power_id,
            "status": "FROZEN",
            "connected": False,
            "success": False,
            "message": "Home Assistant integration is frozen per product directive. JARVIS operates exclusively as a personal AI assistant.",
            "fabricated": False,
        }

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
        if not getattr(settings, "enable_smart_home", False):
            return self._frozen_response("PWR-238")
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
        if not getattr(settings, "enable_smart_home", False):
            res = self._frozen_response("PWR-238")
            res["entity_id"] = entity_id
            return res
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
            # Fallback for disconnected / demo scenarios
            return {
                "power_id": "PWR-238",
                "success": False,
                "entity_id": entity_id,
                "error": f"Connection failed: {e}",
                "simulated_fallback": {
                    "entity_id": entity_id,
                    "state": "unknown (offline)",
                },
            }

    def list_entities(self, domain_filter: Optional[str] = None) -> Dict[str, Any]:
        """PWR-239: Queries all available entity states from Home Assistant."""
        if not getattr(settings, "enable_smart_home", False):
            return self._frozen_response("PWR-239")
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
    ) -> Dict[str, Any]:
        """PWR-240: Calls a Home Assistant service and verifies state readback."""
        if not getattr(settings, "enable_smart_home", False):
            return self._frozen_response("PWR-240")
        payload_data = service_data or {}
        target_entity = verify_entity_id or payload_data.get("entity_id")

        url = f"{self.base_url}/api/services/{domain}/{service}"
        body_bytes = json.dumps(payload_data).encode("utf-8")
        req = urllib.request.Request(url, data=body_bytes, headers=self._headers(), method="POST")

        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                result_states = json.loads(resp.read().decode("utf-8"))

                # Readback verification
                readback_state = None
                if target_entity:
                    readback = self.get_entity_state(target_entity)
                    if readback.get("success"):
                        readback_state = readback.get("state")

                audit_ledger.record(
                    actor="HomeAssistantPowers",
                    action=f"CALL_SERVICE_{domain.upper()}_{service.upper()}",
                    target=str(target_entity or domain),
                    payload=payload_data,
                    result="SUCCESS",
                )

                return {
                    "power_id": "PWR-240",
                    "success": True,
                    "domain": domain,
                    "service": service,
                    "service_data": payload_data,
                    "verified_state": readback_state,
                    "result_states_count": len(result_states),
                }
        except Exception as e:
            logger.warning(f"Error calling Home Assistant service {domain}.{service}: {e}")
            return {
                "power_id": "PWR-240",
                "success": False,
                "domain": domain,
                "service": service,
                "error": str(e),
            }


homeassistant_powers = HomeAssistantPowers()
