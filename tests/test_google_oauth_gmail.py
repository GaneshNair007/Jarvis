"""Google OAuth 2.0 + Gmail integration tests.

All provider traffic is replaced by deterministic fakes.  These tests prove:

- PKCE S256 binding, state expiry, one-time state consumption
- token persistence, refresh, revocation and redacted status
- DPAPI encryption at rest (Windows)
- Gmail inbox/search/read/draft/update parsing
- approval-bound send: no token, content-hash mismatch, provider message id
- the integration refuses to keep a token for the wrong Google account
"""

import base64
import copy
import hashlib
import json
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

import jarvis.api.server as server_module
from jarvis.api.server import app

from integrations.base.credential_manager import DpapiFileStore
from integrations.base.oauth_manager import (
    InMemoryTokenStore,
    OAuthManager,
    OAuthStateError,
)
from integrations.google.gmail_api import (
    GmailApiError,
    GmailDeliveryUnconfirmed,
    GoogleApiClient,
    base64url_decode,
    base64url_encode,
    build_mime_message,
    content_hash,
)
from integrations.google.gmail_integration import GmailIntegration
from jarvis.core.policy_gate import policy_gate

import jarvis.api.routes_google as routes_google
from jarvis.core.policy_gate import policy_gate


# ── Fakes ────────────────────────────────────────────────────────────────────


class FakeOAuthTransport:
    def __init__(self, responses=None):
        self.calls = []
        self.responses = responses or {}

    def post_form(self, url, form):
        self.calls.append({"url": url, "form": dict(form)})
        value = self.responses.get(url.split("?")[0], {})
        if callable(value):
            value = value(form)
        return copy.deepcopy(value)


class FakeGmailTransport:
    def __init__(self):
        self.calls = []
        self.routes = {}

    def route(self, method, path, payload):
        self.routes[(method.upper(), path)] = payload
        return self

    def _request(self, method, url, data=None, headers=None):
        parsed = urlparse(url)
        body = json.loads(data.decode("utf-8")) if data else None
        self.calls.append(
            {
                "method": method.upper(),
                "path": parsed.path,
                "query": parse_qs(parsed.query),
                "json": body,
                "headers": headers or {},
            }
        )
        key = (method.upper(), parsed.path)
        if key not in self.routes:
            raise AssertionError(f"Unexpected Gmail request {key}; calls={self.calls}")
        value = self.routes[key]
        if callable(value):
            return value(body)
        return copy.deepcopy(value)

    def calls_to(self, method, path):
        return [c for c in self.calls if c["method"] == method and c["path"] == path]


class FakeGmailApi:
    def __init__(self, oauth, profile_email="jarvis33246146@gmail.com"):
        self.oauth = oauth
        self.profile_email = profile_email
        self.sent = []

    def get_profile(self):
        return {
            "emailAddress": self.profile_email,
            "messagesTotal": 12,
            "threadsTotal": 8,
        }

    def send_message(self, **kwargs):
        self.sent.append(kwargs)
        return {
            "status": "SENT",
            "provider": "gmail",
            "message_id": "provider-msg-1",
            "thread_id": "provider-thread-1",
            "content_hash": kwargs["expected_content_hash"],
        }


def _oauth(transport=None, store=None, clock=None):
    return OAuthManager(
        token_store=store or InMemoryTokenStore(),
        transport=transport or FakeOAuthTransport(),
        clock=clock,
    )


def _authorization(mgr, redirect_uri="http://127.0.0.1:8765"):
    return mgr.generate_authorization_url(
        "google",
        "client-id.apps.googleusercontent.com",
        redirect_uri,
        ["https://www.googleapis.com/auth/gmail.readonly"],
        use_pkce=True,
    )


def _raw_message(to="owner@example.com", subject="Hello", body="Body text"):
    raw, _meta = build_mime_message(to=to, subject=subject, body=body)
    return raw


def _draft_payload(draft_id="d1", raw=None, message_id="m1"):
    raw = raw or _raw_message()
    return {
        "id": draft_id,
        "message": {
            "id": message_id,
            "threadId": "thread-1",
            "raw": base64url_encode(raw),
        },
    }


