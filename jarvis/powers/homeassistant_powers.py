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
                "status": "unconfigured",
                "base_url": self.base_url,
                "error": "HASS_TOKEN is not configured; refusing unauthenticated device access.",
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
                "status": "unavailable",
                "entity_id": entity_id,
                "error": f"Connection failed: {e}",
            }

    def list_entities(self, domain_filter: Optional[str] = None) -> Dict[str, Any]:
        """PWR-239: Queries all available entity states from Home Assistant."""
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

                verified = bool(readback_state is not None) if target_entity else False
                if target_entity and not verified:
                    return {
                        "power_id": "PWR-240",
                        "success": False,
                        "status": "verification_failed",
                        "domain": domain,
                        "service": service,
                        "service_data": payload_data,
                        "error": f"Home Assistant accepted the service call but state readback failed for {target_entity}.",
                    }

                audit_ledger.record(
                    actor="HomeAssistantPowers",
                    action=f"CALL_SERVICE_{domain.upper()}_{service.upper()}",
                    target=str(target_entity or domain),
                    payload=payload_data,
                    result="VERIFIED" if verified else "ACCEPTED_UNVERIFIED",
                )

                return {
                    "power_id": "PWR-240",
                    "success": True,
                    "verified": verified,
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


    def control_climate(self, action: str, entity_id: Optional[str] = None) -> Dict[str, Any]:
        """Control a real Home Assistant climate entity and verify its resulting state.

        This method deliberately has no in-memory/demo fallback. A command is
        successful only when Home Assistant is authenticated, the target is
        uniquely resolved, the service call is accepted, and state readback
        confirms the requested on/off state.
        """
        normalized_action = (action or "").strip().lower()
        if normalized_action not in {"on", "off"}:
            return {
                "power_id": "PWR-257",
                "success": False,
                "status": "invalid_request",
                "error": "Climate action must be 'on' or 'off'.",
            }

        connection = self.check_connection()
        if not connection.get("connected"):
            return {
                "power_id": "PWR-257",
                "success": False,
                "status": "unavailable",
                "error": connection.get("error", "Home Assistant is unavailable."),
                "setup": "Configure HASS_URL and HASS_TOKEN, then verify Home Assistant is reachable.",
            }

        listed = self.list_entities("climate")
        if not listed.get("success"):
            return {
                "power_id": "PWR-257",
                "success": False,
                "status": "unavailable",
                "error": listed.get("error", "Unable to discover climate entities."),
            }

        entities = listed.get("entities", [])
        if entity_id:
            matches = [item for item in entities if item.get("entity_id") == entity_id]
        else:
            matches = [
                item for item in entities
                if any(term in f"{item.get('entity_id', '')} {item.get('friendly_name', '')}".lower()
                       for term in ("ac", "air conditioner", "air conditioning"))
            ]
            if not matches and len(entities) == 1:
                matches = entities

        if len(matches) != 1:
            return {
                "power_id": "PWR-257",
                "success": False,
                "status": "needs_configuration" if not matches else "ambiguous_device",
                "error": "Could not uniquely identify the room AC climate entity.",
                "available_climate_entities": entities,
            }

        target = matches[0]["entity_id"]
        service = "turn_on" if normalized_action == "on" else "turn_off"
        result = self.call_service(
            domain="climate",
            service=service,
            service_data={"entity_id": target},
            verify_entity_id=target,
        )
        if not result.get("success") or not result.get("verified"):
            return {
                "power_id": "PWR-257",
                "success": False,
                "status": result.get("status", "verification_failed"),
                "entity_id": target,
                "error": result.get("error", "The device state could not be verified."),
                "service_result": result,
            }

        actual_state = str(result.get("verified_state", "")).lower()
        state_matches = actual_state == "off" if normalized_action == "off" else actual_state not in {
            "off", "unknown", "unavailable", ""
        }
        if not state_matches:
            return {
                "power_id": "PWR-257",
                "success": False,
                "status": "verification_failed",
                "entity_id": target,
                "verified_state": actual_state,
                "error": f"Requested climate power {normalized_action}, but Home Assistant reports '{actual_state}'.",
            }

        return {
            "power_id": "PWR-257",
            "success": True,
            "status": "success",
            "verified": True,
            "entity_id": target,
            "state": actual_state,
            "message": f"AC {normalized_action} confirmed by Home Assistant ({target}: {actual_state}).",
        }


homeassistant_powers = HomeAssistantPowers()
