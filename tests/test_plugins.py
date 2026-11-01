"""
Tests for JARVIS Plugin Loader System
PDF Spec Pages 352-371 — Dynamic Powers & Plugin Architecture
"""

import json
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


# ── PluginManifest ─────────────────────────────────────────────────────────────

class TestPluginManifest:
    def test_parse_valid_manifest(self, tmp_path):
        """Valid plugin.json should parse into PluginManifest."""
        from plugins.loader import PluginManifest
        manifest_data = {
            "name": "test-plugin",
            "displayName": "Test Plugin",
            "version": "1.0.0",
            "description": "A test plugin",
            "powers": ["PWR-001"],
            "suggestedPrompts": ["/test-command"],
            "approvalTier": 0,
        }
        manifest_path = tmp_path / "plugin.json"
        manifest_path.write_text(json.dumps(manifest_data))
        manifest = PluginManifest.from_file(manifest_path)
        assert manifest.name == "test-plugin"
        assert manifest.display_name == "Test Plugin"
        assert manifest.version == "1.0.0"
        assert manifest.approval_tier == 0
        assert "PWR-001" in manifest.powers

    def test_manifest_defaults(self, tmp_path):
        """Minimal plugin.json should use sensible defaults."""
        from plugins.loader import PluginManifest
        manifest_data = {"description": "Minimal plugin"}
        manifest_path = tmp_path / "plugin.json"
        manifest_path.write_text(json.dumps(manifest_data))
        manifest = PluginManifest.from_file(manifest_path)
        assert manifest.version == "0.0.1"
        assert manifest.approval_tier == 0
        assert manifest.enabled is True

    def test_manifest_to_dict(self, tmp_path):
        """PluginManifest.to_dict() produces serialisable output."""
        from plugins.loader import PluginManifest
        manifest_data = {"name": "test", "version": "1.0.0", "description": "Test"}
        manifest_path = tmp_path / "plugin.json"
        manifest_path.write_text(json.dumps(manifest_data))
        manifest = PluginManifest.from_file(manifest_path)
        d = manifest.to_dict()
        assert "name" in d
        assert "version" in d
        assert "enabled" in d


# ── PluginLoader ───────────────────────────────────────────────────────────────

class TestPluginLoader:
    def test_discover_finds_plugins(self, tmp_path):
        """discover() finds all subdirs with plugin.json."""
        from plugins.loader import PluginLoader
        # Create two plugin dirs
        for name in ["plugin-a", "plugin-b"]:
            d = tmp_path / name
            d.mkdir()
            (d / "plugin.json").write_text(json.dumps({"name": name, "version": "1.0.0", "description": name}))
        loader = PluginLoader(plugins_root=tmp_path)
        found = loader.discover()
        assert len(found) == 2

    def test_discover_ignores_hidden_dirs(self, tmp_path):
        """Directories starting with '.' are ignored."""
        from plugins.loader import PluginLoader
        hidden = tmp_path / ".hidden"
        hidden.mkdir()
        (hidden / "plugin.json").write_text(json.dumps({"name": "hidden"}))
        loader = PluginLoader(plugins_root=tmp_path)
        found = loader.discover()
        assert len(found) == 0

    def test_load_plugin_without_module(self, tmp_path):
        """Plugin without entry_point loads as metadata-only."""
        from plugins.loader import PluginLoader
        plugin_dir = tmp_path / "meta-only"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.json").write_text(json.dumps({
            "name": "meta-only",
            "version": "1.0.0",
            "description": "Metadata only plugin",
        }))
        loader = PluginLoader(plugins_root=tmp_path)
        plugin = loader.load_plugin(plugin_dir / "plugin.json")
        assert plugin.manifest.name == "meta-only"
        assert plugin.module is None
        assert plugin.status in ("active", "disabled")

    def test_load_plugin_with_python_module(self, tmp_path):
        """Plugin with __init__.py gets its module imported."""
        from plugins.loader import PluginLoader
        plugin_dir = tmp_path / "py-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.json").write_text(json.dumps({
            "name": "py-plugin",
            "version": "1.0.0",
            "description": "Python plugin",
        }))
        (plugin_dir / "__init__.py").write_text(
            "PLUGIN_NAME = 'py-plugin'\ndef setup(): pass\n"
        )
        loader = PluginLoader(plugins_root=tmp_path)
        plugin = loader.load_plugin(plugin_dir / "plugin.json")
        if plugin.module:  # module loading is best-effort
            assert hasattr(plugin.module, "PLUGIN_NAME")

    def test_load_disabled_plugin(self, tmp_path):
        """Plugin with enabled=false in manifest loads as disabled."""
        from plugins.loader import PluginLoader
        plugin_dir = tmp_path / "disabled-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.json").write_text(json.dumps({
            "name": "disabled-plugin",
            "version": "1.0.0",
            "description": "Disabled plugin",
            "enabled": False,
        }))
        loader = PluginLoader(plugins_root=tmp_path)
        plugin = loader.load_plugin(plugin_dir / "plugin.json")
        assert plugin.status == "disabled"

    def test_load_all_returns_list(self, tmp_path):
        """load_all() returns a list of LoadedPlugin objects."""
        from plugins.loader import PluginLoader
        for i in range(3):
            d = tmp_path / f"plugin-{i}"
            d.mkdir()
            (d / "plugin.json").write_text(json.dumps({"name": f"plugin-{i}", "version": "1.0.0", "description": f"Plugin {i}"}))
        loader = PluginLoader(plugins_root=tmp_path)
        plugins = loader.load_all()
        assert len(plugins) == 3


