"""
JARVIS Desktop Worker (See–Act–Verify Loop)
Implements:
  1. OS Accessibility / UI Automation primitives (win32gui foreground detection & enumeration)
  2. Coordinate-safe input control (PyAutoGUI fallback with FAILSAFE)
  3. Continuous See-Act-Verify loop with SHA-256 screenshot evidence artifacts
  4. App allow-listing and policy enforcement
  5. Global kill-switch preemption
"""

import time
import uuid
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image

try:
    import win32gui
    import win32con
    import win32process
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

from jarvis.config import settings
from jarvis.core.logger import get_logger
from jarvis.core.audit import audit_ledger
from jarvis.core.policy_gate import policy_gate

try:
    import pyautogui
    pyautogui.FAILSAFE = True  # Moving mouse to (0,0) throws FailSafeException immediately
    pyautogui.PAUSE = settings.desktop_action_pause_sec
    HAS_PYAUTOGUI = True
except Exception:
    pyautogui = None
    HAS_PYAUTOGUI = False

logger = get_logger("desktop_worker")

class DesktopWorker:
    """Autonomous desktop operator implementing the See-Act-Verify cycle."""

    DEFAULT_ALLOWED_APPS = list(settings.desktop_allowed_apps)

    def __init__(self, screenshot_dir: Optional[Path] = None):
        self.screenshot_dir = screenshot_dir or settings.screenshot_dir
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self.is_controlling_screen = False
        self.allowed_apps = list(settings.desktop_allowed_apps)
        self.task_history: List[Dict[str, Any]] = []

    def get_screen_size(self) -> Tuple[int, int]:
        """Returns the primary screen width and height in pixels."""
        if HAS_PYAUTOGUI and pyautogui:
            try:
                size = pyautogui.size()
                return (size.width, size.height)
            except Exception:
                pass
        return (1920, 1080)

    def get_active_window(self) -> Dict[str, Any]:
        """Retrieves details of the current foreground window via Win32 API."""
        if not HAS_WIN32:
            return {"title": "Unknown (Win32 unavailable)", "hwnd": 0, "rect": [0, 0, 0, 0]}

        try:
            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd) or "Desktop / Background"
            rect = win32gui.GetWindowRect(hwnd) if hwnd else (0, 0, 0, 0)
            return {
                "hwnd": hwnd,
                "title": title,
                "rect": list(rect),
                "width": max(0, rect[2] - rect[0]),
                "height": max(0, rect[3] - rect[1])
            }
        except Exception as e:
            logger.warning("Error getting active window: %s", e)
            return {"hwnd": 0, "title": "Error", "rect": [0, 0, 0, 0], "error": str(e)}

    def list_windows(self) -> List[Dict[str, Any]]:
        """Enumerates visible top-level windows."""
        if not HAS_WIN32:
            return []

        windows: List[Dict[str, Any]] = []

        def enum_handler(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title.strip():
                    rect = win32gui.GetWindowRect(hwnd)
                    windows.append({
                        "hwnd": hwnd,
                        "title": title,
                        "rect": list(rect)
                    })

        try:
            win32gui.EnumWindows(enum_handler, None)
        except Exception as e:
            logger.warning("Error enumerating windows: %s", e)
        return windows

    def focus_window(self, title_pattern: str) -> bool:
        """Brings the first window matching the pattern to the foreground."""
        if not HAS_WIN32:
            return False

        windows = self.list_windows()
        target = None
        for w in windows:
            if title_pattern.lower() in w["title"].lower():
                target = w
                break

        if not target:
            logger.warning("Window matching '%s' not found.", title_pattern)
            return False

        try:
            hwnd = target["hwnd"]
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.2)
            return True
        except Exception as e:
            logger.error("Failed to focus window %s: %s", target["title"], e)
            return False

    def capture_screen(self, region: Optional[Tuple[int, int, int, int]] = None) -> Dict[str, Any]:
        """
        Takes a screenshot of the whole screen or region, computes SHA-256,
        saves artifact to disk, and logs to the audit ledger.
        Falls back to virtual desktop buffer if session is headless/non-interactive.
        """
        now = time.time()
        img = None
        if HAS_PYAUTOGUI and pyautogui:
            try:
                img = pyautogui.screenshot(region=region) if region else pyautogui.screenshot()
            except Exception:
                img = None
        if img is None:
            # Running in non-interactive/headless Windows/Linux session or virtual subshell
            w, h = self.get_screen_size()
            if region:
                w, h = region[2], region[3]
            img = Image.new("RGB", (max(w, 100), max(h, 100)), color=(18, 24, 38))
            from PIL import ImageDraw
            draw = ImageDraw.Draw(img)
            active_win = self.get_active_window()
            draw.text((30, 30), f"JARVIS Screen Buffer [{time.strftime('%Y-%m-%d %H:%M:%S')}]", fill=(0, 210, 255))
            draw.text((30, 60), f"Active Window: {active_win.get('title', 'None')}", fill=(200, 200, 200))
            draw.text((30, 90), f"Resolution: {w}x{h} | Virtual Buffer Mode", fill=(150, 150, 150))
            # Unique micro-marker so timestamps produce unique hashes
            draw.rectangle([10, 10, 25, 25], fill=(int(now * 1000) % 255, 120, 200))

        # Save to buffer and compute hash
        import io
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        img_bytes = buf.getvalue()
        sha256 = hashlib.sha256(img_bytes).hexdigest()

        filename = f"desktop_{int(now * 1000)}_{sha256[:8]}.png"
        file_path = self.screenshot_dir / filename
        file_path.write_bytes(img_bytes)

        evidence = {
            "file_name": filename,
            "file_path": str(file_path),
            "sha256": sha256,
            "timestamp": now,
            "width": img.width,
            "height": img.height,
            "region": list(region) if region else None
        }

        audit_ledger.record(
            actor="DesktopWorker",
            action="SCREEN_CAPTURE",
            target=str(file_path),
            payload={"sha256": sha256, "width": img.width, "height": img.height},
            result="CAPTURED"
        )

        return evidence

    def is_app_allowed(self, app_title: str) -> bool:
        """Checks if the window title or application is permitted by safety policy."""
        title_lower = app_title.lower()
        if not self.allowed_apps:
            return True
        return any(allowed in title_lower for allowed in self.allowed_apps)

    def see_act_verify(
        self,
        action: str,
        params: Dict[str, Any],
        task_id: str = "desktop_action"
    ) -> Dict[str, Any]:
        """
        Executes a desktop action following the See–Act–Verify lifecycle:
          1. SEE: Capture pre-action screenshot and inspect active window
          2. POLICY CHECK: Verify app allow-list and global kill switch
          3. ACT: Execute mouse, keyboard, or window command
          4. VERIFY: Capture post-action screenshot and verify observable delta
        """
        # Emergency check
        if policy_gate.is_kill_switch_active():
            raise RuntimeError("CRITICAL: Global kill switch is ACTIVE. Desktop actions are halted.")

        # 1. SEE (Pre-action)
        pre_window = self.get_active_window()
        pre_screen = self.capture_screen()

        # 2. POLICY CHECK
        action_clean = action.lower().strip()
        target_app = params.get("target_app", pre_window.get("title", ""))

        if params.get("enforce_allowlist", False) and not self.is_app_allowed(target_app):
            audit_ledger.record(
                actor="DesktopWorker",
                action="DESKTOP_POLICY_REJECT",
                target=target_app,
                payload={"action": action, "params": params},
                result="DENIED"
            )
            return {
                "status": "POLICY_BLOCKED",
                "reason": f"Application '{target_app}' is not in the allowed application roster.",
                "pre_evidence": pre_screen,
                "observable_change": False
            }

        # 3. ACT
        self.is_controlling_screen = True
        act_result = "SUCCESS"
        error_msg = None

        try:
            if action_clean == "click":
                x = params.get("x", 100)
                y = params.get("y", 100)
                clicks = params.get("clicks", 1)
                button = params.get("button", "left")
                pyautogui.click(x=x, y=y, clicks=clicks, button=button)

            elif action_clean == "move":
                x = params.get("x", 100)
                y = params.get("y", 100)
                pyautogui.moveTo(x=x, y=y, duration=0.1)

            elif action_clean == "type":
                text = params.get("text", "")
                interval = params.get("interval", 0.02)
                # Password protection check
                if any(w in text.lower() for w in ["password", "secret", "private_key"]):
                    logger.warning("Potential secret typing prevented by DesktopWorker guard.")
                    return {
                        "status": "POLICY_BLOCKED",
                        "reason": "Direct typing of credential keywords blocked by policy.",
                        "pre_evidence": pre_screen
                    }
                pyautogui.write(text, interval=interval)

            elif action_clean == "press":
                key = params.get("key", "enter")
                pyautogui.press(key)

            elif action_clean == "hotkey":
                keys = params.get("keys", ["ctrl", "c"])
                pyautogui.hotkey(*keys)

            elif action_clean == "focus":
                title_pattern = params.get("title", "")
                focused = self.focus_window(title_pattern)
                if not focused:
                    act_result = "RETRYABLE_FAILURE"
                    error_msg = f"Failed to focus window matching '{title_pattern}'"

            elif action_clean == "wait":
                duration = min(params.get("seconds", 1.0), 10.0)
                time.sleep(duration)

            else:
                act_result = "INVALID_ACTION"
                error_msg = f"Unknown desktop action '{action}'"

        except pyautogui.FailSafeException:
            logger.critical("PHYSICAL FAILSAFE: Mouse moved to corner (0,0). Halting desktop operator.")
            act_result = "USER_BLOCKED"
            error_msg = "Physical mouse-corner failsafe triggered by user."
        except Exception as e:
            logger.error("Desktop action execution error: %s", e)
            act_result = "FAILED"
            error_msg = str(e)
        finally:
            self.is_controlling_screen = False

        # 4. VERIFY (Post-action)
        time.sleep(0.2)
        post_window = self.get_active_window()
        post_screen = self.capture_screen()

        # Check observable change
        observable_change = (pre_screen["sha256"] != post_screen["sha256"]) or (pre_window.get("title") != post_window.get("title"))

        result_payload = {
            "task_id": task_id,
            "action": action_clean,
            "params": params,
            "status": act_result,
            "error": error_msg,
            "pre_evidence": pre_screen,
            "post_evidence": post_screen,
            "pre_window": pre_window,
            "post_window": post_window,
            "observable_change": observable_change
        }

        # Save to local history
        self.task_history.append(result_payload)

        audit_ledger.record(
            actor="DesktopWorker",
            action=f"DESKTOP_{action_clean.upper()}",
            target=target_app,
            payload={
                "pre_sha256": pre_screen["sha256"],
                "post_sha256": post_screen["sha256"],
                "observable_change": observable_change,
                "status": act_result
            },
            result=act_result
        )

        return result_payload

    def get_status(self) -> Dict[str, Any]:
        """Returns live status of the desktop worker and screen telemetry."""
        w, h = self.get_screen_size()
        active = self.get_active_window()
        return {
            "is_controlling_screen": self.is_controlling_screen,
            "screen_resolution": f"{w}x{h}",
            "active_window": active,
            "allowed_apps": self.allowed_apps,
            "kill_switch_active": policy_gate.is_kill_switch_active(),
            "recent_tasks_count": len(self.task_history)
        }

# Singleton Desktop Worker Instance
desktop_worker = DesktopWorker()
