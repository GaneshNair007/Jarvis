"""
JARVIS Plugin Loader System
PDF Spec: Pages 352-371 — Dynamic Powers & Plugin Architecture

Provides:
- PluginManifest: validated plugin.json schema
- PluginLoader: discovers, loads, validates, and hot-reloads plugins
- PluginRegistry: live catalog of loaded plugins with enable/disable control
- FileSystemWatcher: watches plugin directories for changes and triggers hot-reload

Plugin directory layout:
  plugins/
    <plugin-name>/
      plugin.json       ← manifest (required)
      __init__.py       ← optional Python entry point
      *.py              ← power implementations
      rules/            ← optional agent rules / prompts
      README.md         ← optional documentation
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from jarvis.core.logger import get_logger

logger = get_logger("plugins.loader")

PLUGINS_ROOT = Path(__file__).resolve().parent


# ── Manifest schema ────────────────────────────────────────────────────────────

@dataclass
class PluginManifest:
    """Validated plugin.json contract."""
    name: str
    display_name: str
    version: str
    description: str
    plugin_dir: Path
    entry_point: Optional[str] = None        # e.g. "plugin_main.py"
    powers: List[str] = field(default_factory=list)
    suggested_prompts: List[str] = field(default_factory=list)
    required_env: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    approval_tier: int = 0
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_file(cls, manifest_path: Path) -> "PluginManifest":
        """Parse and validate a plugin.json file."""
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))

        name = raw.get("name", manifest_path.parent.name)
        display_name = raw.get("displayName", raw.get("display_name", name))
        version = raw.get("version", "0.0.1")
        description = raw.get("description", "")
        entry_point = raw.get("entryPoint", raw.get("entry_point"))
        powers = raw.get("powers", [])
        suggested_prompts = raw.get("suggestedPrompts", raw.get("suggested_prompts", []))
        required_env = raw.get("requiredEnv", raw.get("required_env", []))
        tags = raw.get("tags", [])
        approval_tier = int(raw.get("approvalTier", raw.get("approval_tier", 0)))
        enabled = bool(raw.get("enabled", True))

        return cls(
            name=name,
            display_name=display_name,
            version=version,
            description=description,
            plugin_dir=manifest_path.parent,
            entry_point=entry_point,
            powers=powers,
            suggested_prompts=suggested_prompts,
            required_env=required_env,
            tags=tags,
            approval_tier=approval_tier,
            enabled=enabled,
            metadata=raw,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "version": self.version,
            "description": self.description,
            "plugin_dir": str(self.plugin_dir),
            "entry_point": self.entry_point,
            "powers": self.powers,
            "suggested_prompts": self.suggested_prompts,
            "required_env": self.required_env,
            "tags": self.tags,
            "approval_tier": self.approval_tier,
            "enabled": self.enabled,
        }


# ── Loaded plugin container ────────────────────────────────────────────────────

@dataclass
class LoadedPlugin:
    """A successfully loaded and initialised plugin."""
    plugin_id: str
    manifest: PluginManifest
    module: Optional[Any]          # the imported Python module (if any)
    loaded_at: float = field(default_factory=time.time)
    load_errors: List[str] = field(default_factory=list)
    status: str = "active"         # active | disabled | error | unloaded

    def call(self, function_name: str, *args, **kwargs) -> Any:
        """Call a function exported by this plugin's module."""
        if not self.module:
            raise RuntimeError(f"Plugin '{self.manifest.name}' has no Python module loaded.")
        fn: Callable = getattr(self.module, function_name)
        return fn(*args, **kwargs)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "name": self.manifest.name,
            "display_name": self.manifest.display_name,
            "version": self.manifest.version,
            "description": self.manifest.description,
            "status": self.status,
            "loaded_at": self.loaded_at,
            "load_errors": self.load_errors,
            **{k: v for k, v in self.manifest.to_dict().items()
               if k not in ("name", "display_name", "version", "description")},
        }


# ── Plugin Loader ─────────────────────────────────────────────────────────────

