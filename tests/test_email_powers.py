"""Tests for JARVIS Email Powers, approval binding and real delivery contract.

The old test suite asserted that moving a local ``.eml`` into ``sent/`` meant
"SENT".  That was a false-success path.  These tests require a provider
message id before success is reported.
"""

import hashlib
from email.message import EmailMessage
from pathlib import Path

import pytest

from jarvis.config import settings
from jarvis.core.policy_gate import policy_gate
from jarvis.powers.email_powers import EmailPowers
from integrations.google.gmail_api import GmailNotConnected


class FakeGmailClient:
    def __init__(self, message_id="gmail-msg-1", error=None, messages=None):
        self.message_id = message_id
        self.error = error
        self.messages = messages or []
        self.send_calls = []
        self.list_calls = []

    def send_raw_message(self, raw_bytes, expected_content_hash):
        self.send_calls.append((raw_bytes, expected_content_hash))
        if self.error:
            raise self.error
        return {
            "status": "SENT",
            "provider": "gmail",
            "message_id": self.message_id,
            "thread_id": "th-1",
            "content_hash": expected_content_hash,
        }

    def list_messages(self, **kwargs):
        self.list_calls.append(kwargs)
        if self.error:
            raise self.error
        return {
            "messages": [{"id": m["id"]} for m in self.messages],
            "result_size_estimate": len(self.messages),
        }

    def get_message(self, message_id):
        if self.error:
            raise self.error
        for message in self.messages:
            if message["id"] == message_id:
                return message
        raise AssertionError(f"unknown message {message_id}")


@pytest.fixture
def temp_email(tmp_path: Path):
    outbox = tmp_path / "outbox"
    return EmailPowers(outbox_dir=outbox), outbox


def _approval_token(email_p, draft, task_id="task_send_001"):
    path = Path(draft["file_path"])
    content_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    payload = {"draft_path": str(path), "sha256": content_hash}
    payload_hash = policy_gate.hash_payload(payload)
    token, _expiry = policy_gate.generate_approval_token(
        task_id=task_id,
        power_id="send_email",
        payload_hash=payload_hash,
    )
    return token, content_hash


def test_email_draft_creation(temp_email):
    email_p, outbox = temp_email
    res = email_p.draft_email(
        to="architect@local.internal",
        subject="Project Alpha Milestone Update",
        body="All cognitive core tests have passed with 100% compliance.",
    )

    assert res["status"] == "DRAFT_SAVED"
    assert Path(res["file_path"]).exists()
    assert res["to"] == "architect@local.internal"
    assert len(res["sha256"]) == 64

    outbox_list = email_p.list_outbox(outbox)
    assert outbox_list["count"] == 1


def test_email_send_without_approval_is_refused(temp_email):
    email_p, _ = temp_email
    fake = FakeGmailClient()
    email_p._gmail_client = fake
    draft = email_p.draft_email(
        to="external@partner.org",
        subject="Confidential Dispatch",
        body="Sensitive update payload.",
    )

    send_res = email_p.send_email(draft_path=draft["file_path"], task_id="task_unapproved")

    assert send_res["success"] is False
    assert send_res["status"] == "APPROVAL_REQUIRED"
    assert "pending_approval" in send_res
    assert fake.send_calls == []


def test_email_send_reports_sent_only_with_provider_message_id(temp_email):
    email_p, _ = temp_email
    fake = FakeGmailClient(message_id="gmail-msg-42")
    email_p._gmail_client = fake
    draft = email_p.draft_email(
        to="partner@local.internal",
        subject="Approved Communication",
        body="Action authorized by user.",
    )
    task_id = "task_approved_001"
    token, content_hash = _approval_token(email_p, draft, task_id=task_id)

    send_res = email_p.send_email(
        draft_path=draft["file_path"],
        task_id=task_id,
        approval_token=token,
    )

    assert send_res["success"] is True
    assert send_res["status"] == "SENT"
    assert send_res["provider"] == "gmail"
    assert send_res["message_id"] == "gmail-msg-42"
    assert send_res["provider_message_id"] == "gmail-msg-42"
    assert Path(send_res["archive_path"]).exists()
    assert not Path(draft["file_path"]).exists()
    assert len(fake.send_calls) == 1
    assert fake.send_calls[0][1] == content_hash


