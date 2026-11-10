"""JARVIS Cloned Capability Adapters."""

from jarvis.tools.adapters.claude_code_style_adapter import ClaudeCodeStyleAdapter
from jarvis.tools.adapters.generative_ui_adapter import GenerativeUIAdapter
from jarvis.tools.adapters.workflow_migrator_adapter import WorkflowMigratorAdapter
from jarvis.tools.adapters.obscure_browser_adapter import ObscureBrowserAdapter
from jarvis.tools.adapters.plugin_manager_adapter import PluginManagerAdapter

__all__ = [
    "ClaudeCodeStyleAdapter",
    "GenerativeUIAdapter",
    "WorkflowMigratorAdapter",
    "ObscureBrowserAdapter",
    "PluginManagerAdapter",
]
