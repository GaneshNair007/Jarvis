"""
JARVIS Instant Local Command Powers (PWR-027 to PWR-049)
Deterministic, zero-latency system powers that bypass LLM inference:
  - App launching and switching
  - Audio and volume controls
  - Screen locking and display toggles
  - Clipboard operations
"""

import subprocess
import os
from typing import Dict, Any

from jarvis.constants import DEFAULT_APP_COMMANDS

class InstantPowers:
    @staticmethod
    def lock_workstation() -> Dict[str, Any]:
        """PWR-035: Lock the local operating system workstation."""
        try:
            if os.name == "nt":
                import ctypes
                ctypes.windll.user32.LockWorkStation()
            else:
                subprocess.run(["xdg-screensaver", "lock"], check=False)
            return {"status": "success", "action": "lock_workstation", "message": "Workstation locked successfully"}
        except Exception as e:
            return {"status": "error", "message": f"Failed to lock workstation: {e}"}

    @staticmethod
    def get_clipboard() -> Dict[str, Any]:
        """PWR-038: Read current text content from the OS clipboard."""
        try:
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            text = root.clipboard_get()
            root.destroy()
            return {"status": "success", "clipboard_text": text}
        except Exception as e:
            return {"status": "error", "message": f"Clipboard empty or inaccessible: {e}"}

    @staticmethod
    def launch_app(app_name: str) -> Dict[str, Any]:
        """PWR-027: Launch an approved desktop application."""
        allowed_apps = DEFAULT_APP_COMMANDS
        cmd = allowed_apps.get(app_name.lower().strip())
        if not cmd:
            return {"status": "error", "message": f"Application '{app_name}' is not in the allowed application list"}

        try:
            subprocess.Popen([cmd], shell=(os.name == "nt"))
            return {"status": "success", "launched": app_name, "command": cmd}
        except Exception as e:
            return {"status": "error", "message": f"Failed to launch '{app_name}': {e}"}

instant_powers = InstantPowers()
