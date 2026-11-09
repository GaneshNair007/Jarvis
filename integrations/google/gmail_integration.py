"""Real Gmail integration using the official Google Gmail REST API.

Security invariants:

- OAuth 2.0 only (no IMAP password login, no app passwords, no cookies).
- Least-privilege scopes: gmail.readonly, gmail.compose, gmail.send.
- Sending is approval-gated by the integration policy engine.
- Approval is bound to the SHA-256 of the exact RFC 822 bytes.
- "SENT" is returned only when Gmail returns a real message id.
- Incoming email is marked as untrusted external data.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from integrations.base.base_integration import BaseIntegration
from integrations.base.credential_manager import credential_manager
from integrations.base.integration_health import HealthReport, IntegrationStatus
from integrations.base.oauth_manager import oauth_manager
from integrations.google.gmail_api import (
    GmailApiError,
    GmailDeliveryUnconfirmed,
    GmailNotConnected,
    GoogleApiClient,
)
from jarvis.config import settings
from jarvis.core.logger import get_logger

logger = get_logger("integrations.gmail")

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.send",
]


class GmailIntegration(BaseIntegration):
    """Gmail read/draft/send integration with approval-bound delivery."""

    INTEGRATION_ID = "google_gmail"

    def __init__(self, api: Optional[GoogleApiClient] = None):
        super().__init__(
            integration_id=self.INTEGRATION_ID,
            display_name="Google Gmail",
            category="communication",
            description=(
                "Read, search, summarize, draft and approval-gated send through the official Gmail API "
                "using the dedicated JARVIS Google identity."
            ),
            required_credentials=["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"],
            required_scopes=list(GMAIL_SCOPES),
            danger_level="high",
            default_approval_tier=2,
            rate_limit_rpm=60,
            cost_model="free",
            data_sensitivity="high",
            documentation_url="https://developers.google.com/gmail/api",
        )
        self.api = api or GoogleApiClient(oauth=oauth_manager)
        self.oauth = self.api.oauth
        self.account_email: Optional[str] = None
        self.last_error: Optional[str] = None

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def connect(self, credentials: Optional[Dict[str, str]] = None) -> bool:
        if credentials:
            for key, value in credentials.items():
                if key in self.required_credentials and value:
                    credential_manager.set_override(key, value)

        is_valid, missing = credential_manager.validate_credentials(self.required_credentials)
        if not is_valid:
            self.last_error = f"Missing OAuth client configuration: {', '.join(missing)}"
            self.connected = False
            return False

        try:
            profile = self.api.get_profile()
            email = str(profile.get("emailAddress") or "")
            if not email:
                self.last_error = "Gmail profile did not return an account email"
                self.connected = False
                return False
            expected = (settings.assistant_email or "").strip().lower()
            if expected and email.strip().lower() != expected:
                self.last_error = (
                    f"Connected Google account {email} does not match the configured "
                    f"assistant identity {settings.assistant_email}"
                )
                # Do not keep a token for the wrong account.
                self.oauth_revoke()
                self.connected = False
                return False

            self.oauth.set_account_email("google", email)
            self.account_email = email
            self.connected = True
            self.last_error = None
            return True
        except (GmailNotConnected, GmailApiError) as exc:
            self.last_error = str(exc)
            self.connected = False
            return False
        except Exception as exc:  # never include token material
            self.last_error = f"Gmail connection failed ({type(exc).__name__})"
            self.connected = False
            return False

    def disconnect(self) -> bool:
        revoked = self.oauth_revoke()
        self.account_email = None
        self.connected = False
        self.enabled = False
        return revoked

    def oauth_revoke(self) -> bool:
        try:
            return self.oauth.revoke_token("google")
        except Exception as exc:
            logger.warning("Google token revocation failed (%s); local token deleted.", type(exc).__name__)
            return False

    def health_check(self) -> HealthReport:
        is_valid, missing = credential_manager.validate_credentials(self.required_credentials)
        if not is_valid:
            guide = credential_manager.get_setup_guide("google_gmail")
            return HealthReport(
                integration_id=self.integration_id,
                status=IntegrationStatus.UNCONFIGURED,
                connected=False,
                enabled=self.enabled,
                kill_switched=self.kill_switched,
                details={"missing_credentials": missing, "setup_guide": guide},
                errors=[],
            )

        status = self.oauth.status("google")
        if not status.get("connected"):
            return HealthReport(
                integration_id=self.integration_id,
                status=IntegrationStatus.DISCONNECTED,
                connected=False,
                enabled=self.enabled,
                kill_switched=self.kill_switched,
                details={
                    "account_email": status.get("account_email"),
                    "scopes": status.get("scopes", []),
                    "setup_command": "python -m integrations.google.oauth_flow connect",
                },
                errors=[],
            )

        try:
            profile = self.api.get_profile()
            email = str(profile.get("emailAddress") or "")
            expected = (settings.assistant_email or "").strip().lower()
            if expected and email.strip().lower() != expected:
                return HealthReport(
                    integration_id=self.integration_id,
                    status=IntegrationStatus.DEGRADED,
                    connected=False,
                    enabled=self.enabled,
                    kill_switched=self.kill_switched,
                    details={"account_email": email, "expected": settings.assistant_email},
                    errors=["Connected Google account does not match the assistant identity"],
                )
            self.account_email = email
            self.connected = True
            return HealthReport(
                integration_id=self.integration_id,
                status=IntegrationStatus.HEALTHY,
                connected=True,
                enabled=self.enabled,
                kill_switched=self.kill_switched,
                details={
                    "account_email": email,
                    "scopes": status.get("scopes", []),
                    "has_refresh_token": status.get("has_refresh_token", False),
                    "expires_at": status.get("expires_at"),
                    "auth_method": "oauth2",
                },
                errors=[],
            )
        except GmailNotConnected as exc:
            return HealthReport(
                integration_id=self.integration_id,
                status=IntegrationStatus.DISCONNECTED,
                connected=False,
                enabled=self.enabled,
                kill_switched=self.kill_switched,
                details={"reason": str(exc)},
                errors=[str(exc)],
            )
        except Exception as exc:
            return HealthReport(
                integration_id=self.integration_id,
                status=IntegrationStatus.DEGRADED,
                connected=self.connected,
                enabled=self.enabled,
                kill_switched=self.kill_switched,
                details={"account_email": self.account_email},
                errors=[f"{type(exc).__name__}: {exc}"],
            )

    # ── Power catalogue ──────────────────────────────────────────────────────

    def list_powers(self) -> List[Dict[str, Any]]:
        read = {
            "required_permissions": ["gmail.readonly"],
            "danger_level": "low",
            "tier": 0,
            "approval_required": False,
        }
        draft = {
            "required_permissions": ["gmail.compose"],
            "danger_level": "medium",
            "tier": 1,
            "approval_required": False,
        }
        send = {
            "required_permissions": ["gmail.send"],
            "danger_level": "high",
            "tier": 2,
            "approval_required": True,
        }
        return [
            {
                "power_id": "gmail.profile",
                "name": "Gmail Profile",
                "description": "Return the connected Gmail account identity and message totals.",
                "triggers": ["gmail profile", "which gmail account"],
                **read,
            },
            {
                "power_id": "gmail.list_messages",
                "name": "List Gmail Messages",
                "description": "List recent inbox messages with sender, subject, date and snippet.",
                "triggers": ["check my email", "list inbox", "recent emails"],
                **read,
            },
            {
                "power_id": "gmail.search_messages",
                "name": "Search Gmail",
                "description": "Search Gmail with the official query syntax (sender, subject, date, labels).",
                "triggers": ["search email", "find email"],
                **read,
            },
            {
                "power_id": "gmail.get_message",
                "name": "Read Gmail Message",
                "description": "Retrieve a message body and attachment metadata. Body is untrusted external data.",
                "triggers": ["read email", "open message"],
                **read,
            },
            {
                "power_id": "gmail.list_drafts",
                "name": "List Gmail Drafts",
                "description": "List saved drafts with recipient, subject, body preview and content hash.",
                "triggers": ["list drafts", "show drafts"],
                **read,
            },
            {
                "power_id": "gmail.get_draft",
                "name": "Preview Gmail Draft",
                "description": "Fetch a draft's exact content hash and preview before approval.",
                "triggers": ["preview draft"],
                **read,
            },
            {
                "power_id": "gmail.create_draft",
                "name": "Create Gmail Draft",
                "description": "Save a draft in the real Gmail account and return its content hash.",
                "triggers": ["draft an email", "prepare email"],
                **draft,
            },
            {
                "power_id": "gmail.update_draft",
                "name": "Update Gmail Draft",
                "description": "Replace a draft's content; the previous content hash and approval are invalidated.",
                "triggers": ["edit draft", "update draft"],
                **draft,
            },
            {
                "power_id": "gmail.send_draft",
                "name": "Send Gmail Draft",
                "description": "Send a saved draft after approval bound to its exact content hash.",
                "triggers": ["send draft", "send email"],
                **send,
            },
            {
                "power_id": "gmail.send_message",
                "name": "Send Gmail Message",
                "description": "Compose and send a message after approval bound to its exact content hash.",
                "triggers": ["send email", "email this"],
                **send,
            },
        ]

    # ── Execution ────────────────────────────────────────────────────────────

    def _execute_power_impl(self, power_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if power_id == "gmail.profile":
            return self.api.get_profile()

        if power_id in {"gmail.list_messages", "gmail.search_messages"}:
            return self.api.list_messages(
                query=str(params.get("query", "") or ""),
                max_results=int(params.get("max_results", 10) or 10),
                label_ids=params.get("label_ids"),
                include_metadata=bool(params.get("include_metadata", True)),
            )

        if power_id == "gmail.get_message":
            message_id = str(params.get("message_id") or params.get("id") or "").strip()
            if not message_id:
                raise GmailApiError("message_id is required", status_code=400)
            return self.api.get_message(message_id, fmt=str(params.get("format", "full")))

        if power_id == "gmail.list_drafts":
            return self.api.list_drafts(max_results=int(params.get("max_results", 10) or 10))

        if power_id == "gmail.get_draft":
            draft_id = str(params.get("draft_id") or "").strip()
            if not draft_id:
                raise GmailApiError("draft_id is required", status_code=400)
            return self.api.get_draft(draft_id)

        if power_id in {"gmail.create_draft", "gmail.update_draft"}:
            to = str(params.get("to") or "").strip()
            subject = str(params.get("subject") or "").strip()
            body = str(params.get("body") or "")
            if not to or not subject:
                raise GmailApiError("to and subject are required", status_code=400)
            attachments = self._validate_attachments(params.get("attachments"))
            kwargs = {
                "to": to,
                "subject": subject,
                "body": body,
                "cc": params.get("cc"),
                "bcc": params.get("bcc"),
                "from_addr": settings.assistant_email,
                "attachments": attachments,
            }
            if power_id == "gmail.create_draft":
                return self.api.create_draft(**kwargs)
            draft_id = str(params.get("draft_id") or "").strip()
            if not draft_id:
                raise GmailApiError("draft_id is required", status_code=400)
            return self.api.update_draft(draft_id, **kwargs)

        if power_id == "gmail.send_draft":
            draft_id = str(params.get("draft_id") or "").strip()
            expected_hash = str(params.get("expected_content_hash") or params.get("content_hash") or "").strip()
            if not draft_id or not expected_hash:
                raise GmailApiError("draft_id and expected_content_hash are required", status_code=400)
            return self.api.send_draft(draft_id, expected_hash)

        if power_id == "gmail.send_message":
            to = str(params.get("to") or "").strip()
            subject = str(params.get("subject") or "").strip()
            body = str(params.get("body") or "")
            expected_hash = str(params.get("expected_content_hash") or params.get("content_hash") or "").strip()
            if not to or not subject or not expected_hash:
                raise GmailApiError(
                    "to, subject and expected_content_hash are required", status_code=400
                )
            return self.api.send_message(
                to=to,
                subject=subject,
                body=body,
                expected_content_hash=expected_hash,
                cc=params.get("cc"),
                bcc=params.get("bcc"),
                from_addr=settings.assistant_email,
                attachments=self._validate_attachments(params.get("attachments")),
            )

        raise GmailApiError(f"Unknown Gmail power: {power_id}", status_code=404)

    def _validate_attachments(self, attachments: Any) -> Optional[List[Dict[str, Any]]]:
        if not attachments:
            return None
        if not isinstance(attachments, list):
            raise GmailApiError("attachments must be a list of {path} objects", status_code=400)
        from pathlib import Path

        allowed_roots = [Path(p).resolve() for p in settings.allowed_directories]
        validated: List[Dict[str, Any]] = []
        for item in attachments:
            if not isinstance(item, dict) or not item.get("path"):
                raise GmailApiError("Each attachment requires a path", status_code=400)
            resolved = Path(str(item["path"])).expanduser().resolve()
            if not any(resolved == root or root in resolved.parents for root in allowed_roots):
                raise GmailApiError(
                    f"Attachment path is outside the allowed directories: {resolved.name}",
                    status_code=403,
                )
            validated.append(
                {
                    "path": str(resolved),
                    "filename": item.get("filename") or resolved.name,
                    "mime_type": item.get("mime_type") or "application/octet-stream",
                }
            )
        return validated

    def _approval_preview(self, power_id: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if power_id not in {"gmail.send_draft", "gmail.send_message"}:
            return None
        preview = {
            "action": "SEND_EMAIL",
            "sending_account": settings.assistant_email,
            "to": params.get("to", ""),
            "cc": params.get("cc", ""),
            "bcc": params.get("bcc", ""),
            "subject": params.get("subject", ""),
            "body": params.get("body", ""),
            "attachments": params.get("attachments", []),
            "content_hash": params.get("expected_content_hash") or params.get("content_hash"),
            "draft_id": params.get("draft_id"),
            "note": "For send_draft, call gmail.get_draft first to display the exact saved content.",
        }
        return preview


gmail_integration = GmailIntegration()
