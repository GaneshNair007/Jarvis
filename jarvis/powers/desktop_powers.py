"""
JARVIS Desktop Computer Use Powers
Registers and exposes:
  - Dynamic Windows Application Path Resolution (4-tier resolution)
  - PWR-016: Active Window Tracking
  - PWR-017: Screen Region Capture & Checksum
  - PWR-018: Focus Window by Title
  - PWR-019: Safe Key Sequence / Typing
  - PWR-020: Mouse Move / Click with See-Act-Verify
"""

import glob
import os
from pathlib import Path
import shutil
from typing import Any, Dict, List, Optional, Tuple

from jarvis.computer.desktop_worker import desktop_worker

try:
    import winreg
    HAS_WINREG = True
except ImportError:
    winreg = None
    HAS_WINREG = False

# Destructive binaries forbidden from resolution by safety policy
BLOCKED_SYSTEM_BINARIES = {
    "format.com", "format.exe", "format",
    "vssadmin.exe", "vssadmin",
    "delpart.exe", "delpart",
    "diskpart.exe", "diskpart",
}


def resolve_app_path(app_name: str) -> Optional[Path]:
    """
    Dynamically resolves a Windows application name to its absolute executable Path.

    Resolution Order:
      1. Built-in known shortcuts (notepad, calc, explorer, powershell, cmd)
      2. Windows Registry App Paths (HKLM & HKCU)
      3. Windows Start Menu Programs (%APPDATA% & %PROGRAMDATA%)
      4. System PATH via shutil.which
    Returns None if nonexistent or if blocked by security policy.
    """
    if not app_name or not isinstance(app_name, str):
        return None

    cleaned = app_name.strip().strip('"').strip("'")
    if not cleaned or "\x00" in cleaned or "\r" in cleaned or "\n" in cleaned:
        return None

    lower_name = cleaned.lower()
    base_name = lower_name[:-4] if lower_name.endswith(".exe") else lower_name

    target_path = Path(cleaned)
    target_name = target_path.name.lower()
    target_stem = target_path.stem.lower()

    if (
        target_name in BLOCKED_SYSTEM_BINARIES
        or target_stem in BLOCKED_SYSTEM_BINARIES
        or f"{target_stem}.exe" in BLOCKED_SYSTEM_BINARIES
        or f"{target_stem}.com" in BLOCKED_SYSTEM_BINARIES
    ):
        return None

    # 1. Built-in known shortcuts
    windir = os.environ.get("WINDIR", r"C:\Windows")
    known_shortcuts = {
        "notepad": os.path.join(windir, "System32", "notepad.exe"),
        "calc": os.path.join(windir, "System32", "calc.exe"),
        "explorer": os.path.join(windir, "explorer.exe"),
        "powershell": os.path.join(windir, "System32", "WindowsPowerShell", "v1.0", "powershell.exe"),
        "cmd": os.path.join(windir, "System32", "cmd.exe"),
    }
    if base_name in known_shortcuts:
        target = Path(known_shortcuts[base_name])
        if target.exists():
            return target
        which_path = shutil.which(base_name)
        if which_path:
            return Path(which_path)

    # 2. Windows Registry App Paths (HKLM & HKCU)
    if HAS_WINREG and winreg:
        hives = [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]
        reg_subpath = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"
        candidates = [cleaned, f"{base_name}.exe", lower_name]
        for hive in hives:
            for cand in candidates:
                try:
                    with winreg.OpenKey(hive, f"{reg_subpath}\\{cand}") as key:
                        val, _ = winreg.QueryValueEx(key, "")
                        if val:
                            path_str = str(val).strip().strip('"').strip("'")
                            target = Path(path_str)
                            if target.exists():
                                return target
                except (OSError, FileNotFoundError):
                    pass

    # 3. Windows Start Menu Programs (%APPDATA% & %PROGRAMDATA%)
    start_dirs = [
        os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs"),
        os.path.join(os.environ.get("PROGRAMDATA", ""), r"Microsoft\Windows\Start Menu\Programs"),
    ]
    for d in start_dirs:
        if os.path.exists(d):
            for ext in ("*.lnk", "*.exe"):
                for fpath in glob.glob(os.path.join(d, "**", ext), recursive=True):
                    stem = Path(fpath).stem.lower()
                    if stem == base_name or base_name in stem:
                        if fpath.lower().endswith(".lnk"):
                            try:
                                import win32com.client
                                shell = win32com.client.Dispatch("WScript.Shell")
                                lnk_target = shell.CreateShortcut(fpath).TargetPath
                                if lnk_target and os.path.exists(lnk_target.strip('"')):
                                    return Path(lnk_target.strip('"'))
                            except Exception:
                                pass
                        return Path(fpath)

    # 4. System PATH
    which_path = shutil.which(cleaned) or shutil.which(f"{base_name}.exe")
    if which_path:
        resolved_p = Path(which_path)
        if (
            resolved_p.name.lower() in BLOCKED_SYSTEM_BINARIES
            or resolved_p.stem.lower() in BLOCKED_SYSTEM_BINARIES
        ):
            return None
        return resolved_p

    return None


class DesktopPowers:
    """Provides high-level power implementations for desktop automation."""

    def resolve_app_path(self, app_name: str) -> Optional[Path]:
        """Resolves application path using 4-tier discovery order."""
        return resolve_app_path(app_name)

    def pwr_016_get_active_window(self) -> Dict[str, Any]:
        """PWR-016: Retrieves the active foreground window details."""
        return desktop_worker.get_active_window()

    def pwr_017_capture_screen(self, region: Optional[Tuple[int, int, int, int]] = None) -> Dict[str, Any]:
        """PWR-017: Captures screen region with SHA-256 evidence artifact."""
        return desktop_worker.capture_screen(region=region)

    def pwr_018_focus_window(self, title_pattern: str) -> Dict[str, Any]:
        """PWR-018: Brings window matching title pattern to foreground."""
        success = desktop_worker.focus_window(title_pattern)
        return {"title_pattern": title_pattern, "focused": success, "active_window": desktop_worker.get_active_window()}

    def pwr_019_safe_type(self, text: str, interval: float = 0.02) -> Dict[str, Any]:
        """PWR-019: Types text safely into active element with see-act-verify."""
        return desktop_worker.see_act_verify(action="type", params={"text": text, "interval": interval})

    def pwr_020_mouse_click(self, x: int, y: int, button: str = "left", clicks: int = 1) -> Dict[str, Any]:
        """PWR-020: Clicks at coordinates with See-Act-Verify loop."""
        return desktop_worker.see_act_verify(
            action="click", params={"x": x, "y": y, "button": button, "clicks": clicks}
        )


# Global Desktop Powers Instance
desktop_powers = DesktopPowers()

__all__ = ["DesktopPowers", "desktop_powers", "resolve_app_path", "BLOCKED_SYSTEM_BINARIES"]
