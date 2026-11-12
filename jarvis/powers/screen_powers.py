"""
JARVIS Screen & Window Powers (PWR-016 to PWR-026)
Display interaction and visual automation:
  - Window management (focus, enumerate, minimize)
  - Screen capture and region OCR
  - Mouse/keyboard simulation
  - Screenshot comparison and visual element search
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import hashlib
import os
import struct
import sys
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple


class ScreenPowers:
    """Screen capture, window management, and input simulation powers."""

    # Win32 constants
    _SW_RESTORE = 9
    _SW_MINIMIZE = 6
    _KEYEVENTF_KEYUP = 0x0002
    _INPUT_KEYBOARD = 1
    _INPUT_MOUSE = 0
    _MOUSEEVENTF_LEFTDOWN = 0x0002
    _MOUSEEVENTF_LEFTUP = 0x0004
    _MOUSEEVENTF_ABSOLUTE = 0x8000
    _MOUSEEVENTF_MOVE = 0x0001
    _VK_LWIN = 0x5B
    _VK_D = 0x44

    # ------------------------------------------------------------------ #
    # PWR-016  Get Active Window
    # ------------------------------------------------------------------ #
    @staticmethod
    def get_active_window() -> Dict[str, Any]:
        """PWR-016: Get the currently focused foreground window title and handle."""
        if not hasattr(ctypes, "windll"):
            return {
                "power_id": "PWR-016",
                "status": "unavailable",
                "hwnd": 0,
                "title": "",
                "message": "Desktop window inspection requires Windows Win32 API (ctypes.windll.user32). Unsupported platform.",
                "platform": sys.platform,
            }
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()

            # Get window title
            length = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)

            # Get window rect
            rect = ctypes.wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))

            # Get process ID
            pid = ctypes.wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

            return {
                "power_id": "PWR-016",
                "status": "success",
                "hwnd": hwnd,
                "title": buf.value,
                "pid": pid.value,
                "rect": {
                    "left": rect.left,
                    "top": rect.top,
                    "right": rect.right,
                    "bottom": rect.bottom,
                    "width": rect.right - rect.left,
                    "height": rect.bottom - rect.top,
                },
            }
        except Exception as e:
            return {"power_id": "PWR-016", "status": "error", "message": str(e)}

    # ------------------------------------------------------------------ #
    # PWR-017  Capture Region
    # ------------------------------------------------------------------ #
    @staticmethod
    def capture_region(region: Optional[Tuple[int, int, int, int]] = None) -> Dict[str, Any]:
        """PWR-017: Screenshot (full or region) with SHA-256 hash.

        Args:
            region: Optional (left, top, right, bottom) bounding box.
                    If None, captures the full primary monitor.
        """
        try:
            # Try mss first (fast, no display server dependency)
            try:
                import mss
                import mss.tools

                with mss.mss() as sct:
                    if region:
                        monitor = {
                            "left": region[0],
                            "top": region[1],
                            "width": region[2] - region[0],
                            "height": region[3] - region[1],
                        }
                    else:
                        monitor = sct.monitors[1]  # Primary monitor

                    screenshot = sct.grab(monitor)
                    raw_bytes = mss.tools.to_png(screenshot.rgb, screenshot.size)

                    sha256 = hashlib.sha256(raw_bytes).hexdigest()

                    # Save to temp
                    ts = int(time.time())
                    path = os.path.join(os.environ.get("TEMP", "."), f"jarvis_capture_{ts}.png")
                    with open(path, "wb") as f:
                        f.write(raw_bytes)

                    return {
                        "power_id": "PWR-017",
                        "status": "success",
                        "path": path,
                        "width": screenshot.size[0],
                        "height": screenshot.size[1],
                        "sha256": sha256,
                        "size_bytes": len(raw_bytes),
                    }
            except ImportError:
                pass

            # Fallback: PIL/Pillow
            try:
                from PIL import ImageGrab

                if region:
                    img = ImageGrab.grab(bbox=region)
                else:
                    img = ImageGrab.grab()

                ts = int(time.time())
                path = os.path.join(os.environ.get("TEMP", "."), f"jarvis_capture_{ts}.png")
                img.save(path, "PNG")

                with open(path, "rb") as f:
                    sha256 = hashlib.sha256(f.read()).hexdigest()

                return {
                    "power_id": "PWR-017",
                    "status": "success",
                    "path": path,
                    "width": img.width,
                    "height": img.height,
                    "sha256": sha256,
                    "size_bytes": os.path.getsize(path),
                }
            except ImportError:
                return {
                    "power_id": "PWR-017",
                    "status": "unavailable",
                    "message": "Neither mss nor Pillow is installed. Install via: pip install mss Pillow",
                }

        except Exception as e:
            return {"power_id": "PWR-017", "status": "error", "message": str(e)}

    # ------------------------------------------------------------------ #
    # PWR-018  Focus Window
    # ------------------------------------------------------------------ #
    @staticmethod
    def focus_window(title: str) -> Dict[str, Any]:
        """PWR-018: Bring a window to the foreground by partial title match."""
        if not hasattr(ctypes, "windll"):
            return {"power_id": "PWR-018", "status": "unavailable", "search_title": title, "message": "Windows only"}
        try:
            user32 = ctypes.windll.user32

            # Callback type for EnumWindows
            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.POINTER(ctypes.c_int))

            target_hwnd = None
            target_title = ""

            def enum_callback(hwnd, _lParam):
                nonlocal target_hwnd, target_title
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buf = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buf, length + 1)
                        win_title = buf.value
                        if title.lower() in win_title.lower():
                            target_hwnd = hwnd
                            target_title = win_title
                            return False  # Stop enumeration
                return True

            user32.EnumWindows(WNDENUMPROC(enum_callback), 0)

            if target_hwnd is None:
                return {
                    "power_id": "PWR-018",
                    "status": "not_found",
                    "search_title": title,
                    "message": f"No visible window matching '{title}' found.",
                }

            # Restore if minimized, then bring to front
            user32.ShowWindow(target_hwnd, ScreenPowers._SW_RESTORE)
            user32.SetForegroundWindow(target_hwnd)

            return {
                "power_id": "PWR-018",
                "status": "success",
                "hwnd": target_hwnd,
                "window_title": target_title,
                "search_title": title,
            }
        except Exception as e:
            return {"power_id": "PWR-018", "status": "error", "message": str(e)}

    # ------------------------------------------------------------------ #
    # PWR-019  Safe Type
    # ------------------------------------------------------------------ #
    @staticmethod
    def safe_type(text: str) -> Dict[str, Any]:
        """PWR-019: Type text into the currently focused window using SendInput."""
        if not hasattr(ctypes, "windll"):
            return {
                "power_id": "PWR-019",
                "status": "unavailable",
                "characters_typed": 0,
                "text_length": len(text),
                "message": "Windows only",
            }
        try:
            user32 = ctypes.windll.user32

            # Use SendInput with KEYEVENTF_UNICODE for each character
            KEYEVENTF_UNICODE = 0x0004
            KEYEVENTF_KEYUP = 0x0002
            INPUT_KEYBOARD = 1

            # INPUT structure for SendInput
            class KEYBDINPUT(ctypes.Structure):
                _fields_ = [
                    ("wVk", ctypes.c_ushort),
                    ("wScan", ctypes.c_ushort),
                    ("dwFlags", ctypes.c_ulong),
                    ("time", ctypes.c_ulong),
                    ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
                ]

            class HARDWAREINPUT(ctypes.Structure):
                _fields_ = [
                    ("uMsg", ctypes.c_ulong),
                    ("wParamL", ctypes.c_short),
                    ("wParamH", ctypes.c_ushort),
                ]

            class MOUSEINPUT(ctypes.Structure):
                _fields_ = [
                    ("dx", ctypes.c_long),
                    ("dy", ctypes.c_long),
                    ("mouseData", ctypes.c_ulong),
                    ("dwFlags", ctypes.c_ulong),
                    ("time", ctypes.c_ulong),
                    ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
                ]

            class INPUT_UNION(ctypes.Union):
                _fields_ = [
                    ("ki", KEYBDINPUT),
                    ("mi", MOUSEINPUT),
                    ("hi", HARDWAREINPUT),
                ]

            class INPUT(ctypes.Structure):
                _fields_ = [
                    ("type", ctypes.c_ulong),
                    ("union", INPUT_UNION),
                ]

            chars_sent = 0
            for char in text:
                # Key down
                inp_down = INPUT()
                inp_down.type = INPUT_KEYBOARD
                inp_down.union.ki.wVk = 0
                inp_down.union.ki.wScan = ord(char)
                inp_down.union.ki.dwFlags = KEYEVENTF_UNICODE
                inp_down.union.ki.time = 0
                inp_down.union.ki.dwExtraInfo = ctypes.pointer(ctypes.c_ulong(0))

                # Key up
                inp_up = INPUT()
                inp_up.type = INPUT_KEYBOARD
                inp_up.union.ki.wVk = 0
                inp_up.union.ki.wScan = ord(char)
                inp_up.union.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
                inp_up.union.ki.time = 0
                inp_up.union.ki.dwExtraInfo = ctypes.pointer(ctypes.c_ulong(0))

                user32.SendInput(2, (INPUT * 2)(inp_down, inp_up), ctypes.sizeof(INPUT))
                chars_sent += 1

            return {
                "power_id": "PWR-019",
                "status": "success",
                "characters_typed": chars_sent,
                "text_length": len(text),
            }
        except Exception as e:
            return {"power_id": "PWR-019", "status": "error", "message": str(e)}

    # ------------------------------------------------------------------ #
    # PWR-020  Mouse Click
    # ------------------------------------------------------------------ #
    @staticmethod
    def mouse_click(x: int, y: int) -> Dict[str, Any]:
        """PWR-020: Simulate a left mouse click at screen coordinates (x, y)."""
        if not hasattr(ctypes, "windll"):
            return {"power_id": "PWR-020", "status": "unavailable", "x": x, "y": y, "message": "Windows only"}
        try:
            user32 = ctypes.windll.user32

            # Get screen dimensions for absolute coordinate conversion
            screen_w = user32.GetSystemMetrics(0)
            screen_h = user32.GetSystemMetrics(1)

            # Convert to absolute coordinates (0-65535 range)
            abs_x = int(x * 65535 / screen_w)
            abs_y = int(y * 65535 / screen_h)

            # Move cursor
            user32.SetCursorPos(x, y)
            time.sleep(0.05)

            # Click using mouse_event
            MOUSEEVENTF_LEFTDOWN = 0x0002
            MOUSEEVENTF_LEFTUP = 0x0004
            user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            time.sleep(0.02)
            user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

            return {
                "power_id": "PWR-020",
                "status": "success",
                "x": x,
                "y": y,
                "screen_resolution": {"width": screen_w, "height": screen_h},
            }
        except Exception as e:
            return {"power_id": "PWR-020", "status": "error", "message": str(e)}

    # ------------------------------------------------------------------ #
    # PWR-021  OCR Region
    # ------------------------------------------------------------------ #
    @staticmethod
    def ocr_region(region: Optional[Tuple[int, int, int, int]] = None) -> Dict[str, Any]:
        """PWR-021: OCR text extraction from a screen region.

        Args:
            region: Optional (left, top, right, bottom) bounding box.
        """
        try:
            # Step 1: Capture the region
            try:
                from PIL import ImageGrab
            except ImportError:
                try:
                    import mss
                    # We'll handle mss below
                except ImportError:
                    return {
                        "power_id": "PWR-021",
                        "status": "unavailable",
                        "message": "Neither Pillow nor mss is installed for screen capture.",
                    }

            img = None
            try:
                from PIL import ImageGrab

                if region:
                    img = ImageGrab.grab(bbox=region)
                else:
                    img = ImageGrab.grab()
            except ImportError:
                import mss

                with mss.mss() as sct:
                    if region:
                        monitor = {
                            "left": region[0],
                            "top": region[1],
                            "width": region[2] - region[0],
                            "height": region[3] - region[1],
                        }
                    else:
                        monitor = sct.monitors[1]
                    screenshot = sct.grab(monitor)
                    # Convert to PIL for pytesseract
                    from PIL import Image

                    img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

            if img is None:
                return {"power_id": "PWR-021", "status": "error", "message": "Failed to capture screen region."}

            # Step 2: Run OCR
            try:
                import pytesseract

                text = pytesseract.image_to_string(img)
                return {
                    "power_id": "PWR-021",
                    "status": "success",
                    "text": text.strip(),
                    "region": region,
                    "image_size": {"width": img.width, "height": img.height},
                    "engine": "pytesseract",
                }
            except ImportError:
                # Save image so user can run OCR externally
                ts = int(time.time())
                path = os.path.join(os.environ.get("TEMP", "."), f"jarvis_ocr_{ts}.png")
                img.save(path, "PNG")
                return {
                    "power_id": "PWR-021",
                    "status": "ocr_unavailable",
                    "message": "pytesseract not installed. Screenshot saved for manual OCR.",
                    "screenshot_path": path,
                    "image_size": {"width": img.width, "height": img.height},
                }
            except Exception as ocr_err:
                return {
                    "power_id": "PWR-021",
                    "status": "ocr_error",
                    "message": f"OCR failed: {ocr_err}",
                    "region": region,
                }

        except Exception as e:
            return {"power_id": "PWR-021", "status": "error", "message": str(e)}

    # ------------------------------------------------------------------ #
    # PWR-022  Screen Resolution
    # ------------------------------------------------------------------ #
    @staticmethod
    def get_screen_resolution() -> Dict[str, Any]:
        """PWR-022: Get the primary screen resolution."""
        if not hasattr(ctypes, "windll"):
            return {
                "power_id": "PWR-022",
                "status": "unavailable",
                "message": "Screen resolution query requires Windows Win32 API (ctypes.windll.user32). Unsupported platform.",
                "platform": sys.platform,
            }
        try:
            user32 = ctypes.windll.user32

            # SM_CXSCREEN=0, SM_CYSCREEN=1 for primary monitor
            width = user32.GetSystemMetrics(0)
            height = user32.GetSystemMetrics(1)

            # Virtual screen (all monitors combined)
            # SM_CXVIRTUALSCREEN=78, SM_CYVIRTUALSCREEN=79
            virtual_w = user32.GetSystemMetrics(78)
            virtual_h = user32.GetSystemMetrics(79)

            # Number of monitors: SM_CMONITORS=80
            monitor_count = user32.GetSystemMetrics(80)

            # DPI awareness
            dpi = 96
            try:
                dpi = user32.GetDpiForSystem()
            except AttributeError:
                pass  # Older Windows versions

            return {
                "power_id": "PWR-022",
                "status": "success",
                "primary": {"width": width, "height": height},
                "virtual_screen": {"width": virtual_w, "height": virtual_h},
                "monitor_count": monitor_count,
                "dpi": dpi,
                "scale_factor": round(dpi / 96.0 * 100),
            }
        except Exception as e:
            return {"power_id": "PWR-022", "status": "error", "message": str(e)}

    # ------------------------------------------------------------------ #
    # PWR-023  Visual Element Find (Placeholder)
    # ------------------------------------------------------------------ #
    @staticmethod
    def visual_element_find(description: str) -> Dict[str, Any]:
        """PWR-023: Visual grounding — find a UI element by natural language description.

        This is a placeholder for integration with a vision model (e.g., GPT-4V, OmniParser).
        Currently returns a structured "not implemented" response.
        """
        return {
            "power_id": "PWR-023",
            "status": "not_implemented",
            "description": description,
            "message": (
                "Visual element finding requires a vision model backend (e.g., GPT-4V, OmniParser). "
                "This is a placeholder for future integration. Use window_list() or "
                "get_active_window() for basic window-level discovery."
            ),
            "suggested_alternatives": ["PWR-016 (get_active_window)", "PWR-024 (window_list)"],
        }

    # ------------------------------------------------------------------ #
    # PWR-024  Window List
    # ------------------------------------------------------------------ #
    @staticmethod
    def window_list() -> Dict[str, Any]:
        """PWR-024: Enumerate all visible top-level windows."""
        if not hasattr(ctypes, "windll"):
            return {
                "power_id": "PWR-024",
                "status": "unavailable",
                "window_count": 0,
                "windows": [],
                "message": "Window enumeration requires Windows Win32 API (ctypes.windll.user32). Unsupported platform.",
                "platform": sys.platform,
            }
        try:
            user32 = ctypes.windll.user32

            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.POINTER(ctypes.c_int))

            windows: List[Dict[str, Any]] = []

            def enum_callback(hwnd, _lParam):
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buf = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buf, length + 1)
                        title = buf.value
                        if title.strip():
                            rect = ctypes.wintypes.RECT()
                            user32.GetWindowRect(hwnd, ctypes.byref(rect))

                            pid = ctypes.wintypes.DWORD()
                            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

                            windows.append(
                                {
                                    "hwnd": hwnd,
                                    "title": title,
                                    "pid": pid.value,
                                    "rect": {
                                        "left": rect.left,
                                        "top": rect.top,
                                        "right": rect.right,
                                        "bottom": rect.bottom,
                                        "width": rect.right - rect.left,
                                        "height": rect.bottom - rect.top,
                                    },
                                }
                            )
                return True

            user32.EnumWindows(WNDENUMPROC(enum_callback), 0)

            return {
                "power_id": "PWR-024",
                "status": "success",
                "window_count": len(windows),
                "windows": windows,
            }
        except Exception as e:
            return {"power_id": "PWR-024", "status": "error", "message": str(e)}

    # ------------------------------------------------------------------ #
    # PWR-025  Minimize All
    # ------------------------------------------------------------------ #
    @staticmethod
    def minimize_all() -> Dict[str, Any]:
        """PWR-025: Minimize all windows (Win+D equivalent)."""
        if not hasattr(ctypes, "windll"):
            return {
                "power_id": "PWR-025",
                "status": "unavailable",
                "action": "minimize_all",
                "message": "Minimizing windows requires Windows Win32 API (ctypes.windll.user32). Unsupported platform.",
                "platform": sys.platform,
            }
        try:
            user32 = ctypes.windll.user32

            # Simulate Win+D keystroke
            KEYEVENTF_KEYUP = 0x0002
            VK_LWIN = 0x5B
            VK_D = 0x44

            # Win key down
            user32.keybd_event(VK_LWIN, 0, 0, 0)
            # D key down
            user32.keybd_event(VK_D, 0, 0, 0)
            time.sleep(0.05)
            # D key up
            user32.keybd_event(VK_D, 0, KEYEVENTF_KEYUP, 0)
            # Win key up
            user32.keybd_event(VK_LWIN, 0, KEYEVENTF_KEYUP, 0)

            return {
                "power_id": "PWR-025",
                "status": "success",
                "action": "minimize_all",
                "message": "All windows minimized (Win+D sent)",
            }
        except Exception as e:
            return {"power_id": "PWR-025", "status": "error", "message": str(e)}

    # ------------------------------------------------------------------ #
    # PWR-026  Screenshot Diff
    # ------------------------------------------------------------------ #
    @staticmethod
    def screenshot_diff(img1_path: str, img2_path: str) -> Dict[str, Any]:
        """PWR-026: Compare two screenshots pixel-wise and report differences."""
        try:
            if not os.path.isfile(img1_path):
                return {"power_id": "PWR-026", "status": "error", "message": f"File not found: {img1_path}"}
            if not os.path.isfile(img2_path):
                return {"power_id": "PWR-026", "status": "error", "message": f"File not found: {img2_path}"}

            try:
                from PIL import Image
            except ImportError:
                return {
                    "power_id": "PWR-026",
                    "status": "unavailable",
                    "message": "Pillow is required for screenshot comparison. Install via: pip install Pillow",
                }

            img1 = Image.open(img1_path).convert("RGB")
            img2 = Image.open(img2_path).convert("RGB")

            # Check dimensions
            if img1.size != img2.size:
                return {
                    "power_id": "PWR-026",
                    "status": "size_mismatch",
                    "img1_size": {"width": img1.width, "height": img1.height},
                    "img2_size": {"width": img2.width, "height": img2.height},
                    "message": "Images have different dimensions; pixel-wise comparison not possible.",
                }

            # Pixel-wise comparison
            pixels1 = img1.load()
            pixels2 = img2.load()
            total_pixels = img1.width * img1.height
            diff_count = 0
            total_diff_magnitude = 0

            # Bounding box of changed region
            min_x, min_y = img1.width, img1.height
            max_x, max_y = 0, 0

            for y in range(img1.height):
                for x in range(img1.width):
                    p1 = pixels1[x, y]
                    p2 = pixels2[x, y]
                    if p1 != p2:
                        diff_count += 1
                        total_diff_magnitude += sum(abs(a - b) for a, b in zip(p1, p2))
                        min_x = min(min_x, x)
                        min_y = min(min_y, y)
                        max_x = max(max_x, x)
                        max_y = max(max_y, y)

            diff_pct = round((diff_count / total_pixels) * 100, 4) if total_pixels > 0 else 0.0
            identical = diff_count == 0

            result: Dict[str, Any] = {
                "power_id": "PWR-026",
                "status": "success",
                "identical": identical,
                "total_pixels": total_pixels,
                "different_pixels": diff_count,
                "difference_pct": diff_pct,
                "image_size": {"width": img1.width, "height": img1.height},
            }

            if not identical:
                avg_magnitude = round(total_diff_magnitude / (diff_count * 3), 2) if diff_count > 0 else 0
                result["diff_bounding_box"] = {
                    "left": min_x,
                    "top": min_y,
                    "right": max_x,
                    "bottom": max_y,
                    "width": max_x - min_x + 1,
                    "height": max_y - min_y + 1,
                }
                result["avg_pixel_magnitude"] = avg_magnitude

                # Generate diff image
                try:
                    diff_img = Image.new("RGB", img1.size, (0, 0, 0))
                    diff_pixels = diff_img.load()
                    for y in range(img1.height):
                        for x in range(img1.width):
                            p1 = pixels1[x, y]
                            p2 = pixels2[x, y]
                            if p1 != p2:
                                # Highlight differences in red with intensity proportional to magnitude
                                mag = min(255, sum(abs(a - b) for a, b in zip(p1, p2)))
                                diff_pixels[x, y] = (mag, 0, 0)

                    ts = int(time.time())
                    diff_path = os.path.join(os.environ.get("TEMP", "."), f"jarvis_diff_{ts}.png")
                    diff_img.save(diff_path, "PNG")
                    result["diff_image_path"] = diff_path
                except Exception:
                    pass  # Diff image is optional

            return result

        except Exception as e:
            return {"power_id": "PWR-026", "status": "error", "message": str(e)}


# Module-level singleton
screen_powers = ScreenPowers()
