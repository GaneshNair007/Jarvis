"""
JARVIS Presence-Aware Remote Execution & Notification Failover Router
=====================================================================
Enforces bidirectional notification routing and transport failover across:
1. WhatsApp Dispatcher (jarvis/powers/whatsapp_dispatcher.py)
2. Switch Protocol Bridge (integrations/switch/switch_integration.py)
3. Windows Desktop Toast / Laptop Local Notifications (jarvis/core/notifier.py)

Routing Rules:
- If laptop is OFFLINE -> Route notifications directly to phone (+91 9324094474).
- If phone delivery fails -> Route notifications to laptop desktop toast / HUD.
- Automatic failover between WhatsApp and Switch transports if one is unreachable.
"""

from __future__ import annotations

import asyncio
import inspect
import subprocess
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from jarvis.config import settings
from jarvis.core.logger import get_logger
from jarvis.core.presence_manager import presence_manager, DeviceType, PresenceState
from jarvis.core.audit import audit_ledger
from jarvis.powers.whatsapp_dispatcher import whatsapp_dispatcher
from integrations.switch.switch_integration import switch_integration

logger = get_logger("core.remote_router")


class TransportChannel(str, Enum):
    WHATSAPP = "whatsapp"
    SWITCH = "switch"
    WINDOWS_TOAST = "windows_toast"
    LOCAL_LOG = "local_log"


