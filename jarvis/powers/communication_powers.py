"""JARVIS Communication Powers (PWR-202 to PWR-214).

Provides Telegram messaging, desktop notifications, email drafting/sending,
multi-channel alerts, message scheduling, contact management, and templates.
"""

from __future__ import annotations

import json
import os
import subprocess
import uuid
from datetime import datetime, timezone
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, List, Optional

from jarvis.core.logger import get_logger

logger = get_logger("powers.communication")

_DATA_DIR = Path(os.environ.get(
    "JARVIS_DATA_DIR",
    Path(__file__).resolve().parents[2] / "data"
))
_OUTBOX_DIR = _DATA_DIR / "outbox"
_CONTACTS_FILE = _DATA_DIR / "contacts.json"
_TEMPLATES_DIR = _DATA_DIR / "templates"
_NOTIFICATION_LOG = _DATA_DIR / "notification_log.json"
_SCHEDULED_DIR = _DATA_DIR / "scheduled_messages"


class CommunicationPowers:
    """Implementations for multi-channel communication capabilities."""

    def __init__(self) -> None:
        self._muted_until: Optional[datetime] = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _is_muted(self) -> bool:
        if self._muted_until is None:
            return False
        return datetime.now(timezone.utc) < self._muted_until

    def _append_notification_log(self, entry: Dict[str, Any]) -> None:
        """Append an entry to the notification log."""
        try:
            _DATA_DIR.mkdir(parents=True, exist_ok=True)
            log: List[Dict[str, Any]] = []
            if _NOTIFICATION_LOG.exists():
                log = json.loads(_NOTIFICATION_LOG.read_text(encoding="utf-8"))
            log.append(entry)
            # Keep last 500 entries
            log = log[-500:]
            _NOTIFICATION_LOG.write_text(json.dumps(log, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.error("Failed to write notification log: %s", exc)

    # ------------------------------------------------------------------
    # PWR-202: Send Telegram Message
    # ------------------------------------------------------------------
    def send_telegram_message(self, chat_id: str, message: str) -> Dict[str, Any]:
        """PWR-202: Send a Telegram bot message using TELEGRAM_BOT_TOKEN env var."""
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        if not token:
            return {
                "power_id": "PWR-202",
                "status": "error",
                "error": "TELEGRAM_BOT_TOKEN environment variable not set.",
            }

        try:
            import requests  # type: ignore[import-untyped]

            url = f"https://api.telegram.org/bot{token}/sendMessage"
            resp = requests.post(url, json={"chat_id": chat_id, "text": message}, timeout=15)
            data = resp.json()
            ok = data.get("ok", False)

            entry = {
                "channel": "telegram",
                "chat_id": chat_id,
                "message": message[:100],
                "ok": ok,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self._append_notification_log(entry)

            return {
                "power_id": "PWR-202",
                "status": "success" if ok else "telegram_error",
                "telegram_response": data,
            }
        except ImportError:
            return {
                "power_id": "PWR-202",
                "status": "error",
                "error": "requests library not installed. pip install requests",
            }
        except Exception as exc:
            return {"power_id": "PWR-202", "status": "error", "error": str(exc)}

    # ------------------------------------------------------------------
    # PWR-203: Desktop Notification
    # ------------------------------------------------------------------
    def send_desktop_notification(self, title: str, body: str) -> Dict[str, Any]:
        """PWR-203: Windows toast notification via PowerShell."""
        if self._is_muted():
            return {
                "power_id": "PWR-203",
                "status": "muted",
                "muted_until": self._muted_until.isoformat() if self._muted_until else None,
            }

        ps_script = (
            "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, "
            "ContentType = WindowsRuntime] > $null; "
            "$template = [Windows.UI.Notifications.ToastNotificationManager]::"
            "GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02); "
            "$textNodes = $template.GetElementsByTagName('text'); "
            f"$textNodes.Item(0).AppendChild($template.CreateTextNode('{title.replace(chr(39), '')}')) > $null; "
            f"$textNodes.Item(1).AppendChild($template.CreateTextNode('{body.replace(chr(39), '')}')) > $null; "
            "$toast = [Windows.UI.Notifications.ToastNotification]::new($template); "
            "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('JARVIS').Show($toast)"
        )

        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True, text=True, timeout=10,
            )
            ok = result.returncode == 0

            entry = {
                "channel": "desktop",
                "title": title,
                "body": body[:100],
                "ok": ok,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self._append_notification_log(entry)

            return {
                "power_id": "PWR-203",
                "status": "success" if ok else "error",
                "stderr": result.stderr.strip() if result.stderr else None,
            }
        except Exception as exc:
            return {"power_id": "PWR-203", "status": "error", "error": str(exc)}

    # ------------------------------------------------------------------
    # PWR-205: Draft Email
    # ------------------------------------------------------------------
    def draft_email(self, to: str, subject: str, body: str) -> Dict[str, Any]:
        """PWR-205: Draft email stored as .eml in data/outbox/."""
        try:
            _OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
            msg = MIMEText(body)
            msg["To"] = to
            msg["Subject"] = subject
            msg["From"] = os.environ.get("JARVIS_EMAIL_FROM", "jarvis@localhost")
            msg["Date"] = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")

            draft_id = str(uuid.uuid4())[:8]
            draft_path = _OUTBOX_DIR / f"draft_{draft_id}.eml"
            draft_path.write_text(msg.as_string(), encoding="utf-8")

            return {
                "power_id": "PWR-205",
                "status": "success",
                "draft_id": draft_id,
                "draft_path": str(draft_path),
                "to": to,
                "subject": subject,
            }
        except Exception as exc:
            return {"power_id": "PWR-205", "status": "error", "error": str(exc)}

    # ------------------------------------------------------------------
    # PWR-206: Send Email (legacy entrypoint, no false success)
    # ------------------------------------------------------------------
    def send_email(self, draft_path: str, approval_token: Optional[str] = None) -> Dict[str, Any]:
        """PWR-206: Legacy send entrypoint.

        This power previously moved a local ``.eml`` into a sent folder and
        reported ``dispatched`` without any provider delivery.  It no longer
        performs delivery and never claims success.  Use PWR-052
        (``email_powers.send_email``), which binds approval to the SHA-256 of
        the exact RFC 822 bytes and returns ``SENT`` only after Gmail confirms
        a provider message id.
        """
        dp = Path(draft_path)
        if not dp.exists():
            return {
                "power_id": "PWR-206",
                "success": False,
                "status": "NOT_SENT",
                "error": f"Draft not found: {draft_path}",
            }

        return {
            "power_id": "PWR-206",
            "success": False,
            "status": "NOT_SENT",
            "draft_path": str(dp),
            "delegate_power": "PWR-052",
            "message": (
                "No message was sent. Email delivery requires approval bound to the "
                "exact content hash and a provider-confirmed message id. Use PWR-052 "
                "(email_powers.send_email) with a policy-gate approval token."
            ),
        }

    # ------------------------------------------------------------------
    # PWR-207: Urgent Alert
    # ------------------------------------------------------------------
    def urgent_alert(self, message: str, channels: Optional[List[str]] = None) -> Dict[str, Any]:
        """PWR-207: Multi-channel urgent alert."""
        channels = channels or ["desktop"]
        results: Dict[str, Any] = {}

        for ch in channels:
            if ch == "desktop":
                results["desktop"] = self.send_desktop_notification("🚨 URGENT", message)
            elif ch == "telegram":
                chat_id = os.environ.get("JARVIS_TELEGRAM_CHAT_ID", "")
                if chat_id:
                    results["telegram"] = self.send_telegram_message(chat_id, f"🚨 URGENT: {message}")
                else:
                    results["telegram"] = {"status": "skipped", "reason": "JARVIS_TELEGRAM_CHAT_ID not set"}
            else:
                results[ch] = {"status": "unsupported_channel"}

        return {
            "power_id": "PWR-207",
            "status": "success",
            "channels_attempted": channels,
            "results": results,
        }

    # ------------------------------------------------------------------
    # PWR-208: Schedule Message
    # ------------------------------------------------------------------
    def schedule_message(self, message: str, send_at: str) -> Dict[str, Any]:
        """PWR-208: Schedule a future message (stored for later dispatch)."""
        try:
            _SCHEDULED_DIR.mkdir(parents=True, exist_ok=True)
            msg_id = str(uuid.uuid4())[:8]
            entry = {
                "id": msg_id,
                "message": message,
                "send_at": send_at,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "status": "pending",
            }
            path = _SCHEDULED_DIR / f"scheduled_{msg_id}.json"
            path.write_text(json.dumps(entry, indent=2), encoding="utf-8")
            return {
                "power_id": "PWR-208",
                "status": "success",
                "scheduled": entry,
                "path": str(path),
            }
        except Exception as exc:
            return {"power_id": "PWR-208", "status": "error", "error": str(exc)}

    # ------------------------------------------------------------------
    # PWR-209: Contact Lookup
    # ------------------------------------------------------------------
    def contact_lookup(self, name: str) -> Dict[str, Any]:
        """PWR-209: Search contacts directory."""
        try:
            if not _CONTACTS_FILE.exists():
                return {
                    "power_id": "PWR-209",
                    "status": "success",
                    "matches": [],
                    "note": f"Contacts file not found at {_CONTACTS_FILE}. "
                            "Create it with a JSON array of objects.",
                }
            contacts = json.loads(_CONTACTS_FILE.read_text(encoding="utf-8"))
            query = name.lower()
            matches = [
                c for c in contacts
                if query in c.get("name", "").lower()
                or query in c.get("email", "").lower()
                or query in c.get("phone", "").lower()
            ]
            return {
                "power_id": "PWR-209",
                "status": "success",
                "query": name,
                "matches": matches,
                "count": len(matches),
            }
        except Exception as exc:
            return {"power_id": "PWR-209", "status": "error", "error": str(exc)}

    # ------------------------------------------------------------------
    # PWR-210: Message Template
    # ------------------------------------------------------------------
    def message_template(self, template_name: str, variables: Dict[str, str]) -> Dict[str, Any]:
        """PWR-210: Fill a named message template with variables."""
        # Built-in templates
        builtin: Dict[str, str] = {
            "meeting_reminder": "Hi {name}, reminder about our meeting at {time} on {date}. Topic: {topic}.",
            "follow_up": "Hi {name}, following up on {subject}. {message}",
            "thank_you": "Hi {name}, thank you for {reason}. {message}",
            "status_update": "Status Update — {project}: {status}. Next steps: {next_steps}",
        }

        # Check file-based templates
        template_text: Optional[str] = None
        template_file = _TEMPLATES_DIR / f"{template_name}.txt"
        if template_file.exists():
            template_text = template_file.read_text(encoding="utf-8")
        elif template_name in builtin:
            template_text = builtin[template_name]

        if template_text is None:
            return {
                "power_id": "PWR-210",
                "status": "error",
                "error": f"Template '{template_name}' not found.",
                "available_builtin": list(builtin.keys()),
            }

        try:
            rendered = template_text.format(**variables)
        except KeyError as ke:
            return {
                "power_id": "PWR-210",
                "status": "error",
                "error": f"Missing template variable: {ke}",
            }

        return {
            "power_id": "PWR-210",
            "status": "success",
            "template": template_name,
            "rendered": rendered,
        }

    # ------------------------------------------------------------------
    # PWR-211: Read Telegram Updates
    # ------------------------------------------------------------------
    def read_telegram_updates(self) -> Dict[str, Any]:
        """PWR-211: Check Telegram bot updates (getUpdates)."""
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        if not token:
            return {
                "power_id": "PWR-211",
                "status": "error",
                "error": "TELEGRAM_BOT_TOKEN environment variable not set.",
            }

        try:
            import requests  # type: ignore[import-untyped]

            url = f"https://api.telegram.org/bot{token}/getUpdates"
            resp = requests.get(url, params={"limit": 20, "timeout": 5}, timeout=15)
            data = resp.json()
            updates = data.get("result", [])

            return {
                "power_id": "PWR-211",
                "status": "success",
                "update_count": len(updates),
                "updates": updates,
            }
        except ImportError:
            return {
                "power_id": "PWR-211",
                "status": "error",
                "error": "requests library not installed.",
            }
        except Exception as exc:
            return {"power_id": "PWR-211", "status": "error", "error": str(exc)}

    # ------------------------------------------------------------------
    # PWR-212: Notification History
    # ------------------------------------------------------------------
    def notification_history(self, limit: int = 20) -> Dict[str, Any]:
        """PWR-212: Recent notification log."""
        try:
            if not _NOTIFICATION_LOG.exists():
                return {
                    "power_id": "PWR-212",
                    "status": "success",
                    "entries": [],
                    "count": 0,
                }
            log = json.loads(_NOTIFICATION_LOG.read_text(encoding="utf-8"))
            entries = log[-limit:]
            return {
                "power_id": "PWR-212",
                "status": "success",
                "entries": entries,
                "count": len(entries),
                "total_logged": len(log),
            }
        except Exception as exc:
            return {"power_id": "PWR-212", "status": "error", "error": str(exc)}

    # ------------------------------------------------------------------
    # PWR-213: Mute Notifications
    # ------------------------------------------------------------------
    def mute_notifications(self, duration_min: int = 30) -> Dict[str, Any]:
        """PWR-213: Suppress notifications temporarily."""
        from datetime import timedelta

        self._muted_until = datetime.now(timezone.utc) + timedelta(minutes=duration_min)
        return {
            "power_id": "PWR-213",
            "status": "success",
            "muted_until": self._muted_until.isoformat(),
            "duration_min": duration_min,
        }

    # ------------------------------------------------------------------
    # PWR-214: Broadcast
    # ------------------------------------------------------------------
    def broadcast(self, message: str, channels: List[str]) -> Dict[str, Any]:
        """PWR-214: Send message to multiple channels."""
        results: Dict[str, Any] = {}

        for ch in channels:
            if ch == "desktop":
                results["desktop"] = self.send_desktop_notification("JARVIS Broadcast", message)
            elif ch == "telegram":
                chat_id = os.environ.get("JARVIS_TELEGRAM_CHAT_ID", "")
                if chat_id:
                    results["telegram"] = self.send_telegram_message(chat_id, message)
                else:
                    results["telegram"] = {"status": "skipped", "reason": "JARVIS_TELEGRAM_CHAT_ID not set"}
            elif ch == "email":
                default_to = os.environ.get("JARVIS_BROADCAST_EMAIL", "")
                if default_to:
                    results["email"] = self.draft_email(default_to, "JARVIS Broadcast", message)
                else:
                    results["email"] = {"status": "skipped", "reason": "JARVIS_BROADCAST_EMAIL not set"}
            else:
                results[ch] = {"status": "unsupported_channel"}

        return {
            "power_id": "PWR-214",
            "status": "success",
            "channels": channels,
            "results": results,
        }


communication_powers = CommunicationPowers()
