"""JARVIS Email Powers (PWR-051 to PWR-055).

Provides deterministic RFC 822 / MIME (.eml) email drafting, outbox storage,
cryptographic SHA-256 draft integrity, and policy-gated sending.
"""

from __future__ import annotations
import os
import re
import smtplib

from email.message import EmailMessage
from email.utils import formatdate, make_msgid
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

from jarvis.config import settings
from jarvis.core.audit import audit_ledger
from jarvis.core.logger import get_logger
from jarvis.core.policy_gate import policy_gate
from jarvis.core.capability_guard import capability_guard, CapabilityStatus
from jarvis.core.evidence import TrustResult, Evidence, CapabilityState
from jarvis.core.trust_layer import trust_layer

logger = get_logger("powers.email")


class EmailPowers:
    """Implementations for email drafting and Tier-2 gated sending."""

    def __init__(self, outbox_dir: Optional[Path] = None):
        self.outbox_dir = outbox_dir or (settings.data_dir / "outbox")
        self.outbox_dir.mkdir(parents=True, exist_ok=True)

    def draft_email(
        self,
        to: str,
        subject: str,
        body: str,
        from_addr: Optional[str] = None,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        outbox_dir: Optional[str | Path] = None,
    ) -> Dict[str, Any]:
        """PWR-051: Deterministically composes and saves an RFC 822 .eml draft to the outbox."""
        target_outbox = Path(outbox_dir) if outbox_dir else self.outbox_dir
        target_outbox.mkdir(parents=True, exist_ok=True)

        msg = EmailMessage()
        msg["To"] = to
        sender = from_addr or "jarvis@localhost"
        msg["From"] = sender
        msg["Subject"] = subject
        msg["Date"] = formatdate(localtime=True)
        msg_id = make_msgid(domain="jarvis.local")
        msg["Message-ID"] = msg_id
        if cc:
            msg["Cc"] = cc
        if bcc:
            msg["Bcc"] = bcc
        msg.set_content(body)

        raw_bytes = msg.as_bytes()
        draft_sha256 = hashlib.sha256(raw_bytes).hexdigest()

        # Filename based on hash prefix
        filename = f"draft_{draft_sha256[:12]}.eml"
        file_path = target_outbox / filename
        file_path.write_bytes(raw_bytes)

        audit_ledger.record(
            actor="EmailPowers",
            action="DRAFT_EMAIL",
            target=str(file_path),
            payload={
                "to": to,
                "subject": subject,
                "sha256": draft_sha256,
                "msg_id": msg_id,
            },
            result="SUCCESS",
        )

        return {
            "power_id": "PWR-051",
            "status": "DRAFT_SAVED",
            "file_path": str(file_path),
            "sha256": draft_sha256,
            "message_id": msg_id,
            "to": to,
            "subject": subject,
            "preview": body[:160] + "..." if len(body) > 160 else body,
        }

    def send_email(
        self,
        draft_path: str,
        task_id: str = "send_email_task",
        approval_token: Optional[str] = None,
        archive_only: bool = False,
    ) -> Dict[str, Any]:
        """PWR-052: Sends an email draft strictly gated behind Tier-2 cryptographic approval."""
        p = Path(draft_path)
        if not p.exists():
            return {
                "power_id": "PWR-052",
                "success": False,
                "error": f"Draft file not found: {draft_path}",
            }

        raw_bytes = p.read_bytes()
        content_hash = hashlib.sha256(raw_bytes).hexdigest()
        exec_payload = {"draft_path": str(p), "sha256": content_hash}

        # Tier 3 (OUTBOUND_COMM) Policy Evaluation
        allowed, reason, pending_approval = policy_gate.evaluate_execution(
            task_id=task_id,
            power_id="send_email",
            privilege_level=3,
            payload=exec_payload,
            approval_token=approval_token,
        )

        if not allowed:
            return {
                "power_id": "PWR-052",
                "success": False,
                "status": "APPROVAL_REQUIRED",
                "error": reason or "Sending outbound email requires Tier-2 human cryptographic sign-off.",
                "pending_approval": pending_approval,
                "draft_sha256": content_hash,
                "draft_path": str(p),
            }

        # Approved: Deliver through configured SMTP or archive locally
        logger.info(f"Verified approval token for sending draft {p.name}. Dispatching email.")

        import email
        parsed_msg = email.message_from_bytes(raw_bytes)
        smtp_host = os.getenv("SMTP_HOST") or getattr(settings, "smtp_host", None)
        smtp_port = int(os.getenv("SMTP_PORT") or getattr(settings, "smtp_port", 587))
        smtp_user = os.getenv("SMTP_USER") or getattr(settings, "smtp_user", None) or os.getenv("GMAIL_USER")
        smtp_pass = os.getenv("SMTP_PASSWORD") or getattr(settings, "smtp_password", None) or os.getenv("GMAIL_APP_PASSWORD")
        smtp_use_tls = getattr(settings, "smtp_use_tls", True)

        # Delivery Provider Evaluation: SMTP or Explicit Local Archival
        if archive_only:
            archive_dir = p.parent / "archived"
            archive_dir.mkdir(parents=True, exist_ok=True)
            dest = archive_dir / p.name
            p.rename(dest)
            audit_ledger.record(
                actor="EmailPowers",
                action="ARCHIVE_DRAFT",
                target=str(dest),
                payload={"sha256": content_hash, "task_id": task_id},
                result="ARCHIVED",
            )
            return {
                "power_id": "PWR-052",
                "success": False,
                "status": "ARCHIVED_NOT_SENT",
                "archive_path": str(dest),
                "draft_sha256": content_hash,
            }

        if smtp_host and smtp_user and smtp_pass:
            try:
                if smtp_port == 465:
                    with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=15) as server:
                        server.login(smtp_user, smtp_pass)
                        server.send_message(parsed_msg)
                else:
                    with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
                        if smtp_use_tls:
                            server.starttls()
                        server.login(smtp_user, smtp_pass)
                        server.send_message(parsed_msg)
                logger.info(f"Delivered draft {p.name} via SMTP server {smtp_host}:{smtp_port}")

                audit_ledger.record(
                    actor="EmailPowers",
                    action="SEND_EMAIL",
                    target=str(p),
                    payload={"sha256": content_hash, "task_id": task_id, "delivery_channel": "DELIVERED_VIA_SMTP"},
                    result="SUCCESS",
                )

                # Move to sent/ archive only upon genuine provider delivery
                sent_dir = p.parent / "sent"
                sent_dir.mkdir(parents=True, exist_ok=True)
                dest = sent_dir / p.name
                p.rename(dest)

                return {
                    "power_id": "PWR-052",
                    "success": True,
                    "status": "SENT",
                    "delivery_channel": "DELIVERED_VIA_SMTP",
                    "archive_path": str(dest),
                    "sha256": content_hash,
                }
            except Exception as e:
                logger.error(f"Failed to deliver email via SMTP: {e}")
                audit_ledger.record(
                    actor="EmailPowers",
                    action="SEND_EMAIL_FAILED",
                    target=str(p),
                    payload={"sha256": content_hash, "task_id": task_id, "error": str(e)},
                    result="FAILURE",
                )
                return {
                    "power_id": "PWR-052",
                    "success": False,
                    "status": "DELIVERY_FAILED",
                    "error": f"SMTP transmission failed: {str(e)}",
                    "draft_sha256": content_hash,
                }

        # Neither SMTP credentials nor active OAuth provider configured.
        # Strict truthfulness: NEVER report SENT, NEVER move to sent/, NEVER log audit SUCCESS.
        logger.warning(f"No delivery provider configured for draft {p.name}. Retaining draft in outbox.")
        audit_ledger.record(
            actor="EmailPowers",
            action="SEND_EMAIL_REJECTED",
            target=str(p),
            payload={"sha256": content_hash, "task_id": task_id, "reason": "UNCONFIGURED_DELIVERY_PROVIDER"},
            result="REJECTED_UNCONFIGURED",
        )
        return {
            "power_id": "PWR-052",
            "success": False,
            "status": "NOT_CONFIGURED",
            "error": "No SMTP credentials or OAuth delivery provider configured. Draft retained in outbox.",
            "draft_path": str(p),
            "draft_sha256": content_hash,
        }

    def list_outbox(self, outbox_dir: Optional[str | Path] = None) -> Dict[str, Any]:
        """PWR-053: Lists pending email drafts currently waiting in the outbox."""
        target_outbox = Path(outbox_dir) if outbox_dir else self.outbox_dir
        if not target_outbox.exists():
            return {"power_id": "PWR-053", "count": 0, "drafts": []}

        drafts: List[Dict[str, Any]] = []
        for eml_file in target_outbox.glob("*.eml"):
            try:
                stat = eml_file.stat()
                drafts.append(
                    {
                        "filename": eml_file.name,
                        "path": str(eml_file),
                        "size_bytes": stat.st_size,
                        "created_at": stat.st_ctime,
                    }
                )
            except Exception as e:
                logger.warning(f"Error inspecting draft {eml_file}: {e}")

        return {
            "power_id": "PWR-053",
            "count": len(drafts),
            "drafts": drafts,
        }


    def _parse_email_obj(self, msg: Any, mail_id: str) -> Dict[str, Any]:
        """Helper to extract headers and body text from email.message.EmailMessage."""
        from email.header import decode_header

        def _decode_hdr(header_val: str) -> str:
            if not header_val:
                return ""
            parts = decode_header(header_val)
            res = ""
            for val, enc in parts:
                if isinstance(val, bytes):
                    res += val.decode(enc or "utf-8", errors="ignore")
                else:
                    res += str(val)
            return res

        subject = _decode_hdr(msg.get("Subject", "No Subject"))
        sender = _decode_hdr(msg.get("From", "Unknown"))
        date = msg.get("Date", "")

        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                if ctype == "text/plain":
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            body += payload.decode("utf-8", errors="ignore")
                    except Exception:
                        pass
        else:
            try:
                payload = msg.get_payload(decode=True)
                if payload:
                    body = payload.decode("utf-8", errors="ignore")
                else:
                    body = str(msg.get_payload() or "")
            except Exception:
                body = str(msg.get_payload() or "")

        return {
            "id": mail_id,
            "from": sender,
            "subject": subject,
            "date": date,
            "body": body.strip(),
        }

    def _derive_action_from_content(self, subject: str, sender: str, body: str) -> str:
        """Derives genuine action items from actual email content instead of hardcoded strings."""
        lower_body = body.lower()
        lower_subj = subject.lower()
        combined = f"{lower_subj} {lower_body}"

        if "interview" in combined:
            dates = re.findall(r"\b(?:mon|tue|wed|thu|fri|sat|sun|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b[\w\s,:-]*", body, re.IGNORECASE)
            if dates:
                return f"Review and reply regarding interview invitation with availability ({dates[0].strip()[:40]})"
            return "Review and reply to interview invitation with availability"
        elif "hackathon" in combined or "contest" in combined:
            return "Review hackathon details, schedule, and team registration requirements"
        elif "deadline" in combined or "urgent" in combined or "due" in combined:
            return f"Action required on critical deadline mentioned in email: {subject[:50]}"
        elif "offer" in combined:
            return "Review formal offer letter and compensation terms"
        return f"Review communication from {sender[:40]}"

    def scan_inbox_for_opportunities(
        self,
        inbox_dir: Optional[str | Path] = None,
        query: str = "opportunity OR offer OR interview OR internship OR hackathon",
        limit: int = 10,
    ) -> Dict[str, Any]:
        """PWR-191 & PWR-192: Connects to Gmail via IMAP or scans local incoming mailbox
        for career opportunities, hackathon invitations, and critical academic deadlines.
        Always verifies genuine capability and never fabricates results.
        """
        # Step 1: Pre-flight capability check
        status = capability_guard.check_gmail()
        has_creds = bool(
            os.getenv("GMAIL_USER")
            or os.getenv("GMAIL_ADDRESS")
            or os.getenv("GMAIL_APP_PASSWORD")
            or os.getenv("GMAIL_PASSWORD")
            or os.getenv("GMAIL_OAUTH_TOKEN")
        )
        if (status == CapabilityStatus.DISCONNECTED or not has_creds) and not inbox_dir:
            return {
                "power_id": "PWR-191",
                "status": "DISCONNECTED",
                "connected": False,
                "opportunities_found": 0,
                "opportunities": [],
                "fabricated": False,
                "message": "Email is not configured. Set GMAIL_USER and GMAIL_APP_PASSWORD (or SMTP/IMAP credentials) in your .env file.",
            }

        gmail_user = os.getenv("GMAIL_USER") or os.getenv("GMAIL_ADDRESS") or ""
        gmail_pass = os.getenv("GMAIL_APP_PASSWORD") or os.getenv("GMAIL_PASSWORD")

        live_sync = False
        parsed_emails: List[Dict[str, Any]] = []

        # Step 2: Attempt live IMAP connection if credentials are present
        if gmail_user and gmail_pass:
            try:
                import imaplib
                import email

                imap_server = getattr(settings, "imap_host", "imap.gmail.com") or "imap.gmail.com"
                imap_port = int(getattr(settings, "imap_port", 993) or 993)
                mail = imaplib.IMAP4_SSL(imap_server, imap_port, timeout=10)
                mail.login(gmail_user, gmail_pass)
                mail.select("INBOX")
                status_imap, data = mail.search(None, 'ALL')
                if status_imap == "OK" and data[0]:
                    mail_ids = data[0].split()[-limit:]
                    for mid in reversed(mail_ids):
                        _, msg_data = mail.fetch(mid, "(RFC822)")
                        if msg_data and msg_data[0]:
                            raw_msg = msg_data[0][1]
                            msg = email.message_from_bytes(raw_msg)
                            parsed_emails.append(self._parse_email_obj(msg, f"gmail_{mid.decode()}"))
                    live_sync = True
                mail.close()
                mail.logout()
            except Exception as e:
                logger.warning(f"Live Gmail IMAP error: {e}")
                if not inbox_dir:
                    return {
                        "power_id": "PWR-191",
                        "status": "NETWORK_ERROR",
                        "connected": False,
                        "opportunities_found": 0,
                        "opportunities": [],
                        "fabricated": False,
                        "message": f"Failed to connect to email server: {e}",
                    }

        # Step 3: Explicit directory scan only if caller provided a custom directory fixture
        if not parsed_emails and inbox_dir:
            target_inbox = Path(inbox_dir)
            if target_inbox.exists():
                import email
                for eml in sorted(target_inbox.glob("*.eml"), reverse=True)[:limit]:
                    try:
                        raw = eml.read_bytes()
                        msg = email.message_from_bytes(raw)
                        parsed_emails.append(self._parse_email_obj(msg, eml.name))
                    except Exception as e:
                        logger.warning(f"Error parsing eml {eml}: {e}")

        # Step 4: If no real emails found after all attempts, return honest empty result
        if not parsed_emails:
            return {
                "power_id": "PWR-191",
                "status": "CONNECTED_EMPTY",
                "fabricated": False,
                "opportunities_found": 0,
                "opportunities": [],
                "message": "No emails found in inbox.",
            }

        # Step 5: Categorize real opportunities from actual email content
        opportunities: List[Dict[str, Any]] = []
        for em in parsed_emails:
            subj = em["subject"]
            sender = em["from"]
            body = em["body"]
            subj_lower = subj.lower()
            body_lower = body.lower()

            if "interview" in subj_lower or "shortlist" in subj_lower:
                cat = "Interview Shortlist"
                urgency = "HIGH (Action Required)"
            elif "hackathon" in subj_lower or "contest" in subj_lower:
                cat = "Hackathon Invitation"
                urgency = "MEDIUM (Upcoming Briefing)"
            elif "urgent" in subj_lower or "deadline" in subj_lower or "due" in subj_lower:
                cat = "Academic / Project Deadline"
                urgency = "CRITICAL"
            elif "offer" in subj_lower:
                cat = "Offer Letter"
                urgency = "HIGH (Action Required)"
            else:
                cat = "General Opportunity"
                urgency = "NORMAL"

            action = self._derive_action_from_content(subj, sender, body)

            opportunities.append({
                "source_id": em["id"],
                "from": sender,
                "subject": subj,
                "date": em["date"],
                "category": cat,
                "urgency": urgency,
                "recommended_action": action,
                "snippet": body[:250] + ("..." if len(body) > 250 else ""),
            })

        return {
            "power_id": "PWR-191",
            "account": gmail_user,
            "status": "CONNECTED",
            "fabricated": False,
            "live_sync_active": live_sync,
            "opportunities_found": len(opportunities),
            "urgent_count": sum(1 for o in opportunities if "HIGH" in o["urgency"] or "CRITICAL" in o["urgency"]),
            "opportunities": opportunities,
            "setup_note": "Live Gmail sync active." if live_sync else "Scanned local inbox store.",
        }


email_powers = EmailPowers()
