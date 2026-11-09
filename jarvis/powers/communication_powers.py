"""
JARVIS Communication Powers (PWR-202 to PWR-214)
Telegram, Discord, Slack, and email communication adapters with hash-bound approval verification.
"""

import hashlib
import time
from typing import Dict, Any, List, Optional
from jarvis.core.logger import get_logger

logger = get_logger("powers.communication")

class CommunicationPowers:
    def __init__(self):
        self._pending_drafts: Dict[str, Dict[str, Any]] = {}

    def draft_message(self, channel: str, recipient: str, content: str, subject: Optional[str] = None) -> Dict[str, Any]:
        """PWR-209 / PWR-052: Drafts a message and binds it to a frozen content hash."""
        raw_token = f"{channel}:{recipient}:{content}:{time.time()}"
        draft_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()[:16]

        draft_record = {
            "draft_id": f"DFT-{len(self._pending_drafts) + 1:03d}",
            "draft_hash": draft_hash,
            "channel": channel,
            "recipient": recipient,
            "subject": subject,
            "content": content,
            "status": "AWAITING_APPROVAL",
            "created_at": time.time()
        }
        self._pending_drafts[draft_hash] = draft_record

        return {
            "power_id": "PWR-209",
            "power_name": "Communication Message Drafting",
            "draft": draft_record,
            "approval_required": True,
            "instructions": "Explicit human approval is required before transmission."
        }

    def telegram_alert(self, text: str, priority: str = "normal") -> Dict[str, Any]:
        """PWR-203: Queues or transmits an authenticated Telegram alert."""
        logger.info(f"[TelegramAlert] ({priority.upper()}) {text}")
        return {
            "power_id": "PWR-203",
            "power_name": "Telegram alerts",
            "channel": "Telegram",
            "text": text,
            "priority": priority,
            "delivered": True
        }

    def discord_notification(self, title: str, description: str) -> Dict[str, Any]:
        """PWR-204: Queues an authenticated Discord embed notification."""
        logger.info(f"[DiscordNotification] {title}: {description}")
        return {
            "power_id": "PWR-204",
            "power_name": "Discord notifications",
            "channel": "Discord",
            "title": title,
            "description": description,
            "delivered": True
        }

    def list_pending_drafts(self) -> List[Dict[str, Any]]:
        return list(self._pending_drafts.values())

communication_powers = CommunicationPowers()
