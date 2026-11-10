"""
JARVIS Cross-Device Presence Manager
====================================
Monitors device heartbeats and operational availability for:
1. Host Laptop (Local Windows compute environment, RTX 4050)
2. Mobile Phone (Ganesh: +91 9324094474)

Enforces heartbeat timeouts, status transitions (ONLINE / DEGRADED / OFFLINE),
and provides presence state to the RemoteRouter for failover routing.
"""

from __future__ import annotations

import os
import time
import yaml
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from jarvis.config import settings
from jarvis.core.logger import get_logger

logger = get_logger("core.presence_manager")

_PROFILE_PATH = Path("data/profile.yml")
_CANONICAL_PHONE = "+91 9324094474"


class PresenceState(str, Enum):
    ONLINE = "ONLINE"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"
    UNKNOWN = "UNKNOWN"


class DeviceType(str, Enum):
    LAPTOP = "laptop"
    PHONE = "phone"


@dataclass
class DevicePresence:
    device_id: str
    name: str
    status: str = PresenceState.UNKNOWN.value
    last_heartbeat: float = 0.0
    ttl_sec: float = 60.0
    override_status: Optional[str] = None
    override_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    phone_number: Optional[str] = None
    preferred_transport: str = "windows_toast"
    fallback_transport: Optional[str] = None

    def is_online(self, current_time: Optional[float] = None) -> bool:
        """Determines if the device is currently ONLINE based on TTL and overrides."""
        if self.override_status:
            return self.override_status == PresenceState.ONLINE.value

        now = current_time or time.time()
        if self.last_heartbeat <= 0:
            return False
        return (now - self.last_heartbeat) <= self.ttl_sec

    def evaluate_status(self, current_time: Optional[float] = None) -> str:
        """Evaluates current status string: ONLINE, DEGRADED, or OFFLINE."""
        if self.override_status:
            return self.override_status

        now = current_time or time.time()
        if self.last_heartbeat <= 0:
            return PresenceState.OFFLINE.value

        elapsed = now - self.last_heartbeat
        if elapsed <= self.ttl_sec:
            return PresenceState.ONLINE.value
        elif elapsed <= (self.ttl_sec * 2.0):
            return PresenceState.DEGRADED.value
        else:
            return PresenceState.OFFLINE.value

    def to_dict(self) -> Dict[str, Any]:
        evaluated = self.evaluate_status()
        d = asdict(self)
        d["evaluated_status"] = evaluated
        d["is_online"] = self.is_online()
        d["seconds_since_heartbeat"] = round(time.time() - self.last_heartbeat, 1) if self.last_heartbeat > 0 else None
        return d


class PresenceManager:
    """
    Central monitor for device presence and heartbeats across host laptop and phone.
    """

    def __init__(self, profile_path: Optional[Path] = None):
        self.profile_path = profile_path or _PROFILE_PATH
        self.devices: Dict[str, DevicePresence] = {}
        self.canonical_phone = _CANONICAL_PHONE
        self._load_from_profile()

    def _load_from_profile(self) -> None:
        """Loads canonical phone and device parameters from data/profile.yml."""
        phone = _CANONICAL_PHONE
        laptop_ttl = 60.0
        phone_ttl = 180.0

        if self.profile_path.exists():
            try:
                with open(self.profile_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                    if "phone" in data:
                        phone = str(data["phone"])
                    devices_conf = data.get("devices", {})
                    if "laptop" in devices_conf:
                        laptop_ttl = float(devices_conf["laptop"].get("heartbeat_ttl_sec", 60.0))
                    if "phone" in devices_conf:
                        phone_ttl = float(devices_conf["phone"].get("heartbeat_ttl_sec", 180.0))
            except Exception as exc:
                logger.warning(f"Error loading devices from profile.yml: {exc}")

        self.canonical_phone = phone

        # Initialize default device profiles
        self.devices[DeviceType.LAPTOP.value] = DevicePresence(
            device_id=DeviceType.LAPTOP.value,
            name="Host Laptop (RTX 4050)",
            status=PresenceState.UNKNOWN.value,
            last_heartbeat=time.time(),  # Initially alive on host startup
            ttl_sec=laptop_ttl,
            preferred_transport="windows_toast",
            metadata={"platform": "windows", "compute_node": True},
        )

        self.devices[DeviceType.PHONE.value] = DevicePresence(
            device_id=DeviceType.PHONE.value,
            name=f"Primary Phone ({phone})",
            status=PresenceState.UNKNOWN.value,
            last_heartbeat=time.time(),  # Assume alive initially or updated on webhook
            ttl_sec=phone_ttl,
            phone_number=phone,
            preferred_transport="whatsapp",
            fallback_transport="switch",
            metadata={"carrier": "mobile", "authorized_number": phone},
        )

    def record_heartbeat(
        self,
        device_id: str,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[float] = None,
    ) -> None:
        """
        Records a heartbeat signal from a device.
        Clears any transient override and updates last_heartbeat timestamp.
        """
        dev_id = device_id.lower().strip()
        now = timestamp or time.time()

        if dev_id not in self.devices:
            # Register unknown dynamic device
            self.devices[dev_id] = DevicePresence(
                device_id=dev_id,
                name=f"Device {dev_id}",
                status=PresenceState.ONLINE.value,
                last_heartbeat=now,
                ttl_sec=60.0,
                metadata=metadata or {},
            )
        else:
            dev = self.devices[dev_id]
            dev.last_heartbeat = now
            dev.override_status = None
            dev.override_reason = None
            if metadata:
                dev.metadata.update(metadata)

        logger.debug(f"Heartbeat recorded for '{dev_id}' at {now}")

    def is_device_online(self, device_id: str, timeout_sec: Optional[float] = None) -> bool:
        """
        Returns True if device is currently online within its TTL (or given timeout_sec).
        """
        dev_id = device_id.lower().strip()
        dev = self.devices.get(dev_id)
        if not dev:
            return False

        if dev.override_status:
            return dev.override_status == PresenceState.ONLINE.value

        now = time.time()
        ttl = timeout_sec if timeout_sec is not None else dev.ttl_sec
        if dev.last_heartbeat <= 0:
            return False
        return (now - dev.last_heartbeat) <= ttl

    def get_device_status(self, device_id: str) -> Dict[str, Any]:
        """Returns detailed presence info for a device."""
        dev_id = device_id.lower().strip()
        dev = self.devices.get(dev_id)
        if not dev:
            return {
                "device_id": dev_id,
                "status": PresenceState.UNKNOWN.value,
                "is_online": False,
                "error": "Device not registered",
            }
        return dev.to_dict()

    def set_device_status(
        self,
        device_id: str,
        status: PresenceState | str,
        reason: Optional[str] = None,
    ) -> None:
        """
        Overrides the evaluated presence status of a device (e.g. for testing or offline probes).
        """
        dev_id = device_id.lower().strip()
        norm_status = status.value if isinstance(status, PresenceState) else status.upper()

        if dev_id in self.devices:
            self.devices[dev_id].override_status = norm_status
            self.devices[dev_id].override_reason = reason
        else:
            self.devices[dev_id] = DevicePresence(
                device_id=dev_id,
                name=f"Device {dev_id}",
                override_status=norm_status,
                override_reason=reason,
            )
        logger.info(f"Device '{dev_id}' status manually set to '{norm_status}' (reason: {reason})")

    def get_all_presence(self) -> Dict[str, Dict[str, Any]]:
        """Returns presence status dictionary for all registered devices."""
        return {dev_id: dev.to_dict() for dev_id, dev in self.devices.items()}


# Global Singleton Instance
presence_manager = PresenceManager()
