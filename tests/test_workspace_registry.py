"""
Tests for Spoken Workspace Registry (jarvis/core/workspace_registry.py)
"""

import tempfile
import json
from pathlib import Path
from jarvis.core.workspace_registry import WorkspaceRegistry, resolve_workspace
from jarvis.automation.app_connector import match_app_intent


def test_workspace_registry_defaults():
    registry = WorkspaceRegistry(config_path="non_existent_config.json")
    workspaces = registry.list_workspaces()
    assert "jarvis" in workspaces
    assert "switch-ai" in workspaces
    assert "carbonterra" in workspaces


def test_workspace_alias_resolution():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "workspaces.json"
        project_dir = Path(tmpdir) / "projects" / "my-awesome-project"
        project_dir.mkdir(parents=True)

        data = {
            "workspaces": {
                "my-project": {
                    "path": str(project_dir),
                    "aliases": ["my project", "awesome project", "awesome"],
                }
            }
        }
        config_file.write_text(json.dumps(data), encoding="utf-8")

        reg = WorkspaceRegistry(config_path=str(config_file))

        # Test exact match
        assert reg.resolve("my-project") == str(project_dir)
        # Test spoken aliases with varying case and spacing
        assert reg.resolve("my project") == str(project_dir)
        assert reg.resolve("Awesome Project") == str(project_dir)
        assert reg.resolve("awesome") == str(project_dir)

        # Test existing path resolves directly
        assert reg.resolve(str(project_dir)) == str(project_dir)

        # Test unknown alias returns None
        assert reg.resolve("unknown-alien-workspace") is None


def test_app_connector_resolves_spoken_workspace():
    # "run opencode in switch-ai"
    intent = match_app_intent("run opencode in switch-ai")
    assert intent is not None
    assert intent["kind"] == "opencode_in"
    # Canonical path should be resolved
    assert "switch-ai" in intent["path"]
