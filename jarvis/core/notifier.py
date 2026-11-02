"""
JARVIS Multi-Channel Alert & Dispatch Engine
Sends real-time proactive alerts via WhatsApp, native Windows Desktop Toast,
and local audit logs to Ganesh (+91 9324094474).
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from typing import Any, Dict, List, Optional
import httpx

from jarvis.security.ten_layer_shield import jarvis_security_suite

logger = logging.getLogger("jarvis.notifier")


class OpportunityNotifier:
    """
    Coordinates outbound communication across WhatsApp Cloud API / Webhook,
    native desktop notifications, and structured audit logs.
    """

    DEFAULT_TARGET_PHONE = "+91 9324094474"
    DEFAULT_USER_NAME = "Ganesh"

    def __init__(self):
        self.whatsapp_api_token = os.getenv("WHATSAPP_API_TOKEN")
        self.whatsapp_phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
        self.webhook_url = os.getenv("WHATSAPP_WEBHOOK_URL")

    def format_whatsapp_hackathon_digest(
        self,
        opportunities: List[Dict[str, Any]],
        recipient_name: str = "Ganesh",
        location: str = "India / Remote",
    ) -> str:
        """Formats an executive, high-impact WhatsApp markdown message."""
        timestamp = time.strftime("%d %b %Y, %I:%M %p")
        lines = [
            f"⚡ *JARVIS INTELLIGENCE BRIEFING* ⚡",
            f"👤 Recipient: {recipient_name}",
            f"📍 Target Region: {location}",
            f"🕒 Generated: {timestamp}",
            f"────────────────────────────",
            f"Hey Ganesh, here is the curated list of top hackathons & high-stipend opportunities analyzed for your profile:\n",
        ]

        for i, opp in enumerate(opportunities, start=1):
            title = opp.get("title", "Hackathon Opportunity")
            deadline = opp.get("deadline", "Upcoming")
            mode = opp.get("mode", "Online / Hybrid")
            tags = ", ".join(opp.get("tags", ["AI", "Tech"]))
            url = opp.get("url", "https://devpost.com")

            lines.append(f"*{i}. {title}*")
            lines.append(f"   • *Mode / Location:* {mode}")
            lines.append(f"   • *Deadline:* {deadline}")
            lines.append(f"   • *Focus:* {tags}")
            lines.append(f"   • *Portal:* {url}")
            if "scaffold_path" in opp:
                lines.append(f"   • *Scaffolded Repo:* `{opp['scaffold_path']}`")
            lines.append("")

        lines.append("────────────────────────────")
        lines.append("🤖 _Autonomous Multi-Agent Swarm standing by to scaffold solutions & test harnesses._")
        return "\n".join(lines)

    async def send_whatsapp_message(
        self,
        phone_number: str = DEFAULT_TARGET_PHONE,
        message: str = "",
    ) -> Dict[str, Any]:
        """
        Dispatches message via WhatsApp Cloud API or configured webhook.
        If live credentials are not set, logs the full payload and registers
        dispatch in Merkle Audit Trail.
        """
        clean_phone = phone_number.replace(" ", "").replace("-", "")

        # 1. Attempt Cloud API if tokens provided
        if self.whatsapp_api_token and self.whatsapp_phone_number_id:
            try:
                url = f"https://graph.facebook.com/v19.0/{self.whatsapp_phone_number_id}/messages"
                headers = {
                    "Authorization": f"Bearer {self.whatsapp_api_token}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "messaging_product": "whatsapp",
                    "to": clean_phone,
                    "type": "text",
                    "text": {"body": message},
                }
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(url, headers=headers, json=payload)
                    success = resp.status_code in (200, 201)
                    jarvis_security_suite.layer9_audit.log_event(
                        "WHATSAPP_DISPATCH",
                        f"Dispatched WhatsApp to {clean_phone[:4]}*** (Status: {resp.status_code})",
                    )
                    return {
                        "status": "sent" if success else "failed",
                        "channel": "whatsapp_cloud_api",
                        "recipient": clean_phone,
                        "status_code": resp.status_code,
                        "raw_response": resp.json() if success else resp.text,
                    }
            except Exception as e:
                logger.warning(f"WhatsApp Cloud API send failed: {e}")

        # 2. Webhook Gateway
        if self.webhook_url:
            try:
                async with httpx.AsyncClient(timeout=8.0) as client:
                    resp = await client.post(self.webhook_url, json={"to": clean_phone, "text": message})
                    return {
                        "status": "sent",
                        "channel": "webhook_gateway",
                        "recipient": clean_phone,
                    }
            except Exception as e:
                logger.warning(f"WhatsApp Webhook gateway failed: {e}")

        # 3. Secure Simulated Dispatch & Audit Registration
        jarvis_security_suite.layer9_audit.log_event(
            "WHATSAPP_SIMULATED_DISPATCH",
            f"Simulated WhatsApp message to {clean_phone[:4]}*** ({len(message)} chars)",
        )

        # Trigger native desktop notification to ensure Ganesh receives the alert immediately
        self.send_desktop_notification(
            title="JARVIS Hackathon Scout Alert",
            message=f"Opportunity briefing prepared for Ganesh ({len(message.splitlines())} lines). Check terminal or dashboard.",
        )

        return {
            "status": "simulated_success",
            "channel": "local_dispatcher",
            "recipient": clean_phone,
            "message_length": len(message),
            "payload_preview": message[:300] + "\n...",
            "note": "Formatted message generated and audited. Configure WHATSAPP_API_TOKEN in .env for direct live transmission.",
        }

    def send_desktop_notification(self, title: str, message: str) -> bool:
        """Fires an instant notification on Windows desktop using PowerShell."""
        try:
            clean_title = title.replace('"', '`"')
            clean_msg = message.replace('"', '`"').replace("\n", " ")[:160]
            ps_script = (
                f'[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null; '
                f'$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02); '
                f'$textNodes = $template.GetElementsByTagName("text"); '
                f'$textNodes.Item(0).AppendChild($template.CreateTextNode("{clean_title}")) | Out-Null; '
                f'$textNodes.Item(1).AppendChild($template.CreateTextNode("{clean_msg}")) | Out-Null; '
                f'$toast = [Windows.UI.Notifications.ToastNotification]::new($template); '
                f'[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("JARVIS OS").Show($toast);'
            )
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                capture_output=True,
                timeout=3.0,
            )
            return True
        except Exception:
            return False


# Global Notifier Singleton
opportunity_notifier = OpportunityNotifier()
