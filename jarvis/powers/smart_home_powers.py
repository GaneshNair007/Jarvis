"""JARVIS Smart Home Powers (PWR-256 to PWR-269).

Provides BroadLink IR/RF device control, smart plugs, Wi-Fi smart bulbs,
scene automation, and voice command dispatch for room control.
Reference: Ayman William Stage 01 Smart Room Architecture.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from jarvis.core.logger import get_logger

logger = get_logger("powers.smart_home")


class SmartHomePowers:
    """Implementations for Room Control and Smart Home capabilities."""

    def __init__(self):
        self.device_states: Dict[str, Dict[str, Any]] = {
            # BroadLink IR / RF Layer
            "climate.ac": {
                "name": "Room AC",
                "type": "broadlink_ir",
                "state": "off",
                "temperature": 24,
                "target_temperature": 24,
                "mode": "cool",
                "fan_speed": "auto",
            },
            "media.projector_tv": {
                "name": "Living Room Projector / TV",
                "type": "broadlink_ir",
                "state": "off",
                "input_source": "HDMI1",
                "volume": 35,
                "muted": False,
            },
            # Wi-Fi Smart Plugs (High-load / Appliance)
            "switch.geyser": {
                "name": "Bathroom Geyser",
                "type": "smart_plug",
                "state": "off",
                "power_watts": 0,
                "auto_off_minutes": 15,
                "timer_active": False,
            },
            "switch.workstation": {
                "name": "Workstation Power Dock",
                "type": "smart_plug",
                "state": "on",
                "power_watts": 120,
            },
            # Wi-Fi Smart Bulbs & Lighting
            "light.desk_lamp": {
                "name": "Office Desk Lamp",
                "type": "smart_bulb",
                "state": "on",
                "brightness": 85,
                "color_temp": 4500,
            },
            "light.ambient_rgb": {
                "name": "Ambient Ceiling Strips",
                "type": "smart_bulb",
                "state": "off",
                "brightness": 0,
                "rgb_color": [0, 229, 255],  # Cyan
            },
            "light.living_room": {
                "name": "Main Room Lights",
                "type": "smart_bulb",
                "state": "off",
                "brightness": 0,
                "color_temp": 2700,
            },
            "lock.front_door": {
                "name": "Main Entrance Lock",
                "type": "security_lock",
                "state": "locked",
            },
        }

    def get_all_devices(self) -> Dict[str, Any]:
        """PWR-267: Queries all registered room devices and current states."""
        return {
            "power_id": "PWR-267",
            "device_count": len(self.device_states),
            "devices": self.device_states,
        }

    def get_device_status(self, entity_id: Optional[str] = None) -> Dict[str, Any]:
        """PWR-238: Queries a specific device state, or all devices when entity_id is omitted."""
        if entity_id is None:
            return self.get_all_devices()
        dev = self.device_states.get(entity_id)
        if not dev:
            return {"power_id": "PWR-238", "entity_id": entity_id, "state": "unknown", "error": "Device not found"}
        return {"power_id": "PWR-238", "entity_id": entity_id, "data": dev}

    def control_climate(
        self,
        action: str = "toggle",
        temperature: Optional[int] = None,
        mode: Optional[str] = None,
        fan_speed: Optional[str] = None,
    ) -> Dict[str, Any]:
        """PWR-257: Controls AC and climate devices via BroadLink IR."""
        ac = self.device_states["climate.ac"]

        if action == "on":
            ac["state"] = "on"
        elif action == "off":
            ac["state"] = "off"
        elif action == "toggle":
            ac["state"] = "off" if ac["state"] == "on" else "on"

        if temperature is not None:
            ac["target_temperature"] = max(16, min(30, int(temperature)))
            ac["state"] = "on"

        if mode in ["cool", "heat", "fan", "dry", "auto"]:
            ac["mode"] = mode

        if fan_speed in ["low", "medium", "high", "auto"]:
            ac["fan_speed"] = fan_speed

        logger.info(f"BroadLink IR AC updated: {ac}")
        return {
            "power_id": "PWR-257",
            "device": "climate.ac",
            "state": ac["state"],
            "target_temperature": ac["target_temperature"],
            "mode": ac["mode"],
            "fan_speed": ac["fan_speed"],
            "feedback": f"Air conditioning is now {ac['state']} at {ac['target_temperature']} degrees Celsius ({ac['mode']} mode).",
        }

    def control_media(
        self,
        action: str = "toggle",
        device_id: str = "media.projector_tv",
        input_source: Optional[str] = None,
        volume: Optional[int] = None,
        mute: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """PWR-259: Controls Projector / TV and media receivers via BroadLink IR."""
        media = self.device_states.get(device_id, self.device_states["media.projector_tv"])

        if action == "on":
            media["state"] = "on"
        elif action == "off":
            media["state"] = "off"
        elif action == "toggle":
            media["state"] = "off" if media["state"] == "on" else "on"

        if input_source:
            media["input_source"] = input_source.upper()
            media["state"] = "on"

        if volume is not None:
            media["volume"] = max(0, min(100, int(volume)))
            media["muted"] = False

        if mute is not None:
            media["muted"] = bool(mute)

        logger.info(f"BroadLink IR Media updated: {media}")
        return {
            "power_id": "PWR-259",
            "device": device_id,
            "state": media["state"],
            "input_source": media["input_source"],
            "volume": media["volume"],
            "muted": media["muted"],
            "feedback": f"{media['name']} is {media['state']}"
            + (f" on {media['input_source']}." if media["state"] == "on" else "."),
        }

    def control_plug(
        self,
        entity_id: str,
        state: str = "toggle",
        auto_off_minutes: Optional[int] = None,
    ) -> Dict[str, Any]:
        """PWR-258: Controls Wi-Fi smart plugs with safety timer support."""
        if entity_id not in self.device_states:
            self.device_states[entity_id] = {"name": entity_id, "type": "smart_plug", "state": "off"}

        dev = self.device_states[entity_id]

        if state == "toggle":
            dev["state"] = "off" if dev.get("state") == "on" else "on"
        else:
            dev["state"] = state.lower()

        if dev["state"] == "on":
            timer = auto_off_minutes or dev.get("auto_off_minutes", 15)
            dev["timer_active"] = True
            dev["auto_off_minutes"] = timer
            msg = f"{dev['name']} turned ON with a {timer}-minute auto-off safety shutoff."
        else:
            dev["timer_active"] = False
            msg = f"{dev['name']} turned OFF."

        logger.info(f"Smart Plug updated: {dev}")
        return {
            "power_id": "PWR-258",
            "entity_id": entity_id,
            "state": dev["state"],
            "timer_active": dev.get("timer_active", False),
            "feedback": msg,
        }

    def control_lights(
        self,
        entity_id: str = "light.ambient_rgb",
        state: str = "toggle",
        brightness: Optional[int] = None,
        rgb_color: Optional[List[int]] = None,
        color_temp: Optional[int] = None,
    ) -> Dict[str, Any]:
        """PWR-256: Controls Wi-Fi smart bulb color, brightness, and state."""
        if entity_id not in self.device_states:
            self.device_states[entity_id] = {"name": entity_id, "type": "smart_bulb", "state": "off"}

        bulb = self.device_states[entity_id]

        if state == "toggle":
            bulb["state"] = "off" if bulb.get("state") == "on" else "on"
        elif state in ["on", "off"]:
            bulb["state"] = state

        if brightness is not None:
            bulb["brightness"] = max(0, min(100, int(brightness)))
            if bulb["brightness"] > 0:
                bulb["state"] = "on"
            else:
                bulb["state"] = "off"

        if rgb_color and len(rgb_color) == 3:
            bulb["rgb_color"] = [max(0, min(255, c)) for c in rgb_color]
            bulb["state"] = "on"

        if color_temp is not None:
            bulb["color_temp"] = max(2000, min(6500, int(color_temp)))

        logger.info(f"Smart Light updated: {bulb}")
        return {
            "power_id": "PWR-256",
            "entity_id": entity_id,
            "state": bulb["state"],
            "brightness": bulb.get("brightness", 100),
            "rgb_color": bulb.get("rgb_color"),
            "feedback": f"{bulb['name']} set to {bulb['state']} (Brightness: {bulb.get('brightness', 100)}%).",
        }

    def activate_scene(self, scene_name: str) -> Dict[str, Any]:
        """PWR-260: Executes synchronized multi-device room scene."""
        scene = scene_name.lower().strip()

        if "work" in scene or "focus" in scene:
            self.control_lights("light.desk_lamp", state="on", brightness=100, color_temp=4500)
            self.control_lights("light.ambient_rgb", state="on", brightness=30, rgb_color=[0, 229, 255])
            self.control_climate(action="on", temperature=24, mode="cool")
            self.control_media(action="off")
            desc = "Work Focus Scene activated. Desk lamp at 100%, ambient cyan accent at 30%, AC set to 24C, projector off."

        elif "movie" in scene or "cinema" in scene:
            self.control_lights("light.desk_lamp", state="off")
            self.control_lights("light.living_room", state="off")
            self.control_lights("light.ambient_rgb", state="on", brightness=12, rgb_color=[10, 20, 90])
            self.control_media(action="on", input_source="HDMI1", volume=45)
            self.control_climate(action="on", temperature=22, mode="cool")
            desc = "Movie Night Scene activated. Room lights dimmed to 12% deep blue, projector powered on HDMI1, AC set to 22C."

        elif "sleep" in scene or "night" in scene:
            self.control_lights("light.desk_lamp", state="off")
            self.control_lights("light.living_room", state="off")
            self.control_lights("light.ambient_rgb", state="off")
            self.control_media(action="off")
            self.control_plug("switch.geyser", state="off")
            self.control_climate(action="on", temperature=25, mode="cool", fan_speed="low")
            desc = "Sleep Mode activated. All room lights and appliances powered down, AC set to sleep mode 25C."

        elif "morning" in scene or "wake" in scene:
            self.control_lights("light.ambient_rgb", state="on", brightness=45, rgb_color=[255, 180, 100])
            self.control_plug("switch.geyser", state="on", auto_off_minutes=15)
            self.control_climate(action="off")
            desc = "Morning Wake Scene activated. Warm sunrise lighting at 45%, geyser switched on with 15m timer."

        else:
            return {
                "power_id": "PWR-260",
                "scene": scene_name,
                "status": "unrecognized",
                "feedback": f"Scene '{scene_name}' not defined. Available scenes: work_mode, movie_night, sleep_mode, morning_wake.",
            }

        return {
            "power_id": "PWR-260",
            "scene": scene_name,
            "status": "active",
            "feedback": desc,
        }

    def process_voice_command(self, transcript: str) -> Dict[str, Any]:
        """PWR-269: Parses natural language smart-room voice utterances into device actions."""
        t = transcript.lower().strip()

        # 1. AC commands
        if "ac" in t or "air condition" in t:
            temp_match = re.search(r"(\d{2})", t)
            target_temp = int(temp_match.group(1)) if temp_match else None

            if "off" in t:
                return self.control_climate(action="off")
            elif "on" in t or target_temp:
                return self.control_climate(action="on", temperature=target_temp)
            return self.control_climate(action="toggle")

        # 2. Projector / TV commands
        if "projector" in t or "tv" in t or "television" in t:
            if "off" in t:
                return self.control_media(action="off")
            elif "on" in t:
                return self.control_media(action="on")
            return self.control_media(action="toggle")

        # 3. Geyser commands
        if "geyser" in t or "water heater" in t:
            if "off" in t:
                return self.control_plug("switch.geyser", state="off")
            return self.control_plug("switch.geyser", state="on", auto_off_minutes=15)

        # 4. Light commands
        if "light" in t or "lamp" in t:
            if "off" in t:
                self.control_lights("light.desk_lamp", state="off")
                self.control_lights("light.ambient_rgb", state="off")
                return self.control_lights("light.living_room", state="off")
            elif "on" in t:
                return self.control_lights("light.desk_lamp", state="on", brightness=100)
            elif "dim" in t:
                return self.control_lights("light.ambient_rgb", state="on", brightness=20)
            return self.control_lights("light.desk_lamp", state="toggle")

        # 5. Scene triggers
        if "movie" in t:
            return self.activate_scene("movie_night")
        if "work" in t or "focus" in t:
            return self.activate_scene("work_mode")
        if "sleep" in t or "goodnight" in t:
            return self.activate_scene("sleep_mode")
        if "morning" in t or "wake up" in t:
            return self.activate_scene("morning_wake")

        return {
            "power_id": "PWR-269",
            "status": "unhandled",
            "feedback": f"No smart room command mapped for: '{transcript}'",
        }


smart_home_powers = SmartHomePowers()
