"""
JARVIS Integration Registry
Central manager tracking all active, configured, and available integrations.
Synchronizes powers into the PowerRegistry and enforces system-wide safety controls.
"""

from typing import Dict, Any, List, Optional
from jarvis.core.power_registry import power_registry
from integrations.base.base_integration import BaseIntegration

class IntegrationRegistry:
    """Master registry and lifecycle coordinator for all JARVIS integrations."""

    def __init__(self):
        self._integrations: Dict[str, BaseIntegration] = {}

    def register(self, integration: BaseIntegration) -> None:
        """Registers an integration and syncs its powers to PowerRegistry."""
        iid = integration.integration_id.lower()
        self._integrations[iid] = integration

        # Sync powers into PowerRegistry
        for p in integration.list_powers():
            power_id = p.get("power_id")
            if power_id:
                # Add to initial powers map so it can be enabled/disabled via standard PowerRegistry APIs
                power_registry.initial_powers[power_id] = {
                    "power_id": power_id,
                    "name": p.get("name", power_id),
                    "category": integration.category,
                    "description": p.get("description", ""),
                    "triggers": p.get("triggers", [p.get("name", power_id)]),
                    "inputs": p.get("inputs", []),
                    "outputs": p.get("outputs", []),
                    "required_permissions": p.get("required_permissions", []),
                    "danger_level": p.get("danger_level", integration.danger_level),
                    "approval_required": p.get("approval_required", integration.default_approval_tier >= 2),
                    "enabled": integration.enabled,
                    "version": "1.0.0",
                    "dependencies": [integration.integration_id],
                    "test_status": "verified"
                }

    def unregister(self, integration_id: str) -> bool:
        """Removes an integration from the registry."""
        return self._integrations.pop(integration_id.lower(), None) is not None

    def get(self, integration_id: str) -> Optional[BaseIntegration]:
        """Retrieves an integration instance by ID."""
        return self._integrations.get(integration_id.lower())

    def list_integrations(self) -> List[Dict[str, Any]]:
        """Returns metadata summaries for all registered integrations."""
        results = []
        for iid, item in sorted(self._integrations.items()):
            results.append({
                "integration_id": item.integration_id,
                "display_name": item.display_name,
                "category": item.category,
                "description": item.description,
                "enabled": item.enabled,
                "connected": item.connected,
                "kill_switched": item.kill_switched,
                "danger_level": item.danger_level,
                "default_approval_tier": item.default_approval_tier,
                "rate_limit_rpm": item.rate_limit_rpm,
                "cost_model": item.cost_model,
                "data_sensitivity": item.data_sensitivity,
                "powers_count": len(item.list_powers()),
                "documentation_url": item.documentation_url
            })
        return results

    def list_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Filters integrations by category."""
        return [i for i in self.list_integrations() if i["category"].lower() == category.lower()]

    def connect(self, integration_id: str, credentials: Optional[Dict[str, str]] = None) -> bool:
        integ = self.get(integration_id)
        if not integ:
            return False
        return integ.connect(credentials)

    def disconnect(self, integration_id: str) -> bool:
        integ = self.get(integration_id)
        if not integ:
            return False
        return integ.disconnect()

    def enable(self, integration_id: str) -> bool:
        integ = self.get(integration_id)
        if not integ:
            return False
        integ.enable()
        # Also sync power registry
        for p in integ.list_powers():
            pid = p.get("power_id")
            if pid in power_registry.initial_powers:
                power_registry.initial_powers[pid]["enabled"] = True
        return True

    def disable(self, integration_id: str) -> bool:
        integ = self.get(integration_id)
        if not integ:
            return False
        integ.disable()
        # Also sync power registry
        for p in integ.list_powers():
            pid = p.get("power_id")
            if pid in power_registry.initial_powers:
                power_registry.initial_powers[pid]["enabled"] = False
        return True

    def trip_all_kill_switches(self, reason: str = "Global integration halt") -> Dict[str, Any]:
        """Emergency stop across every registered integration."""
        for integ in self._integrations.values():
            integ.trip_kill_switch(reason=reason)
        return {"status": "ALL_INTEGRATIONS_KILL_SWITCHED", "reason": reason}

    def reset_all_kill_switches(self) -> Dict[str, Any]:
        """Resets kill switch for all integrations."""
        for integ in self._integrations.values():
            integ.reset_kill_switch()
        return {"status": "ALL_INTEGRATIONS_RESET"}

    def health_overview(self) -> Dict[str, Any]:
        """Runs live health checks across all integrations."""
        reports = {}
        for iid, integ in self._integrations.items():
            reports[iid] = integ.health_check().model_dump()
        return {
            "total_integrations": len(self._integrations),
            "reports": reports
        }

# Global Integration Registry singleton
integration_registry = IntegrationRegistry()
