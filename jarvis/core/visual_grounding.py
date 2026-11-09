"""
JARVIS GUI Visual Grounding & Safe Desktop Control.

Implements UI-TARS-1.5-7B vision-language-action grounding substrate:
  - 0-1000 normalized coordinate <-> absolute screen pixel transformation
  - Desktop screenshot capture pipeline
  - UI-TARS action syntax parser
  - Inline permission broker with restricted zone collision detection
  - Safe desktop hardware action dispatching with dry-run support
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, Field

from jarvis.config import settings
from jarvis.core.logger import get_logger

logger = get_logger("core.visual_grounding")


@dataclass
class RestrictedZone:
    """Designates a protected screen boundary that blocks or gates automation clicks."""

    name: str
    norm_xmin: float
    norm_ymin: float
    norm_xmax: float
    norm_ymax: float
    severity: str = "critical"  # "critical", "high", "prompt_user"
    description: str = ""

    def contains(self, norm_x: float, norm_y: float) -> bool:
        return self.norm_xmin <= norm_x <= self.norm_xmax and self.norm_ymin <= norm_y <= self.norm_ymax


class VisualAction(BaseModel):
    action_type: str  # "click", "double_click", "right_click", "type", "drag", "scroll", "hotkey"
    norm_x: Optional[float] = None
    norm_y: Optional[float] = None
    target_text: Optional[str] = None
    keys: Optional[str] = None
    drag_to_norm_x: Optional[float] = None
    drag_to_norm_y: Optional[float] = None
    confidence: float = 1.0


class VisualGroundingEngine:
    """
    Translates UI-TARS 0-1000 normalized coordinates to display hardware coordinates
    and enforces safety boundaries before executing OS mouse/keyboard actions.
    """

    DEFAULT_SCREEN_WIDTH: int = 1920
    DEFAULT_SCREEN_HEIGHT: int = 1080

    # Default safety guardrail zones on 0-1000 scale
    DEFAULT_RESTRICTED_ZONES: List[RestrictedZone] = [
        # Top-right window close button (accidental app termination guard)
        RestrictedZone(
            name="top_right_system_close",
            norm_xmin=975,
            norm_ymin=0,
            norm_xmax=1000,
            norm_ymax=40,
            severity="prompt_user",
            description="Window close button region",
        ),
        # Windows Start button / Taskbar critical system corner
        RestrictedZone(
            name="taskbar_system_privilege",
            norm_xmin=0,
            norm_ymin=960,
            norm_xmax=50,
            norm_ymax=1000,
            severity="prompt_user",
            description="Start menu administrative area",
        ),
        # Common UAC / elevated credential dialog center zone
        RestrictedZone(
            name="uac_prompt_shield",
            norm_xmin=400,
            norm_ymin=450,
            norm_xmax=600,
            norm_ymax=550,
            severity="critical",
            description="Elevated Administrator prompt sensitive zone",
        ),
    ]

    def __init__(self, display_width: Optional[int] = None, display_height: Optional[int] = None):
        self.screen_width = display_width or self._detect_screen_width()
        self.screen_height = display_height or self._detect_screen_height()
        self.restricted_zones: List[RestrictedZone] = list(self.DEFAULT_RESTRICTED_ZONES)
        self.action_history: List[Dict[str, Any]] = []

    def _detect_screen_width(self) -> int:
        try:
            import ctypes

            user32 = ctypes.windll.user32
            return int(user32.GetSystemMetrics(0))
        except Exception:
            return self.DEFAULT_SCREEN_WIDTH

    def _detect_screen_height(self) -> int:
        try:
            import ctypes

            user32 = ctypes.windll.user32
            return int(user32.GetSystemMetrics(1))
        except Exception:
            return self.DEFAULT_SCREEN_HEIGHT

    def add_restricted_zone(self, zone: RestrictedZone) -> None:
        """Appends a custom restricted zone to safety broker."""
        self.restricted_zones.append(zone)

    def normalized_to_absolute(
        self,
        norm_x: float,
        norm_y: float,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> Tuple[int, int]:
        """
        Converts 0-1000 relative UI-TARS coordinate to exact screen pixel coordinates.
        Clamps inputs safely to [0, 1000].
        """
        w = width or self.screen_width
        h = height or self.screen_height

        clamped_x = max(0.0, min(1000.0, float(norm_x)))
        clamped_y = max(0.0, min(1000.0, float(norm_y)))

        abs_x = int(round((clamped_x / 1000.0) * w))
        abs_y = int(round((clamped_y / 1000.0) * h))

        # Clamp pixels to bounds
        abs_x = max(0, min(w - 1, abs_x))
        abs_y = max(0, min(h - 1, abs_y))

        return abs_x, abs_y

    def absolute_to_normalized(
        self,
        abs_x: int,
        abs_y: int,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> Tuple[float, float]:
        """Converts screen pixel coordinates to 0-1000 UI-TARS normalized float."""
        w = width or self.screen_width
        h = height or self.screen_height

        norm_x = round((float(abs_x) / float(w)) * 1000.0, 2)
        norm_y = round((float(abs_y) / float(h)) * 1000.0, 2)

        return max(0.0, min(1000.0, norm_x)), max(0.0, min(1000.0, norm_y))

    def parse_uitars_output(self, raw_output: str) -> List[VisualAction]:
        """
        Parses UI-TARS / Agent S formatted action responses into executable VisualActions.
        Supports standard UI-TARS 1.5 output formats:
          - click(point='[500, 250]') or click(point=[500, 250])
          - click(point='(500, 250)') or click(point=(500, 250))
          - click(start_box='[ymin, xmin, ymax, xmax]') -> centroid calculation
          - click(start_box='[500, 250]')
          - double_click(point=...) / double_click(start_box=...)
          - right_click(point=...) / right_click(start_box=...)
          - type(content='hello') / type(text='hello')
          - hotkey(key='ctrl+s')
          - scroll(direction='down') / scroll(direction='up')
          - drag(start=[100, 100], end=[500, 500])
        """
        ordered_actions: List[Tuple[int, VisualAction]] = []
        text = raw_output.strip()

        # Helper to parse coordinates from point or start_box
        def _extract_coords(arg_str: str) -> Optional[Tuple[float, float]]:
            nums = [float(n) for n in re.findall(r"(\d+(?:\.\d+)?)", arg_str)]
            if len(nums) == 2:
                return nums[0], nums[1]
            elif len(nums) == 4:
                # Bounding box [ymin, xmin, ymax, xmax] or [x1, y1, x2, y2] -> centroid
                cx = round((nums[0] + nums[2]) / 2.0, 2)
                cy = round((nums[1] + nums[3]) / 2.0, 2)
                return cx, cy
            return None

        # 1. Matches click, double_click, right_click
        click_pattern = re.finditer(
            r"(click|double_click|right_click)\s*\(\s*(?:point|start_box)\s*=\s*(['\"].*?['\"]|\[.*?\]|\(.*?\))(?:,\s*[^)]*)?\)",
            text,
            re.IGNORECASE,
        )
        for m in click_pattern:
            act_type = m.group(1).lower()
            coords = _extract_coords(m.group(2))
            if coords:
                ordered_actions.append(
                    (m.start(), VisualAction(action_type=act_type, norm_x=coords[0], norm_y=coords[1]))
                )

        # 2. Match type(content='...') or type(text='...')
        type_matches = re.finditer(
            r"type\s*\(\s*(?:content|text)\s*=\s*['\"](.*?)['\"]\s*(?:,\s*[^)]*)?\)",
            text,
            re.IGNORECASE,
        )
        for m in type_matches:
            ordered_actions.append((m.start(), VisualAction(action_type="type", target_text=m.group(1))))

        # 3. Match hotkey(key='...')
        hotkey_matches = re.finditer(
            r"hotkey\s*\(\s*key\s*=\s*['\"](.*?)['\"]\s*(?:,\s*[^)]*)?\)",
            text,
            re.IGNORECASE,
        )
        for m in hotkey_matches:
            ordered_actions.append((m.start(), VisualAction(action_type="hotkey", keys=m.group(1))))

        # 4. Match scroll(direction='...')
        scroll_matches = re.finditer(
            r"scroll\s*\(\s*(?:direction\s*=\s*)?['\"]?(up|down|left|right)['\"]?\s*(?:,\s*[^)]*)?\)",
            text,
            re.IGNORECASE,
        )
        for m in scroll_matches:
            ordered_actions.append((m.start(), VisualAction(action_type="scroll", keys=m.group(1).lower())))

        # 5. Match drag(start=[x1, y1], end=[x2, y2])
        drag_matches = re.finditer(
            r"drag\s*\(\s*start\s*=\s*['\"]?[\[\(]\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*[\]\)]['\"]?\s*,\s*end\s*=\s*['\"]?[\[\(]\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*[\]\)]['\"]?\s*\)",
            text,
            re.IGNORECASE,
        )
        for m in drag_matches:
            ordered_actions.append(
                (
                    m.start(),
                    VisualAction(
                        action_type="drag",
                        norm_x=float(m.group(1)),
                        norm_y=float(m.group(2)),
                        drag_to_norm_x=float(m.group(3)),
                        drag_to_norm_y=float(m.group(4)),
                    ),
                )
            )

        ordered_actions.sort(key=lambda item: item[0])
        return [act for _, act in ordered_actions]

    def validate_action_safety(self, action: VisualAction) -> Tuple[bool, Optional[str]]:
        """
        Inline permission broker checks whether coordinate falls in a restricted zone.
        Returns (is_safe, violation_reason).
        """
        if action.norm_x is not None and action.norm_y is not None:
            for zone in self.restricted_zones:
                if zone.contains(action.norm_x, action.norm_y):
                    reason = (
                        f"Blocked dangerous coordinate ({action.norm_x}, {action.norm_y}): "
                        f"Target intersects restricted zone '{zone.name}' ({zone.description}). "
                        f"Severity: {zone.severity}."
                    )
                    logger.warning(reason)
                    return False, reason

        if action.drag_to_norm_x is not None and action.drag_to_norm_y is not None:
            for zone in self.restricted_zones:
                if zone.contains(action.drag_to_norm_x, action.drag_to_norm_y):
                    reason = f"Blocked drag destination: target intersects restricted zone '{zone.name}'."
                    return False, reason

        return True, None

    def capture_screen(self, save_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Captures active desktop display buffer.
        Saves screenshot if path provided; returns perception metadata.
        """
        timestamp = time.time()
        try:
            from PIL import ImageGrab

            screenshot = ImageGrab.grab()
            w, h = screenshot.size
            if save_path:
                Path(save_path).parent.mkdir(parents=True, exist_ok=True)
                screenshot.save(save_path)
            return {
                "status": "success",
                "width": w,
                "height": h,
                "timestamp": timestamp,
                "saved_to": save_path,
                "mode": "live_display",
            }
        except Exception as e:
            logger.info(f"Using synthetic display buffer fallback: {e}")
            return {
                "status": "simulated",
                "width": self.screen_width,
                "height": self.screen_height,
                "timestamp": timestamp,
                "saved_to": None,
                "mode": "synthetic_buffer",
            }

    def execute_action(self, action: VisualAction, dry_run: bool = True) -> Dict[str, Any]:
        """
        Dispatches action to desktop with safety validation.
        Defaults to dry_run=True to ensure safety in test suites.
        """
        is_safe, violation = self.validate_action_safety(action)
        if not is_safe:
            return {
                "status": "blocked",
                "action": action.action_type,
                "reason": violation,
                "executed": False,
            }

        abs_x, abs_y = None, None
        if action.norm_x is not None and action.norm_y is not None:
            abs_x, abs_y = self.normalized_to_absolute(action.norm_x, action.norm_y)

        result = {
            "status": "success",
            "action": action.action_type,
            "norm_coords": (action.norm_x, action.norm_y) if action.norm_x is not None else None,
            "abs_coords": (abs_x, abs_y) if abs_x is not None else None,
            "dry_run": dry_run,
            "executed": True,
        }

        if not dry_run:
            try:
                import pyautogui

                if action.action_type == "click" and abs_x is not None and abs_y is not None:
                    pyautogui.click(abs_x, abs_y)
                elif action.action_type == "double_click" and abs_x is not None and abs_y is not None:
                    pyautogui.doubleClick(abs_x, abs_y)
                elif action.action_type == "type" and action.target_text:
                    pyautogui.write(action.target_text)
                elif action.action_type == "hotkey" and action.keys:
                    pyautogui.hotkey(*action.keys.split("+"))
            except Exception as e:
                result["status"] = "error"
                result["error"] = str(e)

        self.action_history.append(result)
        return result


# Global Singleton
visual_grounding = VisualGroundingEngine()