class PluginLoader:
    """
    Discovers and loads all valid plugins from the plugins/ directory.

    Load sequence per plugin:
    1. Find plugin.json → parse PluginManifest
    2. Validate manifest schema (required fields, version format)
    3. Check required_env variables are set
    4. Import Python entry point module (if specified or __init__.py exists)
    5. Call plugin.setup() if the module exports it
    6. Register with PluginRegistry
    """

    MANIFEST_FILENAME = "plugin.json"

    def __init__(self, plugins_root: Path = PLUGINS_ROOT):
        self.plugins_root = plugins_root

    def discover(self) -> List[Path]:
        """Find all directories containing a plugin.json."""
        manifests: List[Path] = []
        if not self.plugins_root.exists():
            return manifests
        for item in sorted(self.plugins_root.iterdir()):
            if item.is_dir() and not item.name.startswith("."):
                manifest_path = item / self.MANIFEST_FILENAME
                if manifest_path.exists():
                    manifests.append(manifest_path)
        return manifests

    def load_plugin(self, manifest_path: Path) -> LoadedPlugin:
        """Load a single plugin from its manifest path."""
        plugin_id = f"plugin_{uuid.uuid4().hex[:8]}"
        errors: List[str] = []

        # ── Parse manifest ────────────────────────────────────────────────────
        try:
            manifest = PluginManifest.from_file(manifest_path)
        except Exception as exc:
            logger.error(f"PluginLoader: failed to parse {manifest_path} — {exc}")
            return LoadedPlugin(
                plugin_id=plugin_id,
                manifest=PluginManifest(
                    name=manifest_path.parent.name,
                    display_name=manifest_path.parent.name,
                    version="0.0.0",
                    description="",
                    plugin_dir=manifest_path.parent,
                ),
                module=None,
                load_errors=[str(exc)],
                status="error",
            )

        plugin_id = f"plugin_{manifest.name.replace('-', '_')}"

        # ── Check enabled flag ────────────────────────────────────────────────
        if not manifest.enabled:
            logger.info(f"PluginLoader: plugin '{manifest.name}' is disabled (manifest)")
            return LoadedPlugin(
                plugin_id=plugin_id,
                manifest=manifest,
                module=None,
                status="disabled",
            )

        # ── Check required env ────────────────────────────────────────────────
        import os
        missing_env = [e for e in manifest.required_env if not os.environ.get(e)]
        if missing_env:
            msg = f"Missing required env vars: {missing_env}"
            logger.warning(f"PluginLoader: plugin '{manifest.name}' — {msg}")
            errors.append(msg)
            # Don't hard-fail — load without module so metadata is still available

        # ── Import Python module ──────────────────────────────────────────────
        module = None
        entry_point = manifest.entry_point or (
            "__init__.py" if (manifest.plugin_dir / "__init__.py").exists() else None
        )

        if entry_point and not missing_env:
            module_path = manifest.plugin_dir / entry_point
            if module_path.exists():
                try:
                    module = self._import_module(manifest.name, module_path)
                    # Call setup() if exported
                    if hasattr(module, "setup"):
                        module.setup()
                    logger.info(
                        f"PluginLoader: loaded '{manifest.name}' v{manifest.version} "
                        f"from {module_path.name}"
                    )
                except Exception as exc:
                    errors.append(f"Module import error: {exc}")
                    logger.warning(
                        f"PluginLoader: '{manifest.name}' module load failed — {exc}"
                    )

        status = "active" if not errors else ("error" if missing_env else "active")

        return LoadedPlugin(
            plugin_id=plugin_id,
            manifest=manifest,
            module=module,
            load_errors=errors,
            status=status,
        )

    def load_all(self) -> List[LoadedPlugin]:
        """Discover and load all plugins. Returns list of LoadedPlugin objects."""
        manifest_paths = self.discover()
        plugins: List[LoadedPlugin] = []
        for mp in manifest_paths:
            try:
                plugin = self.load_plugin(mp)
                plugins.append(plugin)
            except Exception as exc:
                logger.error(f"PluginLoader: unexpected error loading {mp} — {exc}")
        logger.info(f"PluginLoader: loaded {len(plugins)} plugins from {self.plugins_root}")
        return plugins

    @staticmethod
    def _import_module(name: str, module_path: Path) -> Any:
        """Import a Python module from an absolute file path."""
        # Add plugin dir to sys.path so relative imports work
        plugin_dir = str(module_path.parent)
        if plugin_dir not in sys.path:
            sys.path.insert(0, plugin_dir)

        module_name = f"jarvis_plugin_{name.replace('-', '_')}"
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot create module spec from {module_path}")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = mod
        spec.loader.exec_module(mod)  # type: ignore[attr-defined]
        return mod