def _full_message(message_id="m1", subject="Hello", body="Body text"):
    return {
        "id": message_id,
        "threadId": "thread-1",
        "labelIds": ["INBOX", "UNREAD"],
        "snippet": "snippet text",
        "payload": {
            "mimeType": "text/plain",
            "headers": [
                {"name": "From", "value": "sender@example.com"},
                {"name": "To", "value": "jarvis33246146@gmail.com"},
                {"name": "Subject", "value": subject},
                {"name": "Date", "value": "Mon, 09 Nov 2026 10:00:00 +0000"},
            ],
            "body": {"data": base64url_encode(body.encode("utf-8"))},
        },
    }


def _gmail_client(monkeypatch, transport):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "client-id.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "client-secret")
    oauth = _oauth()
    oauth.register_token("google", "access-token", refresh_token="refresh-token", expires_in_sec=3600)
    return GoogleApiClient(oauth=oauth, transport=transport), oauth


# ── OAuth lifecycle ──────────────────────────────────────────────────────────


def test_authorization_url_contains_state_and_pkce_s256():
    mgr = _oauth()
    auth = _authorization(mgr)
    params = parse_qs(urlparse(auth["authorization_url"]).query)

    assert params["client_id"] == ["client-id.apps.googleusercontent.com"]
    assert params["response_type"] == ["code"]
    assert params["code_challenge_method"] == ["S256"]
    assert params["state"] == [auth["state"]]
    assert params["access_type"] == ["offline"]
    assert len(params["code_challenge"][0]) >= 43
    assert auth["pkce"] is True


def test_state_is_one_time_and_expires():
    now = [1_000_000.0]
    mgr = _oauth(clock=lambda: now[0])
    auth = _authorization(mgr)

    assert mgr.verify_state(auth["state"]) is not None
    consumed = mgr.consume_state(auth["state"])
    assert consumed is not None
    assert mgr.consume_state(auth["state"]) is None

    second = _authorization(mgr)
    now[0] += OAuthManager.STATE_TTL_SEC + 1
    assert mgr.verify_state(second["state"]) is None
    assert mgr.consume_state(second["state"]) is None


def test_exchange_code_sends_pkce_verifier_and_persists_redacted_token():
    store = InMemoryTokenStore()
    transport = FakeOAuthTransport(
        {
            "https://oauth2.googleapis.com/token": {
                "access_token": "secret-access",
                "refresh_token": "secret-refresh",
                "expires_in": 3600,
                "scope": "https://www.googleapis.com/auth/gmail.readonly",
                "token_type": "Bearer",
            }
        }
    )
    mgr = _oauth(transport=transport, store=store)
    auth = _authorization(mgr)
    challenge = parse_qs(urlparse(auth["authorization_url"]).query)["code_challenge"][0]

    summary = mgr.exchange_code(
        "google",
        code="auth-code",
        state=auth["state"],
        client_id="client-id.apps.googleusercontent.com",
        client_secret="client-secret",
    )

    form = transport.calls[0]["form"]
    assert form["grant_type"] == "authorization_code"
    assert form["code"] == "auth-code"
    verifier = form["code_verifier"]
    recomputed = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
    )
    assert recomputed == challenge

    stored = store.load("google")
    assert stored["access_token"] == "secret-access"
    assert stored["refresh_token"] == "secret-refresh"
    assert summary["status"] == "CONNECTED"
    assert summary["has_refresh_token"] is True
    serialized = json.dumps(summary)
    assert "secret-access" not in serialized
    assert "secret-refresh" not in serialized


def test_exchange_code_rejects_replayed_state():
    transport = FakeOAuthTransport({"https://oauth2.googleapis.com/token": {"access_token": "a", "refresh_token": "r"}})
    mgr = _oauth(transport=transport)
    auth = _authorization(mgr)
    mgr.exchange_code("google", "code", auth["state"], "cid", "secret")

    with pytest.raises(OAuthStateError):
        mgr.exchange_code("google", "code", auth["state"], "cid", "secret")