def test_email_send_without_gmail_connection_never_claims_sent(temp_email):
    email_p, outbox = temp_email
    fake = FakeGmailClient(error=GmailNotConnected())
    email_p._gmail_client = fake
    draft = email_p.draft_email(
        to="partner@local.internal",
        subject="Not delivered",
        body="This must not be archived.",
    )
    task_id = "task_not_connected"
    token, content_hash = _approval_token(email_p, draft, task_id=task_id)

    send_res = email_p.send_email(
        draft_path=draft["file_path"],
        task_id=task_id,
        approval_token=token,
    )

    assert send_res["success"] is False
    assert send_res["status"] == "NOT_SENT"
    assert send_res["provider_message_id"] is None
    assert send_res["draft_sha256"] == content_hash
    assert Path(draft["file_path"]).exists()
    assert not (outbox / "sent").exists()
    assert "oauth_flow connect" in send_res["setup_command"]


def test_email_send_without_provider_id_is_unconfirmed(temp_email):
    email_p, outbox = temp_email
    fake = FakeGmailClient(message_id=None)
    email_p._gmail_client = fake
    draft = email_p.draft_email(
        to="partner@local.internal",
        subject="Provider silent",
        body="No id, no success.",
    )
    task_id = "task_no_id"
    token, _hash = _approval_token(email_p, draft, task_id=task_id)

    send_res = email_p.send_email(
        draft_path=draft["file_path"],
        task_id=task_id,
        approval_token=token,
    )

    assert send_res["success"] is False
    assert send_res["status"] == "NOT_SENT"
    assert Path(draft["file_path"]).exists()
    assert not (outbox / "sent").exists()


def test_local_inbox_scan_is_explicit_fallback_with_assistant_identity(tmp_path):
    email_p = EmailPowers(outbox_dir=tmp_path / "outbox", gmail_client=FakeGmailClient(error=GmailNotConnected()))
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    msg = EmailMessage()
    msg["From"] = "recruiter@example.com"
    msg["To"] = settings.assistant_email
    msg["Subject"] = "Interview invitation"
    msg["Date"] = "Mon, 09 Nov 2026 10:00:00 +0000"
    msg.set_content("We would like to schedule an interview.")
    (inbox / "invite.eml").write_bytes(msg.as_bytes())

    result = email_p.scan_inbox_for_opportunities(inbox_dir=inbox)

    assert result["live_sync_active"] is False
    assert result["auth_method"] == "local_inbox"
    assert result["source"] == "local_inbox"
    assert result["account"] == settings.assistant_email
    assert result["opportunities_found"] == 1
    assert result["opportunities"][0]["category"] == "Interview Shortlist"
    assert result["opportunities"][0]["content_trust"] == "UNTRUSTED_EXTERNAL_DATA"
    assert "oauth_flow connect" in result["setup_note"]


def test_gmail_scan_uses_oauth_api_and_marks_untrusted(tmp_path):
    fake = FakeGmailClient(
        messages=[
            {
                "id": "m1",
                "from": "events@example.com",
                "subject": "Hackathon invitation",
                "date": "Mon, 09 Nov 2026",
                "body_text": "Join the hackathon briefing.",
            }
        ]
    )
    email_p = EmailPowers(outbox_dir=tmp_path / "outbox", gmail_client=fake)

    result = email_p.scan_inbox_for_opportunities(limit=5)

    assert result["live_sync_active"] is True
    assert result["auth_method"] == "oauth2"
    assert result["source"] == "gmail_oauth"
    assert result["opportunities_found"] == 1
    assert result["opportunities"][0]["subject"] == "Hackathon invitation"
    assert result["opportunities"][0]["content_trust"] == "UNTRUSTED_EXTERNAL_DATA"
    assert fake.list_calls and fake.list_calls[0]["max_results"] == 5


def test_email_powers_has_no_imap_or_password_path():
    source = Path(__file__).resolve().parents[1] / "jarvis" / "powers" / "email_powers.py"
    text = source.read_text(encoding="utf-8", errors="replace")
    assert "imaplib" not in text
    assert "GMAIL_APP_PASSWORD" not in text
    assert "nairganesh134@gmail.com" not in text
    assert "gmail_client.send_raw_message" in text