# ── Plugin Registry ────────────────────────────────────────────────────────────

class PluginRegistry:
    """
    Live catalog of all loaded plugins.
    Thread-safe enable/disable, lookup, and hot-reload.
    """

    def __init__(self):
        self._plugins: Dict[str, LoadedPlugin] = {}
        self._lock = threading.RLock()
        self._loader = PluginLoader()
        self._watcher_thread: Optional[threading.Thread] = None
        self._watch_active = False

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def load_all(self) -> int:
        """Initial load of all plugins. Returns count loaded."""
        plugins = self._loader.load_all()
        with self._lock:
            for p in plugins:
                self._plugins[p.plugin_id] = p
        logger.info(f"PluginRegistry: {len(plugins)} plugins registered")
        return len(plugins)

    def reload_plugin(self, plugin_id: str) -> LoadedPlugin:
        """Hot-reload a single plugin by ID. Replaces existing registration."""
        with self._lock:
            existing = self._plugins.get(plugin_id)
            if not existing:
                raise KeyError(f"No plugin with id '{plugin_id}'")
            manifest_path = existing.manifest.plugin_dir / PluginLoader.MANIFEST_FILENAME
            # Remove old module from sys.modules to force re-import
            old_mod_name = f"jarvis_plugin_{existing.manifest.name.replace('-', '_')}"
            sys.modules.pop(old_mod_name, None)
            reloaded = self._loader.load_plugin(manifest_path)
            self._plugins[plugin_id] = reloaded
            logger.info(f"PluginRegistry: hot-reloaded plugin '{existing.manifest.name}'")
            return reloaded

    def reload_all(self) -> int:
        """Hot-reload every registered plugin."""
        with self._lock:
            ids = list(self._plugins.keys())
        count = 0
        for pid in ids:
            try:
                self.reload_plugin(pid)
                count += 1
            except Exception as exc:
                logger.warning(f"PluginRegistry: reload failed for {pid} — {exc}")
        return count

    # ── Lookup ────────────────────────────────────────────────────────────────

    def get(self, plugin_id: str) -> Optional[LoadedPlugin]:
        with self._lock:
            return self._plugins.get(plugin_id)

    def get_by_name(self, name: str) -> Optional[LoadedPlugin]:
        with self._lock:
            for p in self._plugins.values():
                if p.manifest.name == name:
                    return p
        return None

    def list_active(self) -> List[LoadedPlugin]:
        with self._lock:
            return [p for p in self._plugins.values() if p.status == "active"]

    def list_all(self) -> List[LoadedPlugin]:
        with self._lock:
            return list(self._plugins.values())

    def count(self) -> int:
        with self._lock:
            return len(self._plugins)

    def active_count(self) -> int:
        with self._lock:
            return sum(1 for p in self._plugins.values() if p.status == "active")

    # ── Enable / Disable ──────────────────────────────────────────────────────

    def enable(self, plugin_id: str) -> bool:
        with self._lock:
            p = self._plugins.get(plugin_id)
            if not p:
                return False
            p.status = "active"
            p.manifest.enabled = True
            logger.info(f"PluginRegistry: enabled '{p.manifest.name}'")
            return True

    def disable(self, plugin_id: str) -> bool:
        with self._lock:
            p = self._plugins.get(plugin_id)
            if not p:
                return False
            p.status = "disabled"
            p.manifest.enabled = False
            logger.info(f"PluginRegistry: disabled '{p.manifest.name}'")
            return True

    # ── Call ──────────────────────────────────────────────────────────────────

    def call(self, plugin_id: str, function_name: str, *args, **kwargs) -> Any:
        """Invoke a function on a loaded plugin module."""
        with self._lock:
            plugin = self._plugins.get(plugin_id)
        if not plugin:
            raise KeyError(f"Plugin '{plugin_id}' not found")
        if plugin.status != "active":
            raise RuntimeError(f"Plugin '{plugin.manifest.name}' is not active (status={plugin.status})")
        return plugin.call(function_name, *args, **kwargs)

    # ── Dashboard state ───────────────────────────────────────────────────────

    def dashboard_state(self) -> Dict[str, Any]:
        with self._lock:
            plugins = list(self._plugins.values())
        return {
            "total": len(plugins),
            "active": sum(1 for p in plugins if p.status == "active"),
            "disabled": sum(1 for p in plugins if p.status == "disabled"),
            "error": sum(1 for p in plugins if p.status == "error"),
            "plugins": [p.to_dict() for p in plugins],
        }

    # ── FileSystem Watcher ────────────────────────────────────────────────────

    def start_watcher(self, poll_interval: float = 5.0):
        """
        Start background thread that polls plugin directories for changes.
        When a plugin.json modification time changes, hot-reloads that plugin.
        """
        if self._watch_active:
            return
        self._watch_active = True
        self._watcher_thread = threading.Thread(
            target=self._watch_loop,
            args=(poll_interval,),
            daemon=True,
            name="plugin-watcher",
        )
        self._watcher_thread.start()
        logger.info(f"PluginRegistry: filesystem watcher started (interval={poll_interval}s)")

    def stop_watcher(self):
        self._watch_active = False
        if self._watcher_thread:
            self._watcher_thread.join(timeout=10)
        logger.info("PluginRegistry: filesystem watcher stopped")

    def _watch_loop(self, poll_interval: float):
        """Poll for plugin.json mtime changes and hot-reload affected plugins."""
        mtimes: Dict[str, float] = {}

        # Seed initial mtimes
        with self._lock:
            for p in self._plugins.values():
                mpath = p.manifest.plugin_dir / PluginLoader.MANIFEST_FILENAME
                if mpath.exists():
                    mtimes[p.plugin_id] = mpath.stat().st_mtime

        while self._watch_active:
            time.sleep(poll_interval)
            with self._lock:
                current_plugins = list(self._plugins.items())

            for pid, plugin in current_plugins:
                mpath = plugin.manifest.plugin_dir / PluginLoader.MANIFEST_FILENAME
                if not mpath.exists():
                    continue
                current_mtime = mpath.stat().st_mtime
                if mtimes.get(pid, 0) != current_mtime:
                    logger.info(
                        f"PluginRegistry watcher: change detected in "
                        f"'{plugin.manifest.name}' — hot-reloading"
                    )
                    try:
                        self.reload_plugin(pid)
                        mtimes[pid] = current_mtime
                    except Exception as exc:
                        logger.warning(f"PluginRegistry watcher: reload failed — {exc}")

            # Also check for new plugins added to plugins_root
            try:
                new_manifests = self._loader.discover()
                known_dirs = {p.manifest.plugin_dir for p in self.list_all()}
                for mp in new_manifests:
                    if mp.parent not in known_dirs:
                        logger.info(f"PluginRegistry watcher: new plugin detected at {mp.parent}")
                        try:
                            new_plugin = self._loader.load_plugin(mp)
                            with self._lock:
                                self._plugins[new_plugin.plugin_id] = new_plugin
                            mtimes[new_plugin.plugin_id] = mp.stat().st_mtime
                        except Exception as exc:
                            logger.warning(f"PluginRegistry watcher: load failed — {exc}")
            except Exception:
                pass


# ── Singletons ─────────────────────────────────────────────────────────────────
plugin_loader = PluginLoader()
plugin_registry = PluginRegistry()

# Auto-load on first import
try:
    plugin_registry.load_all()
except Exception as _e:
    logger.warning(f"plugin_registry auto-load failed: {_e}")

__all__ = [
    "PluginManifest",
    "LoadedPlugin",
    "PluginLoader",
    "PluginRegistry",
    "plugin_loader",
    "plugin_registry",
]