def test_expired_access_token_refreshes_and_preserves_refresh_token():
    now = [2_000_000.0]
    store = InMemoryTokenStore()
    transport = FakeOAuthTransport(
        {
            "https://oauth2.googleapis.com/token": {
                "access_token": "new-access",
                "expires_in": 3600,
                "scope": "https://www.googleapis.com/auth/gmail.readonly",
            }
        }
    )
    mgr = _oauth(transport=transport, store=store, clock=lambda: now[0])
    mgr.register_token(
        "google",
        "old-access",
        refresh_token="keep-me",
        expires_in_sec=60,
    )

    now[0] += 120
    token = mgr.get_valid_access_token("google", "cid", "secret")

    assert token == "new-access"
    refresh_form = transport.calls[0]["form"]
    assert refresh_form["grant_type"] == "refresh_token"
    assert refresh_form["refresh_token"] == "keep-me"
    assert store.load("google")["refresh_token"] == "keep-me"
    assert store.load("google")["access_token"] == "new-access"


def test_revoke_calls_provider_and_deletes_local_token():
    transport = FakeOAuthTransport({"https://oauth2.googleapis.com/revoke": {}})
    store = InMemoryTokenStore()
    mgr = _oauth(transport=transport, store=store)
    mgr.register_token("google", "access", refresh_token="refresh", expires_in_sec=3600)
    store.save(
        "google",
        {
            "access_token": "access",
            "refresh_token": "refresh",
            "expires_at": time.time() + 3600,
            "scopes": [],
            "token_type": "Bearer",
        },
    )

    assert mgr.revoke_token("google") is True

    assert transport.calls[0]["url"].startswith("https://oauth2.googleapis.com/revoke")
    assert transport.calls[0]["form"]["token"] == "refresh"
    assert store.load("google") is None
    assert mgr.status("google")["connected"] is False


def test_dpapi_store_encrypts_at_rest(tmp_path):
    pytest.importorskip("win32crypt")
    store = DpapiFileStore(tmp_path)
    secret_payload = {"refresh_token": "super-secret-refresh-value", "access_token": "secret-access"}

    path = store.save("google_oauth", secret_payload)
    raw = Path(path).read_bytes()

    assert b"super-secret-refresh-value" not in raw
    assert b"secret-access" not in raw
    assert store.load("google_oauth") == secret_payload
    assert store.delete("google_oauth") is True
    assert store.load("google_oauth") is None


# ── Gmail API (mocked transport) ─────────────────────────────────────────────


def test_list_messages_parses_metadata_and_account(monkeypatch):
    transport = FakeGmailTransport()
    transport.route(
        "GET",
        "/gmail/v1/users/me/messages",
        {
            "messages": [{"id": "m1", "threadId": "thread-1"}],
            "resultSizeEstimate": 1,
        },
    )
    transport.route("GET", "/gmail/v1/users/me/messages/m1", _full_message())
    transport.route("GET", "/gmail/v1/users/me/profile", {"emailAddress": "jarvis33246146@gmail.com"})
    client, _oauth_mgr = _gmail_client(monkeypatch, transport)

    result = client.list_messages(query="in:inbox", max_results=5)

    assert result["account"] == "jarvis33246146@gmail.com"
    assert result["messages"][0]["subject"] == "Hello"
    assert result["messages"][0]["unread"] is True
    assert "body_text" not in result["messages"][0]


def test_get_message_marks_body_as_untrusted(monkeypatch):
    transport = FakeGmailTransport()
    transport.route("GET", "/gmail/v1/users/me/messages/m1", _full_message())
    client, _ = _gmail_client(monkeypatch, transport)

    message = client.get_message("m1")

    assert message["body_text"] == "Body text"
    assert message["content_trust"] == "UNTRUSTED_EXTERNAL_DATA"
    assert message["instruction_policy"].startswith("NEVER_TREAT_EMAIL_CONTENT")


