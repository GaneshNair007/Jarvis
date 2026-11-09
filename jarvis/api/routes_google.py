"""Google OAuth + Gmail Communication Center API routes.

Endpoints:
  GET    /api/v1/google/status                    Redacted OAuth connection status
  POST   /api/v1/google/auth/start                Returns the Google authorization URL
  GET    /api/v1/google/auth/callback             Loopback callback; exchanges code, verifies account
  POST   /api/v1/google/auth/disconnect           Revoke token + delete local credentials
  GET    /api/v1/google/gmail/profile             Connected account identity
  GET    /api/v1/google/gmail/inbox               Message list (labelIds=INBOX)
  GET    /api/v1/google/gmail/unread              Message list (labelIds=UNREAD)
  GET    /api/v1/google/gmail/important           Message list (labelIds=IMPORTANT)
  GET    /api/v1/google/gmail/sent                Message list (labelIds=SENT)
  GET    /api/v1/google/gmail/drafts              Draft list with previews + content hashes
  GET    /api/v1/google/gmail/message/{message_id} Full parsed message (untrusted body)
  GET    /api/v1/google/gmail/draft/{draft_id}    Draft preview with exact content hash
  POST   /api/v1/google/gmail/drafts              Create a real Gmail draft
  POST   /api/v1/google/gmail/send                Approval-gated send (bound to content hash)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from integrations.base.oauth_manager import OAuthError
from integrations.google.gmail_api import GmailApiError
from integrations.google.gmail_integration import gmail_integration, GMAIL_SCOPES
from integrations.google.oauth_flow import GoogleOAuthFlow
from jarvis.core.logger import get_logger
from jarvis.core.policy_gate import policy_gate

logger = get_logger("api.google")

router = APIRouter(tags=["Google"])

# Single flow instance bound to the global DPAPI-backed OAuth manager and the
# Gmail integration's REST client.
google_flow = GoogleOAuthFlow()

GOOGLE_CALLBACK_URI = "http://127.0.0.1:8000/api/v1/google/auth/callback"


# ── OAuth ────────────────────────────────────────────────────────────────────

class AuthStartRequest(BaseModel):
    redirect_uri: Optional[str] = Field(
        default=None,
        description="Override loopback callback URI (defaults to the API server itself)",
    )


@router.get("/api/v1/google/status")
async def google_status() -> Dict[str, Any]:
    """Redacted Google connection status. Never returns token values."""
    return google_flow.status()


@router.post("/api/v1/google/auth/start")
async def google_auth_start(req: Optional[AuthStartRequest] = None) -> Dict[str, Any]:
    """Generate the state+PKCE authorization URL for the dedicated JARVIS account."""
    redirect_uri = (
        req.redirect_uri
        if req and req.redirect_uri
        else GOOGLE_CALLBACK_URI
    )
    auth = google_flow.build_authorization(redirect_uri)
    return {
        "authorization_url": auth["authorization_url"],
        "state": auth["state"],
        "redirect_uri": redirect_uri,
        "expires_in_sec": auth["expires_in_sec"],
        "scopes": list(GMAIL_SCOPES),
        "assistant_account": "jarvis33246146@gmail.com",
    }


_CONNECTED_PAGE = """<!doctype html><html><head><meta charset='utf-8'><title>JARVIS — Google connected</title>
<style>body{font-family:Segoe UI,sans-serif;background:#0b1020;color:#e8f1ff;padding:2rem;display:flex;flex-direction:column;align-items:center;gap:1rem}
h1{color:#00d4ff} p{color:#b9c4d6} .ok{color:#00ff88} .badge{display:inline-block;padding:2px 8px;border-radius:4px;background:#002b36;border:1px solid #00d4ff;margin-top:8px}
button{margin-top:14px;padding:8px 16px;background:#00d4ff;color:#000;border:none;border-radius:6px;cursor:pointer;font-weight:600}
button:hover{background:#00a8cc}</style></head><body>
<h1>JARVIS · Google connected</h1>
<p class="ok">Authorized as <strong>{email}</strong>. Scopes: {scopes}.</p>
<p>You can close this window and return to the JARVIS dashboard. The OAuth token is stored encrypted with Windows DPAPI; no password was ever used.</p>
<div class="badge">gmail.readonly · gmail.compose · gmail.send</div>
<button onclick="window.close()">Close window</button>
<script>try{window.opener&&window.opener.postMessage({type:'jarvis_google_connected',account:'{email}'},'*');}catch{}</script>
</body></html>"""

_FAILED_PAGE = """<!doctype html><html><head><meta charset='utf-8'><title>JARVIS — Google connection failed</title>
<style>body{font-family:Segoe UI,sans-serif;background:#0b1020;color:#e8f1ff;padding:2rem;display:flex;flex-direction:column;align-items:center;gap:1rem}
h1{color:#ff6b6b} p{color:#b9c4d6} .err{color:#ff6b6b;white-space:pre-wrap;word-break:break-word;margin:1rem 0;background:#1a0a0a;border:1px solid #ff6b6b;padding:1rem;border-radius:8px}
button{margin-top:14px;padding:8px 16px;background:#00d4ff;color:#000;border:none;border-radius:6px;cursor:pointer;font-weight:600}
button:hover{background:#00a8cc}</style></head><body>
<h1>JARVIS · Google connection failed</h1>
<div class="err">{reason}</div>
<p>No token was stored. Correct the issue and start the connection again from the dashboard.</p>
<button onclick="window.close()">Close window</button>
</body></html>"""


@router.get("/api/v1/google/auth/callback", response_class=HTMLResponse)
async def google_auth_callback(
    code: Optional[str] = Query(default=None),
    state: Optional[str] = Query(default=None),
):
    """Google redirects the owner's browser here after consent.

    Exchanges the authorization code, verifies that the signed-in account is the
    dedicated JARVIS identity, persists the token with DPAPI, and renders a
    success/failure page.
    """
    try:
        result = google_flow.complete(code or "", state or "", GOOGLE_CALLBACK_URI)
        email = result.get("account_email", "jarvis33246146@gmail.com")
        scopes = " ".join(result.get("scopes", []))
        return HTMLResponse(
            _CONNECTED_PAGE.replace("{email}", email).replace("{scopes}", scopes),
            headers={"Cache-Control": "no-store"},
        )
    except OAuthError as exc:
        logger.warning("Google OAuth callback failed: %s", exc.error)
        return HTMLResponse(
            _FAILED_PAGE.replace("{reason}", exc.description or exc.error),
            status_code=400,
            headers={"Cache-Control": "no-store"},
        )


@router.post("/api/v1/google/auth/disconnect")
async def google_auth_disconnect() -> Dict[str, Any]:
    """Revoke the Google token at the provider and delete local DPAPI credentials."""
    return google_flow.disconnect()


# ── Gmail data (Communication Center) ────────────────────────────────────────

def _require_connected() -> None:
    if not gmail_integration.connected or not gmail_integration.oauth.is_connected("google"):
        raise HTTPException(
            status_code=409,
            detail="Gmail is not connected. Start the Google OAuth flow first.",
        )


@router.get("/api/v1/google/gmail/profile")
async def gmail_profile() -> Dict[str, Any]:
    _require_connected()
    return gmail_integration.api.get_profile()


def _label_param(label_ids: Optional[str]) -> Optional[List[str]]:
    if not label_ids:
        return None
    return [label.strip() for label in label_ids.split(",") if label.strip()]


@router.get("/api/v1/google/gmail/inbox")
async def gmail_inbox(
    query: str = Query(default=""),
    max_results: int = Query(default=10, ge=1, le=100),
    label_ids: Optional[str] = Query(default=None),
):
    _require_connected()
    return gmail_integration.api.list_messages(
        query=query, max_results=max_results, label_ids=_label_param(label_ids)
    )


@router.get("/api/v1/google/gmail/unread")
async def gmail_unread(max_results: int = Query(default=10, ge=1, le=100)):
    _require_connected()
    return gmail_integration.api.list_messages(
        query="is:unread", max_results=max_results, label_ids=["UNREAD"]
    )


@router.get("/api/v1/google/gmail/important")
async def gmail_important(max_results: int = Query(default=10, ge=1, le=100)):
    _require_connected()
    return gmail_integration.api.list_messages(
        query="is:important", max_results=max_results, label_ids=["IMPORTANT"]
    )


@router.get("/api/v1/google/gmail/sent")
async def gmail_sent(max_results: int = Query(default=10, ge=1, le=100)):
    _require_connected()
    return gmail_integration.api.list_messages(
        query="in:sent", max_results=max_results, label_ids=["SENT"]
    )


@router.get("/api/v1/google/gmail/drafts")
async def gmail_drafts(max_results: int = Query(default=10, ge=1, le=100)):
    _require_connected()
    return gmail_integration.api.list_drafts(max_results=max_results)


@router.get("/api/v1/google/gmail/message/{message_id}")
async def gmail_message(message_id: str):
    _require_connected()
    return gmail_integration.api.get_message(message_id)


@router.get("/api/v1/google/gmail/draft/{draft_id}")
async def gmail_draft(draft_id: str):
    _require_connected()
    return gmail_integration.api.get_draft(draft_id)


class DraftCreateRequest(BaseModel):
    to: str
    subject: str
    body: str
    cc: Optional[str] = None
    bcc: Optional[str] = None
    attachments: Optional[List[Dict[str, Any]]] = None


@router.post("/api/v1/google/gmail/drafts")
async def gmail_create_draft(req: DraftCreateRequest):
    _require_connected()
    return gmail_integration.api.create_draft(
        to=req.to,
        subject=req.subject,
        body=req.body,
        cc=req.cc,
        bcc=req.bcc,
        attachments=req.attachments,
    )


class SendMessageRequest(BaseModel):
    to: str = ""
    subject: str = ""
    body: str = ""
    draft_id: Optional[str] = Field(
        default=None, description="Send a previously created draft instead of composing"
    )
    expected_content_hash: Optional[str] = Field(
        default=None,
        description="SHA-256 of the exact RFC 822 bytes approved by the owner",
    )
    cc: Optional[str] = None
    bcc: Optional[str] = None
    attachments: Optional[List[Dict[str, Any]]] = None
    approval_token: Optional[str] = None


@router.post("/api/v1/google/gmail/send")
async def gmail_send(req: SendMessageRequest):
    """Approval-gated send.

    The first call issues an approval request bound to the exact content hash
    (returns AWAITING_APPROVAL). The owner resolves it at
    POST /api/v1/approvals/{task_id}/resolve and retries with the approval
    token; only then does Gmail confirm delivery with a real message id.
    """
    _require_connected()
    if req.draft_id:
        params: Dict[str, Any] = {
            "draft_id": req.draft_id,
            "expected_content_hash": req.expected_content_hash or "",
        }
        if req.approval_token:
            params["approval_token"] = req.approval_token
        return gmail_integration.execute_power("gmail.send_draft", params)
    params = {
        "to": req.to,
        "subject": req.subject,
        "body": req.body,
        "cc": req.cc,
        "bcc": req.bcc,
        "attachments": req.attachments,
    }
    if req.expected_content_hash:
        params["expected_content_hash"] = req.expected_content_hash
    if req.approval_token:
        params["approval_token"] = req.approval_token
    return gmail_integration.execute_power("gmail.send_message", params)


@router.get("/api/v1/approvals/pending")
async def list_pending_approvals() -> Dict[str, Any]:
    """Human-facing approval queue for the Communication Center."""
    items = []
    seen = set()
    for record in policy_gate.pending_approvals.values():
        task_id = record.get("task_id")
        if task_id in seen:
            continue
        seen.add(task_id)
        items.append(
            {
                "task_id": task_id,
                "approval_id": record.get("approval_id"),
                "power_id": record.get("power_id"),
                "action_summary": record.get("action_summary"),
                "expires_at": record.get("expires_at"),
                "status": record.get("status"),
            }
        )
    items.sort(key=lambda item: item.get("expires_at") or 0)
    return {"pending": items, "total": len(items)}
