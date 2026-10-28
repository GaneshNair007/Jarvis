"""
JARVIS Desktop Computer Use Powers
Registers and exposes:
  - PWR-016: Active Window Tracking
  - PWR-017: Screen Region Capture & Checksum
  - PWR-018: Focus Window by Title
  - PWR-019: Safe Key Sequence / Typing
  - PWR-020: Mouse Move / Click with See-Act-Verify
"""

from typing import Dict, Any, Optional, Tuple
from jarvis.computer.desktop_worker import desktop_worker

class DesktopPowers:
    """Provides high-level power implementations for desktop automation."""

    def pwr_016_get_active_window(self) -> Dict[str, Any]:
        """PWR-016: Retrieves the active foreground window details."""
        return desktop_worker.get_active_window()

    def pwr_017_capture_screen(self, region: Optional[Tuple[int, int, int, int]] = None) -> Dict[str, Any]:
        """PWR-017: Captures screen region with SHA-256 evidence artifact."""
        return desktop_worker.capture_screen(region=region)

    def pwr_018_focus_window(self, title_pattern: str) -> Dict[str, Any]:
        """PWR-018: Brings window matching title pattern to foreground."""
        success = desktop_worker.focus_window(title_pattern)
        return {
            "title_pattern": title_pattern,
            "focused": success,
            "active_window": desktop_worker.get_active_window()
        }

    def pwr_019_safe_type(self, text: str, interval: float = 0.02) -> Dict[str, Any]:
        """PWR-019: Types text safely into active element with see-act-verify."""
        return desktop_worker.see_act_verify(
            action="type",
            params={"text": text, "interval": interval}
        )

    def pwr_020_mouse_click(self, x: int, y: int, button: str = "left", clicks: int = 1) -> Dict[str, Any]:
        """PWR-020: Clicks at coordinates with See-Act-Verify loop."""
        return desktop_worker.see_act_verify(
            action="click",
            params={"x": x, "y": y, "button": button, "clicks": clicks}
        )

# Global Desktop Powers Instance
desktop_powers = DesktopPowers()