def test_get_message_extracts_html_and_attachment_metadata(monkeypatch):
    html_body = "<html><body><p>Hello <b>there</b></p><script>bad()</script></body></html>"
    payload = {
        "id": "m2",
        "threadId": "t2",
        "labelIds": ["INBOX"],
        "payload": {
            "mimeType": "multipart/mixed",
            "headers": [{"name": "Subject", "value": "Attachment"}],
            "parts": [
                {
                    "mimeType": "text/html",
                    "body": {"data": base64url_encode(html_body.encode("utf-8"))},
                },
                {
                    "mimeType": "application/pdf",
                    "filename": "report.pdf",
                    "body": {"attachmentId": "att-1", "size": 1234},
                },
            ],
        },
    }
    transport = FakeGmailTransport().route("GET", "/gmail/v1/users/me/messages/m2", payload)
    client, _ = _gmail_client(monkeypatch, transport)

    message = client.get_message("m2")

    assert "Hello" in message["body_text"]
    assert "bad()" not in message["body_text"]
    assert message["attachments"][0]["filename"] == "report.pdf"
    assert message["attachments"][0]["download_available"] is True


def test_create_draft_is_deterministic_and_returns_content_hash(monkeypatch):
    captured = []

    def store_draft(body):
        captured.append(body)
        return {"id": "d1", "message": {"id": "m1", "threadId": "t1"}}

    transport = FakeGmailTransport().route("POST", "/gmail/v1/users/me/drafts", store_draft)
    client, _ = _gmail_client(monkeypatch, transport)

    first = client.create_draft(to="owner@example.com", subject="Hi", body="Body")
    second = client.create_draft(to="owner@example.com", subject="Hi", body="Body")

    assert first["content_hash"] == second["content_hash"]
    raw_one = base64url_decode(captured[0]["message"]["raw"])
    raw_two = base64url_decode(captured[1]["message"]["raw"])
    assert raw_one == raw_two
    assert first["content_hash"] == content_hash(raw_one)
    assert b"Subject: Hi" in raw_one


def test_update_draft_changes_content_hash(monkeypatch):
    transport = FakeGmailTransport().route(
        "PUT", "/gmail/v1/users/me/drafts/d1", {"id": "d1", "message": {"id": "m2", "threadId": "t1"}}
    )
    client, _ = _gmail_client(monkeypatch, transport)

    updated = client.update_draft("d1", to="owner@example.com", subject="New subject", body="New body")

    assert updated["draft_id"] == "d1"
    assert updated["subject"] == "New subject"
    assert len(updated["content_hash"]) == 64


def test_send_draft_refuses_content_hash_mismatch(monkeypatch):
    raw = _raw_message()
    transport = FakeGmailTransport()
    transport.route("GET", "/gmail/v1/users/me/drafts/d1", _draft_payload(raw=raw))
    transport.route("POST", "/gmail/v1/users/me/drafts/send", {"id": "sent-1"})
    client, _ = _gmail_client(monkeypatch, transport)

    with pytest.raises(GmailApiError) as excinfo:
        client.send_draft("d1", "0" * 64)

    assert excinfo.value.description == "content_hash_mismatch"
    assert transport.calls_to("POST", "/gmail/v1/users/me/drafts/send") == []


def test_send_draft_requires_provider_message_id(monkeypatch):
    raw = _raw_message()
    transport = FakeGmailTransport()
    transport.route("GET", "/gmail/v1/users/me/drafts/d1", _draft_payload(raw=raw))
    transport.route("POST", "/gmail/v1/users/me/drafts/send", {})
    client, _ = _gmail_client(monkeypatch, transport)

    with pytest.raises(GmailDeliveryUnconfirmed):
        client.send_draft("d1", content_hash(raw))


