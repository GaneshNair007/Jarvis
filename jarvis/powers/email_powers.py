"""JARVIS Email Powers (PWR-051 to PWR-055).

Provides deterministic RFC 822 / MIME (.eml) email drafting, outbox storage,
cryptographic SHA-256 draft integrity, and policy-gated sending.
"""

from __future__ import annotations

from email.message import EmailMessage
from email.utils import formatdate, make_msgid
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

from jarvis.config import settings
from jarvis.core.audit import audit_ledger
from jarvis.core.logger import get_logger
from jarvis.core.policy_gate import policy_gate

logger = get_logger("powers.email")


class EmailPowers:
    """Implementations for email drafting and Tier-2 gated sending.

    Delivery is performed exclusively through the Gmail integration (OAuth 2.0).
    A local ``.eml`` file move is never reported as a sent email.  ``SENT`` is
    returned only when Gmail confirms a provider message id.
    """

    def __init__(self, outbox_dir: Optional[Path] = None, gmail_client: Any = None):
        self.outbox_dir = outbox_dir or (settings.data_dir / "outbox")
        self.outbox_dir.mkdir(parents=True, exist_ok=True)
        self._gmail_client = gmail_client

    @property
    def gmail_client(self) -> Any:
        """Lazily construct the real Gmail API client (never at import time)."""
        if self._gmail_client is None:
            from integrations.google.gmail_api import GoogleApiClient

            self._gmail_client = GoogleApiClient()
        return self._gmail_client

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

        # Approved.  Delivery must be confirmed by a real provider.
        from integrations.google.gmail_api import GmailApiError

        try:
            provider_result = self.gmail_client.send_raw_message(
                raw_bytes=raw_bytes,
                expected_content_hash=content_hash,
            )
        except GmailApiError as exc:
            logger.warning("Gmail delivery not confirmed for draft %s: %s", p.name, exc.error)
            return {
                "power_id": "PWR-052",
                "success": False,
                "status": "NOT_SENT",
                "error": f"Gmail delivery not confirmed: {exc}",
                "reason": exc.description or exc.error,
                "draft_sha256": content_hash,
                "draft_path": str(p),
                "provider_message_id": None,
                "setup_command": "python -m integrations.google.oauth_flow connect",
            }
        except Exception as exc:  # never claim success on an unknown failure
            logger.warning("Email dispatch failed for draft %s (%s)", p.name, type(exc).__name__)
            return {
                "power_id": "PWR-052",
                "success": False,
                "status": "NOT_SENT",
                "error": f"Email dispatch failed ({type(exc).__name__})",
                "draft_sha256": content_hash,
                "draft_path": str(p),
                "provider_message_id": None,
            }

        message_id = provider_result.get("message_id") if isinstance(provider_result, dict) else None
        if not message_id:
            return {
                "power_id": "PWR-052",
                "success": False,
                "status": "NOT_SENT",
                "error": "The provider did not return a message id; delivery is unconfirmed.",
                "draft_sha256": content_hash,
                "draft_path": str(p),
                "provider_message_id": None,
            }

        audit_ledger.record(
            actor="EmailPowers",
            action="SEND_EMAIL",
            target=str(p),
            payload={
                "sha256": content_hash,
                "task_id": task_id,
                "provider": provider_result.get("provider", "gmail"),
                "message_id": message_id,
            },
            result="SUCCESS",
        )

        # Archive only after the provider confirmed the message id.
        sent_dir = p.parent / "sent"
        sent_dir.mkdir(parents=True, exist_ok=True)
        dest = sent_dir / p.name
        p.rename(dest)

        return {
            "power_id": "PWR-052",
            "success": True,
            "status": "SENT",
            "provider": provider_result.get("provider", "gmail"),
            "message_id": message_id,
            "provider_message_id": message_id,
            "thread_id": provider_result.get("thread_id"),
            "archive_path": str(dest),
            "sha256": content_hash,
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

    def scan_inbox_for_opportunities(
        self,
        inbox_dir: Optional[str | Path] = None,
        query: str = "opportunity OR offer OR interview OR internship OR hackathon",
        limit: int = 10,
    ) -> Dict[str, Any]:
        """PWR-191 & PWR-192: Scan the Gmail account (OAuth 2.0) for opportunities.

        There is no IMAP or app-password path.  If Gmail is not connected, the
        local ``data/inbox/*.eml`` store is scanned as an explicitly labelled
        fallback.  Email content is always treated as untrusted external data.
        """
        parsed_emails: List[Dict[str, Any]] = []
        live_sync = False
        source = "local_inbox"

        # 1. Real Gmail read through the official API (OAuth 2.0).
        try:
            listing = self.gmail_client.list_messages(
                query=query,
                max_results=limit,
                include_metadata=False,
            )
            live_sync = True
            source = "gmail_oauth"
            for stub in listing.get("messages", []):
                message_id = stub.get("id")
                if not message_id:
                    continue
                detail = self.gmail_client.get_message(message_id)
                parsed_emails.append(
                    {
                        "id": detail.get("id") or message_id,
                        "from": detail.get("from", ""),
                        "subject": detail.get("subject", ""),
                        "date": detail.get("date", ""),
                        "body": detail.get("body_text", ""),
                    }
                )
        except Exception as exc:
            # Missing credentials / disconnected account / transient API error:
            # fall back to the local store and report the truth.
            logger.info(
                "Gmail inbox scan unavailable (%s); using local inbox fallback.",
                type(exc).__name__,
            )

        # 2. Local incoming store fallback (data/inbox/*.eml)
        if not parsed_emails and not live_sync:
            target_inbox = Path(inbox_dir) if inbox_dir else (settings.data_dir / "inbox")
            if target_inbox.exists():
                import email

                for eml in sorted(target_inbox.glob("*.eml"), reverse=True)[:limit]:
                    try:
                        raw = eml.read_bytes()
                        msg = email.message_from_bytes(raw)
                        parsed_emails.append(self._parse_email_obj(msg, eml.name))
                    except Exception as e:
                        logger.warning(f"Error parsing local eml {eml}: {e}")

        # 3. Categorize opportunities & extract recommendations
        opportunities: List[Dict[str, Any]] = []
        for em in parsed_emails:
            subj = em["subject"].lower()
            body = em["body"].lower()

            if "interview" in subj or "shortlist" in subj:
                cat = "Interview Shortlist"
                urgency = "HIGH (Action Required)"
                action = "Review the message and reply with available interview slots."
            elif "hackathon" in subj or "contest" in subj:
                cat = "Hackathon Invitation"
                urgency = "MEDIUM (Upcoming Briefing)"
                action = "Confirm team registration and review the event brief."
            elif "urgent" in subj or "assignment" in subj or "deadline" in subj or "submission" in subj:
                cat = "Academic / Project Deadline"
                urgency = "CRITICAL"
                action = "Review the deadline and submit the required material."
            else:
                cat = "General Opportunity"
                urgency = "NORMAL"
                action = "Review message"

            opportunities.append({
                "source_id": em["id"],
                "from": em["from"],
                "subject": em["subject"],
                "date": em["date"],
                "category": cat,
                "urgency": urgency,
                "recommended_action": action,
                "snippet": em["body"][:250] + ("..." if len(em["body"]) > 250 else ""),
                "content_trust": "UNTRUSTED_EXTERNAL_DATA",
            })

        if live_sync:
            setup_note = "Live Gmail sync active through OAuth 2.0."
        else:
            setup_note = (
                "Gmail is not connected. Scanned the local data/inbox store only. "
                "Run `python -m integrations.google.oauth_flow connect` to authorize "
                "the assistant account (OAuth 2.0, no password or app password)."
            )

        return {
            "power_id": "PWR-191",
            "account": settings.assistant_email,
            "auth_method": "oauth2" if live_sync else "local_inbox",
            "source": source,
            "live_sync_active": live_sync,
            "opportunities_found": len(opportunities),
            "urgent_count": sum(1 for o in opportunities if "HIGH" in o["urgency"] or "CRITICAL" in o["urgency"]),
            "opportunities": opportunities,
            "content_trust": "UNTRUSTED_EXTERNAL_DATA",
            "setup_note": setup_note,
        }


email_powers = EmailPowers()

