"""Unit tests for PluginManagerAdapter."""

from jarvis.tools.adapters.plugin_manager_adapter import PluginManagerAdapter


def test_plugin_manager_adapter_lifecycle():
    adapter = PluginManagerAdapter()
    plugins = adapter.list_plugins()
    assert isinstance(plugins, list)

    if len(plugins) > 0:
        first_plugin = plugins[0]
        name = first_plugin["name"]
        details = adapter.get_plugin_details(name)
        assert details is not None
        assert details["name"] == name
        assert "enabled" in details