def test_send_draft_returns_real_provider_id(monkeypatch):
    raw = _raw_message()
    transport = FakeGmailTransport()
    transport.route("GET", "/gmail/v1/users/me/drafts/d1", _draft_payload(raw=raw))
    transport.route(
        "POST",
        "/gmail/v1/users/me/drafts/send",
        {"id": "sent-99", "threadId": "thread-99", "labelIds": ["SENT"]},
    )
    client, _ = _gmail_client(monkeypatch, transport)

    result = client.send_draft("d1", content_hash(raw))

    assert result["status"] == "SENT"
    assert result["message_id"] == "sent-99"
    assert result["content_hash"] == content_hash(raw)


def test_send_message_refuses_changed_content(monkeypatch):
    transport = FakeGmailTransport().route("POST", "/gmail/v1/users/me/messages/send", {"id": "sent-1"})
    client, _ = _gmail_client(monkeypatch, transport)

    with pytest.raises(GmailApiError):
        client.send_message(
            to="owner@example.com",
            subject="Hi",
            body="Body",
            expected_content_hash="f" * 64,
        )
    assert transport.calls_to("POST", "/gmail/v1/users/me/messages/send") == []


def test_send_raw_message_submits_exact_approved_bytes(monkeypatch):
    transport = FakeGmailTransport().route(
        "POST", "/gmail/v1/users/me/messages/send", {"id": "sent-raw", "threadId": "t1"}
    )
    client, _ = _gmail_client(monkeypatch, transport)
    raw = _raw_message(subject="Exact bytes")

    result = client.send_raw_message(raw, content_hash(raw))

    assert result["message_id"] == "sent-raw"
    posted = transport.calls_to("POST", "/gmail/v1/users/me/messages/send")[0]["json"]
    assert base64url_decode(posted["raw"]) == raw


def test_send_raw_message_without_id_is_unconfirmed(monkeypatch):
    transport = FakeGmailTransport().route("POST", "/gmail/v1/users/me/messages/send", {})
    client, _ = _gmail_client(monkeypatch, transport)
    raw = _raw_message()

    with pytest.raises(GmailDeliveryUnconfirmed):
        client.send_raw_message(raw, content_hash(raw))


# ── Integration approval gate ────────────────────────────────────────────────


def _gmail_integration(monkeypatch, profile_email="jarvis33246146@gmail.com"):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "client-id.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "client-secret")
    oauth = _oauth()
    oauth.register_token("google", "access-token", refresh_token="refresh-token", expires_in_sec=3600)
    fake_api = FakeGmailApi(oauth, profile_email=profile_email)
    integration = GmailIntegration(api=fake_api)
    integration.enable()
    return integration, fake_api, oauth


def _send_params(body="Approved body"):
    return {
        "to": "owner@example.com",
        "subject": "Approved subject",
        "body": body,
        "expected_content_hash": "a" * 64,
    }


def test_send_power_requires_approval_and_shows_preview(monkeypatch):
    integration, fake_api, _oauth_mgr = _gmail_integration(monkeypatch)

    result = integration.execute_power("gmail.send_message", _send_params())

    assert result["status"] == "AWAITING_APPROVAL"
    assert result["approval_required"] is True
    assert result["approval_preview"]["action"] == "SEND_EMAIL"
    assert result["approval_preview"]["sending_account"] == "jarvis33246146@gmail.com"
    assert result["approval_preview"]["to"] == "owner@example.com"
    assert "token" not in json.dumps(result["approval_preview"]).lower()
    assert fake_api.sent == []


def test_approval_token_is_bound_to_exact_content(monkeypatch):
    integration, fake_api, _oauth_mgr = _gmail_integration(monkeypatch)
    params = _send_params(body="Original body")

    pending = integration.execute_power("gmail.send_message", params)
    token = policy_gate.pending_approvals[pending["task_id"]]["token"]

    changed = dict(params, body="Changed after approval")
    rejected = integration.execute_power("gmail.send_message", changed, approval_token=token)

    assert rejected["status"] == "APPROVAL_INVALID"
    assert fake_api.sent == []

    accepted = integration.execute_power("gmail.send_message", params, approval_token=token)
    assert accepted["status"] == "SUCCESS"
    assert accepted["result"]["status"] == "SENT"
    assert accepted["result"]["message_id"] == "provider-msg-1"
    assert len(fake_api.sent) == 1