@dataclass
class NotificationResult:
    success: bool
    delivered_to: str  # 'phone', 'laptop', 'both', 'failed'
    channel_used: str  # 'whatsapp', 'switch', 'windows_toast', 'local_log', 'none'
    failover_occurred: bool = False
    title: str = ""
    message: str = ""
    recipient: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RemoteRouter:
    """
    Presence-aware notification and task execution routing engine.
    Dynamically routes outbound alerts to the right active device,
    and fails over between WhatsApp and Switch Protocol transports.
    """

    def __init__(
        self,
        presence_mon=None,
        whatsapp_disp=None,
        switch_int=None,
    ):
        self.presence = presence_mon or presence_manager
        self.whatsapp = whatsapp_disp or whatsapp_dispatcher
        self.switch = switch_int or switch_integration
        self.desktop_notifier_override: Optional[Callable[[str, str], bool]] = None

    def set_desktop_notifier(self, notifier_fn: Optional[Callable[[str, str], bool]]) -> None:
        """Injects a custom/mock desktop notifier for testing or headless execution."""
        self.desktop_notifier_override = notifier_fn

    def _send_desktop_notification(self, title: str, message: str) -> bool:
        """Dispatches desktop toast on host laptop with fallback."""
        if self.desktop_notifier_override is not None:
            try:
                return bool(self.desktop_notifier_override(title, message))
            except Exception as e:
                logger.warning(f"Desktop notifier override error: {e}")
                return False

        try:
            from jarvis.core.notifier import opportunity_notifier
            return opportunity_notifier.send_desktop_notification(title, message)
        except Exception as exc:
            logger.warning(f"Failed to dispatch desktop toast: {exc}")
            return False

    async def _dispatch_whatsapp(self, message: str, phone: Optional[str] = None) -> Dict[str, Any]:
        """Dispatches message via WhatsApp, raising exception on failure."""
        res = await self.whatsapp.send_whatsapp_message(message, phone=phone)
        status = res.get("status")
        # In testing/production, if an explicit failure status is returned, treat as error
        if status in ("failed", "error", "unavailable"):
            raise RuntimeError(f"WhatsApp dispatch returned failure status: {status}")
        return res

    def _dispatch_switch(self, message: str, room_id: Optional[str] = None) -> Dict[str, Any]:
        """Dispatches message via Switch Protocol room bridge."""
        if not self.switch.enabled:
            raise RuntimeError("Switch integration is disabled")

        res = self.switch.send_room_message(message, room_id=room_id)
        if not res.success:
            raise RuntimeError(f"Switch room message failed: {res.message}")
        return res.to_dict()

    async def _send_to_phone_with_failover(
        self,
        title: str,
        message: str,
        primary_channel: str = "whatsapp",
        phone_number: Optional[str] = None,
    ) -> Tuple[bool, str, bool, Dict[str, Any]]:
        """
        Attempts delivery to phone using primary_channel.
        Fails over to secondary channel if primary channel fails.
        Returns: (success, channel_used, failover_occurred, details)
        """
        target_phone = phone_number or self.presence.canonical_phone
        formatted_message = f"[{title}]\n{message}" if title else message
        failover_occurred = False
        details: Dict[str, Any] = {}

        if primary_channel == "whatsapp":
            try:
                # Attempt primary: WhatsApp
                logger.info(f"Dispatching alert to phone ({target_phone}) via WhatsApp...")
                wa_res = await self._dispatch_whatsapp(formatted_message, phone=target_phone)
                details["whatsapp"] = wa_res
                return True, "whatsapp", False, details
            except Exception as wa_err:
                logger.warning(f"WhatsApp dispatch failed ({wa_err}). Triggering failover to Switch Protocol...")
                failover_occurred = True
                details["whatsapp_error"] = str(wa_err)

                # Log failover audit entry
                try:
                    audit_ledger.log_event(
                        event_type="TRANSPORT_FAILOVER",
                        task_id=f"failover_{int(time.time() * 1000)}",
                        power_id="remote_router",
                        status="TRIGGERED",
                        inputs={"primary": "whatsapp", "target": target_phone},
                        outputs={"fallback": "switch", "error": str(wa_err)},
                    )
                except Exception:
                    pass

                # Attempt fallback: Switch
                try:
                    sw_res = self._dispatch_switch(formatted_message)
                    details["switch"] = sw_res
                    return True, "switch", True, details
                except Exception as sw_err:
                    logger.error(f"Switch fallback dispatch also failed: {sw_err}")
                    details["switch_error"] = str(sw_err)
                    return False, "none", True, details

        else:
            # Primary: Switch
            try:
                logger.info("Dispatching alert via Switch Protocol...")
                sw_res = self._dispatch_switch(formatted_message)
                details["switch"] = sw_res
                return True, "switch", False, details
            except Exception as sw_err:
                logger.warning(f"Switch dispatch failed ({sw_err}). Triggering failover to WhatsApp...")
                failover_occurred = True
                details["switch_error"] = str(sw_err)

                # Log failover audit entry
                try:
                    audit_ledger.log_event(
                        event_type="TRANSPORT_FAILOVER",
                        task_id=f"failover_{int(time.time() * 1000)}",
                        power_id="remote_router",
                        status="TRIGGERED",
                        inputs={"primary": "switch"},
                        outputs={"fallback": "whatsapp", "error": str(sw_err)},
                    )
                except Exception:
                    pass

                # Attempt fallback: WhatsApp
                try:
                    wa_res = await self._dispatch_whatsapp(formatted_message, phone=target_phone)
                    details["whatsapp"] = wa_res
                    return True, "whatsapp", True, details
                except Exception as wa_err:
                    logger.error(f"WhatsApp fallback dispatch also failed: {wa_err}")
                    details["whatsapp_error"] = str(wa_err)
                    return False, "none", True, details

    async def route_notification(
        self,
        title: str,
        message: str,
        priority: str = "normal",
        target: Optional[str] = None,
        primary_transport: str = "whatsapp",
    ) -> NotificationResult:
        """
        Routes an outbound alert based on device availability and presence rules.

        Invariants:
        1. If laptop is OFFLINE -> routes to phone (+91 9324094474).
        2. If phone delivery fails -> routes to laptop desktop toast.
        3. Automatic failover between WhatsApp and Switch.
        """
        laptop_online = self.presence.is_device_online(DeviceType.LAPTOP.value)
        phone_online = self.presence.is_device_online(DeviceType.PHONE.value)
        canonical_phone = self.presence.canonical_phone

        logger.info(
            f"Routing notification '{title}': target={target}, laptop_online={laptop_online}, "
            f"phone_online={phone_online}, priority={priority}"
        )

        # Decide primary destination device
        route_to_phone_first = False
        if target == DeviceType.PHONE.value:
            route_to_phone_first = True
        elif not laptop_online:
            # Rule 1: Laptop is offline/unreachable -> Route to phone
            logger.info("Laptop is OFFLINE. Routing notification to phone.")
            route_to_phone_first = True
        elif target == DeviceType.LAPTOP.value:
            route_to_phone_first = False
        else:
            # General event: if priority is high/critical or laptop offline, send to phone
            if priority in ("critical", "high") or not laptop_online:
                route_to_phone_first = True
            else:
                route_to_phone_first = False

        if route_to_phone_first:
            # Route to Phone with WhatsApp <-> Switch failover
            success, channel, failover, details = await self._send_to_phone_with_failover(
                title=title,
                message=message,
                primary_channel=primary_transport,
                phone_number=canonical_phone,
            )

            if success:
                return NotificationResult(
                    success=True,
                    delivered_to="phone",
                    channel_used=channel,
                    failover_occurred=failover,
                    title=title,
                    message=message,
                    recipient=canonical_phone,
                    details=details,
                )

            # Rule 2: Phone delivery failed -> Route to laptop
            logger.warning("Phone delivery failed across all transports. Falling back to laptop desktop toast...")
            toast_success = self._send_desktop_notification(title, message)
            details["laptop_fallback_toast"] = toast_success

            if toast_success:
                return NotificationResult(
                    success=True,
                    delivered_to="laptop",
                    channel_used="windows_toast",
                    failover_occurred=True,
                    title=title,
                    message=message,
                    details=details,
                )
            else:
                return NotificationResult(
                    success=False,
                    delivered_to="failed",
                    channel_used="none",
                    failover_occurred=True,
                    title=title,
                    message=message,
                    details=details,
                    error="All delivery channels (WhatsApp, Switch, Desktop Toast) failed",
                )

        else:
            # Route to Laptop Desktop Toast first
            toast_success = self._send_desktop_notification(title, message)
            if toast_success:
                return NotificationResult(
                    success=True,
                    delivered_to="laptop",
                    channel_used="windows_toast",
                    failover_occurred=False,
                    title=title,
                    message=message,
                    details={"toast": True},
                )

            # Laptop toast failed -> Fallback to phone
            logger.warning("Laptop toast notification failed. Falling back to phone notification...")
            success, channel, failover, details = await self._send_to_phone_with_failover(
                title=title,
                message=message,
                primary_channel=primary_transport,
                phone_number=canonical_phone,
            )

            return NotificationResult(
                success=success,
                delivered_to="phone" if success else "failed",
                channel_used=channel,
                failover_occurred=True,
                title=title,
                message=message,
                recipient=canonical_phone if success else None,
                details=details,
                error=None if success else "Laptop notification and phone failover both failed",
            )

    def route_notification_sync(
        self,
        title: str,
        message: str,
        priority: str = "normal",
        target: Optional[str] = None,
        primary_transport: str = "whatsapp",
    ) -> NotificationResult:
        """Synchronous wrapper for route_notification."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # If already running inside an active event loop, execute via task or thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
                    asyncio.run,
                    self.route_notification(title, message, priority, target, primary_transport),
                )
                return future.result()
        else:
            return asyncio.run(
                self.route_notification(title, message, priority, target, primary_transport)
            )


# Global Singleton Instance
remote_router = RemoteRouter()
