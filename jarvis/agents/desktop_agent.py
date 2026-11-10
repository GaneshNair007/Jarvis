"""
JARVIS Desktop Specialist Agent
PDF Spec: Multi-Agent & Orchestration — Computer Use & Desktop Control

Executes Windows desktop automation and computer use operations:
- Dynamic application path resolution (4-tier resolution order)
- Desktop window inspection and foreground activation
- Cryptographically verified screen region capture
- Safe key typing and mouse automation with See-Act-Verify
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple

from jarvis.agents.base import AgentContext, AgentResult, AgentTask, BaseSpecialistAgent
from jarvis.core.logger import get_logger
from jarvis.powers.desktop_powers import DesktopPowers, desktop_powers

logger = get_logger("agents.desktop")


class DesktopAgent(BaseSpecialistAgent):
    """
    Specialist agent for desktop interactions, application resolution,
    window management, screen capture, and safe human-in-the-loop input.
    """

    name: str = "DesktopAgent"
    role: str = "desktop"
    permitted_tools: List[str] = [
        "app_resolver",
        "app_launcher",
        "window_focus",
        "screen_capture",
        "safe_type",
        "mouse_click",
        "desktop",
        "file",
    ]

    def __init__(self, powers: Optional[DesktopPowers] = None):
        self._powers = powers or desktop_powers

    def resolve_app_path(self, app_name: str) -> Optional[Path]:
        """
        Dynamically resolves application path following the 4-tier resolution order:
        1. Built-in known shortcuts
        2. Windows Registry (HKLM & HKCU App Paths)
        3. Windows Start Menu Programs
        4. System PATH
        Returns None if nonexistent or if blocked by security policy.
        """
        return self._powers.resolve_app_path(app_name=app_name)

    def launch_app(self, app_name: str, args: Optional[List[str]] = None) -> Dict[str, Any]:
        """Launches an application after resolving its verified executable path."""
        resolved = self.resolve_app_path(app_name)
        if not resolved:
            return {
                "status": "NOT_FOUND",
                "app_name": app_name,
                "error": f"Could not resolve executable path for '{app_name}'",
            }

        cmd = [str(resolved)] + (args or [])
        try:
            proc = subprocess.Popen(cmd)
            return {
                "status": "LAUNCHED",
                "app_name": app_name,
                "path": str(resolved),
                "pid": proc.pid,
            }
        except Exception as exc:
            return {
                "status": "LAUNCH_FAILED",
                "app_name": app_name,
                "path": str(resolved),
                "error": str(exc),
            }

    def pwr_016_get_active_window(self) -> Dict[str, Any]:
        """PWR-016: Retrieves the active foreground window details."""
        return self._powers.pwr_016_get_active_window()

    def pwr_017_capture_screen(self, region: Optional[Tuple[int, int, int, int]] = None) -> Dict[str, Any]:
        """PWR-017: Captures screen region with SHA-256 evidence artifact."""
        return self._powers.pwr_017_capture_screen(region=region)

    def pwr_018_focus_window(self, title_pattern: str) -> Dict[str, Any]:
        """PWR-018: Brings window matching title pattern to foreground."""
        return self._powers.pwr_018_focus_window(title_pattern=title_pattern)

    def pwr_019_safe_type(self, text: str, interval: float = 0.02) -> Dict[str, Any]:
        """PWR-019: Types text safely into active element with see-act-verify."""
        return self._powers.pwr_019_safe_type(text=text, interval=interval)

    def pwr_020_mouse_click(
        self,
        x: int,
        y: int,
        button: str = "left",
        clicks: int = 1,
    ) -> Dict[str, Any]:
        """PWR-020: Clicks at coordinates with See-Act-Verify loop."""
        return self._powers.pwr_020_mouse_click(x=x, y=y, button=button, clicks=clicks)

    async def execute(self, task: AgentTask, context: AgentContext) -> AgentResult:
        """Executes assigned desktop task using permitted tools only."""
        start = time.time()
        params = task.parameters
        goal = (task.goal or "").lower()
        tools_used: List[str] = []
        output: Any = None
        status = "SUCCESS"
        error: Optional[str] = None

        try:
            if "resolve" in goal or "resolve_app" in params:
                tools_used.append("app_resolver")
                app_name = params.get("app_name") or params.get("resolve_app") or task.goal
                res_path = self.resolve_app_path(app_name)
                output = {"app_name": app_name, "resolved_path": str(res_path) if res_path else None}
            elif "launch" in goal or "launch" in params:
                tools_used.append("app_launcher")
                app_name = params.get("app_name") or params.get("launch") or task.goal
                output = self.launch_app(app_name, args=params.get("args"))
            elif "focus" in goal or "focus_window" in params:
                tools_used.append("window_focus")
                title = params.get("title_pattern") or params.get("title") or task.goal
                output = self.pwr_018_focus_window(title)
            elif "capture" in goal or "screenshot" in goal or "capture_screen" in params:
                tools_used.append("screen_capture")
                output = self.pwr_017_capture_screen(region=params.get("region"))
            elif "type" in goal or "safe_type" in params:
                tools_used.append("safe_type")
                output = self.pwr_019_safe_type(
                    text=params.get("text", ""),
                    interval=float(params.get("interval", 0.02)),
                )
            elif "click" in goal or "mouse_click" in params:
                tools_used.append("mouse_click")
                output = self.pwr_020_mouse_click(
                    x=int(params.get("x", 100)),
                    y=int(params.get("y", 100)),
                    button=params.get("button", "left"),
                    clicks=int(params.get("clicks", 1)),
                )
            else:
                tools_used.append("window_focus")
                output = self.pwr_016_get_active_window()

            duration_ms = round((time.time() - start) * 1000, 2)
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                role=self.role,
                status=status,
                output=output,
                evidence={"tools": tools_used, "goal": task.goal},
                tools_used=tools_used,
                duration_ms=duration_ms,
                error=error,
            )
        except Exception as exc:
            duration_ms = round((time.time() - start) * 1000, 2)
            logger.error(f"DesktopAgent.execute failed: {exc}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                role=self.role,
                status="FAILED",
                output=None,
                error=str(exc),
                duration_ms=duration_ms,
            )


# ── Singletons & Aliases ─────────────────────────────────────────────────────
desktop_agent = DesktopAgent()
agent = desktop_agent

__all__ = ["DesktopAgent", "desktop_agent", "agent"]