def test_health_check_requires_the_assistant_account(monkeypatch):
    integration, _fake_api, oauth = _gmail_integration(monkeypatch)

    healthy = integration.health_check()
    assert healthy.status.value == "HEALTHY"
    assert healthy.details["account_email"] == "jarvis33246146@gmail.com"

    wrong, _fake_api, wrong_oauth = _gmail_integration(monkeypatch, profile_email="someone-else@gmail.com")
    degraded = wrong.health_check()
    assert degraded.status.value == "DEGRADED"
    assert degraded.connected is False
    assert wrong_oauth.status("google")["connected"] is True  # token untouched by health probe


def test_connect_revokes_token_for_wrong_google_account(monkeypatch):
    integration, _fake_api, oauth = _gmail_integration(monkeypatch, profile_email="someone-else@gmail.com")

    assert integration.connect() is False
    assert "does not match" in integration.last_error
    assert oauth.status("google")["connected"] is False


def test_health_check_reports_unconfigured_without_client_credentials(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
    integration = GmailIntegration(api=FakeGmailApi(_oauth()))

    report = integration.health_check()

    assert report.status.value == "UNCONFIGURED"
    assert report.connected is False
    assert "GOOGLE_CLIENT_ID" in report.details["missing_credentials"]


# ── Route-level tests (TestClient, faked flow) ───────────────────────────────


class FakeRouteFlow:
    def __init__(self, status_payload=None):
        self.status_payload = status_payload or {
            "status": "UNCONFIGURED",
            "connected": False,
            "missing_credentials": ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"],
            "assistant_email": "jarvis33246146@gmail.com",
        }
        self.calls = []

    def status(self):
        return dict(self.status_payload)

    def build_authorization(self, redirect_uri, scopes=None):
        self.calls.append(("build_authorization", redirect_uri))
        return {
            "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?state=abc",
            "state": "abc",
            "expires_in_sec": 600,
            "scopes": scopes or [],
        }

    def complete(self, code, state, redirect_uri):
        self.calls.append(("complete", code, state, redirect_uri))
        return {
            "status": "CONNECTED",
            "account_email": "jarvis33246146@gmail.com",
            "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
        }

    def disconnect(self):
        self.calls.append(("disconnect",))
        return {"status": "DISCONNECTED", "local_token_deleted": True}


@pytest.fixture
def google_routes_client(monkeypatch):
    fake = FakeRouteFlow()
    monkeypatch.setattr(routes_google, "google_flow", fake)
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")
    with TestClient(app) as client:
        yield client, fake


def test_google_status_route_unconfigured(google_routes_client):
    client, _fake = google_routes_client
    resp = client.get("/api/v1/google/status")
    assert resp.status_code == 200
    assert resp.json()["status"] == "UNCONFIGURED"
    assert resp.json()["connected"] is False


def test_google_auth_start_returns_url(google_routes_client):
    client, fake = google_routes_client
    resp = client.post("/api/v1/google/auth/start")
    assert resp.status_code == 200
    body = resp.json()
    assert "accounts.google.com" in body["authorization_url"]
    assert body["state"] == "abc"
    assert fake.calls[-1][0] == "build_authorization"
    assert "/api/v1/google/auth/callback" in fake.calls[-1][1]


def test_google_callback_connects(google_routes_client):
    client, fake = google_routes_client
    resp = client.get("/api/v1/google/auth/callback", params={"code": "code-1", "state": "abc"})
    assert resp.status_code == 200
    assert "jarvis33246146@gmail.com" in resp.text
    assert fake.calls[-1][0] == "complete"
    assert fake.calls[-1][1] == "code-1"
    assert fake.calls[-1][2] == "abc"


def test_google_disconnect_route(google_routes_client):
    client, fake = google_routes_client
    resp = client.post("/api/v1/google/auth/disconnect")
    assert resp.status_code == 200
    assert resp.json()["status"] == "DISCONNECTED"
    assert ("disconnect",) in fake.calls