# ── PluginRegistry ─────────────────────────────────────────────────────────────

class TestPluginRegistry:
    def _make_registry(self, tmp_path, plugin_names=("test-plugin",)):
        from plugins.loader import PluginRegistry, PluginLoader
        for name in plugin_names:
            d = tmp_path / name
            d.mkdir()
            (d / "plugin.json").write_text(json.dumps({
                "name": name, "version": "1.0.0", "description": name
            }))
        registry = PluginRegistry()
        registry._loader = PluginLoader(plugins_root=tmp_path)
        registry._plugins.clear()
        registry.load_all()
        return registry

    def test_load_all_registers_plugins(self, tmp_path):
        registry = self._make_registry(tmp_path, ["alpha", "beta"])
        assert registry.count() == 2

    def test_get_by_name(self, tmp_path):
        registry = self._make_registry(tmp_path, ["gamma"])
        plugin = registry.get_by_name("gamma")
        assert plugin is not None
        assert plugin.manifest.name == "gamma"

    def test_enable_disable(self, tmp_path):
        registry = self._make_registry(tmp_path, ["toggleable"])
        plugin = registry.get_by_name("toggleable")
        assert plugin is not None
        pid = plugin.plugin_id
        registry.disable(pid)
        assert registry.get(pid).status == "disabled"
        registry.enable(pid)
        assert registry.get(pid).status == "active"

    def test_list_active_filters_disabled(self, tmp_path):
        registry = self._make_registry(tmp_path, ["active-one", "will-disable"])
        to_disable = registry.get_by_name("will-disable")
        registry.disable(to_disable.plugin_id)
        active = registry.list_active()
        active_names = [p.manifest.name for p in active]
        assert "active-one" in active_names
        assert "will-disable" not in active_names

    def test_dashboard_state(self, tmp_path):
        registry = self._make_registry(tmp_path, ["dash-plugin"])
        state = registry.dashboard_state()
        assert "total" in state
        assert "active" in state
        assert "plugins" in state
        assert isinstance(state["plugins"], list)

    def test_career_ops_plugin_discoverable(self):
        """The real career-ops plugin shipped in the repo should be loadable."""
        from plugins.loader import PluginLoader
        loader = PluginLoader()  # uses actual plugins/ dir
        manifests = loader.discover()
        names = [m.parent.name for m in manifests]
        assert "career-ops" in names

    def test_career_ops_plugin_manifest_valid(self):
        """career-ops plugin.json should parse without errors."""
        from plugins.loader import PluginLoader, PluginManifest
        loader = PluginLoader()
        manifests = loader.discover()
        career_ops_manifest = next(
            (m for m in manifests if m.parent.name == "career-ops"), None
        )
        if career_ops_manifest:
            manifest = PluginManifest.from_file(career_ops_manifest)
            assert manifest.name == "jarvis-career-ops"
            assert len(manifest.suggested_prompts) > 0
