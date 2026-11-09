"""JARVIS app connectors (launch + delegate). See app_connector for the contract."""

from jarvis.automation.app_connector import (
    match_app_intent,
    launch_app,
    launch_in_console,
    opencode_delegate,
    antigravity_delegate,
    set_clipboard,
)

__all__ = [
    "match_app_intent",
    "launch_app",
    "launch_in_console",
    "opencode_delegate",
    "antigravity_delegate",
    "set_clipboard",
]
