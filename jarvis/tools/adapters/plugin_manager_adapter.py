"""JARVIS Plugin Manager Adapter.

Exposes the core plugins/loader.py subsystem to the Jarvis Tool Registry and Dashboard.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from plugins.loader import PluginRegistry, plugin_loader, plugin_registry


class PluginManagerAdapter:
    """Tool adapter allowing Jarvis agents to inspect and toggle system plugins."""

    def __init__(self, registry: Optional[PluginRegistry] = None):
        self.registry = registry or plugin_registry
        self.loader = plugin_loader

    def list_plugins(self) -> List[Dict[str, Any]]:
        """Returns catalog of all discovered and loaded plugins."""
        self.loader.load_all()
        return self.registry.dashboard_state().get("plugins", [])

    def get_plugin_details(self, plugin_name: str) -> Optional[Dict[str, Any]]:
        """Retrieves metadata and powers for a specific plugin."""
        plugin = self.registry.get_by_name(plugin_name)
        if not plugin:
            return None
        return {
            "name": plugin.manifest.name,
            "display_name": plugin.manifest.display_name,
            "version": plugin.manifest.version,
            "description": plugin.manifest.description,
            "enabled": plugin.manifest.enabled,
            "approval_tier": plugin.manifest.approval_tier,
            "powers": plugin.manifest.powers,
            "required_env": plugin.manifest.required_env,
        }

    def set_plugin_state(self, plugin_name: str, enabled: bool) -> bool:
        """Enables or disables a plugin at runtime."""
        plugin = self.registry.get_by_name(plugin_name)
        if not plugin:
            return False
        if enabled:
            return self.registry.enable(plugin.plugin_id)
        else:
            return self.registry.disable(plugin.plugin_id)
