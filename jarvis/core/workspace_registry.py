"""
JARVIS Spoken Workspace Registry
Resolves spoken project aliases (e.g. "jarvis", "switch-ai", "carbonterra")
to canonical filesystem paths.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from jarvis.core.logger import get_logger

logger = get_logger("core.workspaces")


def _normalize_key(key: str) -> str:
    """Normalizes spoken alias or project key."""
    if not key:
        return ""
    text = key.lower().strip()
    text = re.sub(r"[\s_-]+", " ", text)
    return text.strip()


class WorkspaceRegistry:
    """Manages workspace paths and resolves spoken project aliases."""

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            # Default to config/workspaces.json relative to repo root
            repo_root = Path(__file__).resolve().parent.parent.parent
            self.config_path = repo_root / "config" / "workspaces.json"
        else:
            self.config_path = Path(config_path)

        self._workspaces: Dict[str, Dict[str, Any]] = {}
        self._alias_map: Dict[str, str] = {}
        self.load()

    def load(self) -> None:
        """Loads configuration from JSON file or populates defaults."""
        self._workspaces.clear()
        self._alias_map.clear()

        loaded_data = {}
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    loaded_data = data.get("workspaces", {})
            except Exception as e:
                logger.warning(f"Failed to read workspace config {self.config_path}: {e}")

        # Fallback defaults if empty
        if not loaded_data:
            repo_root = str(Path(__file__).resolve().parent.parent.parent)
            loaded_data = {
                "jarvis": {
                    "path": repo_root,
                    "aliases": ["jarvis", "jarvis core", "jarvis repo", "main"],
                },
                "switch-ai": {
                    "path": str(Path(repo_root).parent / "switch-ai"),
                    "aliases": ["switch", "switch-ai", "switch ai", "switch console"],
                },
                "carbonterra": {
                    "path": str(Path(repo_root).parent / "carbonterra"),
                    "aliases": ["carbonterra", "carbon terra", "carbon"],
                },
            }

        for name, spec in loaded_data.items():
            path_str = spec.get("path", "")
            aliases = spec.get("aliases", [])
            self.register(name, path_str, aliases)

    def register(self, name: str, path: str, aliases: Optional[List[str]] = None) -> None:
        """Registers a workspace with aliases."""
        clean_name = _normalize_key(name)
        canonical_path = os.path.normpath(path)
        self._workspaces[name] = {
            "name": name,
            "path": canonical_path,
            "aliases": aliases or [],
        }
        self._alias_map[clean_name] = canonical_path
        # Also map without hyphens / with hyphens
        self._alias_map[name.lower().strip()] = canonical_path
        if aliases:
            for alias in aliases:
                norm_alias = _normalize_key(alias)
                self._alias_map[norm_alias] = canonical_path
                self._alias_map[alias.lower().strip()] = canonical_path

    def resolve(self, spoken_or_path: str) -> Optional[str]:
        """
        Resolves a spoken phrase, project name, or filesystem path to an absolute path.
        Returns the resolved canonical path, or None if unrecognized.
        """
        if not spoken_or_path:
            return None

        candidate = spoken_or_path.strip().strip("\"'")
        # 1. If it's already an existing directory or file, resolve directly
        if os.path.exists(candidate):
            return os.path.abspath(candidate)

        # 2. Check alias map
        norm = _normalize_key(candidate)
        if norm in self._alias_map:
            return self._alias_map[norm]

        raw_lower = candidate.lower()
        if raw_lower in self._alias_map:
            return self._alias_map[raw_lower]

        # 3. Check for partial substring match in registered workspace names
        for name, spec in self._workspaces.items():
            if norm == _normalize_key(name) or norm in [_normalize_key(a) for a in spec.get("aliases", [])]:
                return spec["path"]

        return None

    def list_workspaces(self) -> Dict[str, Dict[str, Any]]:
        """Returns registered workspaces."""
        return dict(self._workspaces)


_INSTANCE: Optional[WorkspaceRegistry] = None


def get_workspace_registry() -> WorkspaceRegistry:
    """Returns singleton instance."""
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = WorkspaceRegistry()
    return _INSTANCE


def resolve_workspace(spoken_or_path: str) -> str:
    """
    Convenience function that resolves alias to canonical path,
    or falls back to original input if not matched.
    """
    reg = get_workspace_registry()
    resolved = reg.resolve(spoken_or_path)
    return resolved if resolved is not None else spoken_or_path
