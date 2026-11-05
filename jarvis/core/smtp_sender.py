"""JARVIS Gmail SMTP Sender.

Delivers outbound email through Gmail SMTP (smtp.gmail.com:465) producing a
structured result. Respects the First Law: no send is reported success unless
the SMTP handshake + send actually completed, or an honest failure is returned.
"""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from typing import Any, Dict, List, Optional

from jarvis.config import settings
from jarvis.core.logger import get_logger

logger = get_logger("core.smtp")

DEFAULT_SMTP_HOST = "smtp.gmail.com"
DEFAULT_SMTP_PORT = 465


class SmtpSender:
    """Gmail SMTP delivery client producing evidence-rich results."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        user: Optional[str] = None,
        app_password: Optional[str] = None,
        sender_name: Optional[str] = None,
    ) -> None:
        self.host = host or getattr(settings, "smtp_host", None) or DEFAULT_SMTP_HOST
        self.port = int(port or getattr(settings, "smtp_port", None) or DEFAULT_SMTP_PORT)
        self.user = user or getattr(settings, "smtp_user", None) or "jarvis007@gmail.com"
        self.app_password = app_password or getattr(settings, "smtp_app_password", None) or None
        self.sender_name = sender_name or getattr(settings, "smtp_sender_name", None) or "JARVIS"

    def is_configured(self) -> bool:
        user = (self.user or "").strip()
        return bool(user) and bool((self.app_password or "").strip()) and "@" in user

    def send_email(
        self,
        from_addr: Optional[str] = None,
        to_addrs: Optional[List[str]] = None,
        subject: str = "",
        body: str = "",
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        timeout: int = 20,
    ) -> Dict[str, Any]:
        """Send a single email via Gmail SMTP. Returns evidence-rich result."""
        sender = (from_addr or self.user or "jarvis007@gmail.com").strip()
        recipients = [r.strip() for r in (to_addrs or []) if r and "@" in r]
        if not recipients:
            return {
                "success": False,
                "status": "INVALID_RECIPIENTS",
                "error": "No valid recipient email addresses provided.",
                "evidence": {"from": sender},
            }

        if not self.is_configured():
            return {
                "success": False,
                "status": "SMTP_NOT_CONFIGURED",
                "error": "Gmail SMTP is not configured. Set SMTP_USER and SMTP_APP_PASSWORD.",
                "evidence": {"from": sender, "to": recipients, "subject": subject, "smtp_configured": False},
            }

        from email.utils import formatdate, make_msgid
        import smtplib
        import ssl

        msg = EmailMessage()
        msg["From"] = sender
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = subject
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain="gmail.com")
        if cc:
            msg["Cc"] = cc
        if bcc:
            msg["Bcc"] = bcc
        msg.set_content(body)

        try:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(self.host, self.port, context=ctx, timeout=timeout) as server:
                server.login(self.user, self.app_password)
                server.send_message(msg)
            logger.info(f"SMTP send OK: {sender} -> {recipients} ({subject})")
            return {
                "success": True,
                "status": "SENT",
                "evidence": {
                    "smtp_host": self.host,
                    "smtp_port": self.port,
                    "from": sender,
                    "to": recipients,
                    "subject": subject,
                    "bytes_sent": len(msg.as_bytes()),
                },
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"SMTP send failed: {exc}")
            return {
                "success": False,
                "status": "SMTP_SEND_FAILED",
                "error": f"SMTP delivery failed: {exc}",
                "evidence": {"from": sender, "to": recipients, "subject": subject, "configured": True},
            }


smtp_sender = SmtpSender()
