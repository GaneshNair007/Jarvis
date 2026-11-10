"""Tests for JARVIS Email Powers and Policy Gate integration."""

import hashlib
from pathlib import Path
import pytest
from jarvis.powers.email_powers import EmailPowers
from jarvis.core.policy_gate import policy_gate


@pytest.fixture
def temp_email(tmp_path: Path):
    outbox = tmp_path / "outbox"
    return EmailPowers(outbox_dir=outbox), outbox


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

    # Verify outbox listing
    outbox_list = email_p.list_outbox(outbox)
    assert outbox_list["count"] == 1


def test_email_send_without_approval_is_refused(temp_email):
    email_p, _ = temp_email
    draft = email_p.draft_email(
        to="external@partner.org",
        subject="Confidential Dispatch",
        body="Sensitive update payload.",
    )

    # Attempt to send without approval token
    send_res = email_p.send_email(draft_path=draft["file_path"], task_id="task_unapproved")
    assert send_res["success"] is False
    assert send_res["status"] == "APPROVAL_REQUIRED"
    assert "pending_approval" in send_res


def test_email_send_unconfigured_credentials_truthful_rejection(temp_email):
    """Verifies that an approved draft is NOT marked SENT or moved to sent/ when SMTP is unconfigured."""
    email_p, _ = temp_email
    draft = email_p.draft_email(
        to="partner@local.internal",
        subject="Approved Communication",
        body="Action authorized by user.",
    )

    task_id = "task_approved_001"
    raw_bytes = Path(draft["file_path"]).read_bytes()
    content_hash = hashlib.sha256(raw_bytes).hexdigest()
    exec_payload = {"draft_path": str(Path(draft["file_path"])), "sha256": content_hash}
    payload_hash = policy_gate.hash_payload(exec_payload)

    # Pre-generate valid approval token via policy_gate
    token, expiry = policy_gate.generate_approval_token(
        task_id=task_id,
        power_id="send_email",
        payload_hash=payload_hash,
    )

    # Sending without SMTP credentials configured must report NOT_CONFIGURED and NOT fake a successful transmission
    send_res = email_p.send_email(
        draft_path=draft["file_path"],
        task_id=task_id,
        approval_token=token,
    )

    assert send_res["success"] is False
    assert send_res["status"] == "NOT_CONFIGURED"
    assert "No SMTP credentials" in send_res["error"]
    assert Path(draft["file_path"]).exists()  # Kept in outbox, never moved to sent/


def test_email_send_explicit_archive_only_mode(temp_email):
    """Verifies that explicit local archival returns ARCHIVED_NOT_SENT and does not fake a SENT status."""
    email_p, _ = temp_email
    draft = email_p.draft_email(
        to="partner@local.internal",
        subject="Archive Test Draft",
        body="Draft to be archived locally.",
    )

    task_id = "task_archive_001"
    raw_bytes = Path(draft["file_path"]).read_bytes()
    content_hash = hashlib.sha256(raw_bytes).hexdigest()
    exec_payload = {"draft_path": str(Path(draft["file_path"])), "sha256": content_hash}
    payload_hash = policy_gate.hash_payload(exec_payload)

    token, _ = policy_gate.generate_approval_token(
        task_id=task_id,
        power_id="send_email",
        payload_hash=payload_hash,
    )

    send_res = email_p.send_email(
        draft_path=draft["file_path"],
        task_id=task_id,
        approval_token=token,
        archive_only=True,
    )

    assert send_res["success"] is False
    assert send_res["status"] == "ARCHIVED_NOT_SENT"
    assert "archive_path" in send_res
    assert Path(send_res["archive_path"]).exists()
    assert "archived" in send_res["archive_path"]


def test_scan_inbox_disconnected_truthful_status(temp_email, monkeypatch):
    """Verifies that when credentials are not configured, scan_inbox returns DISCONNECTED without fake data."""
    email_p, _ = temp_email
    monkeypatch.delenv("GMAIL_USER", raising=False)
    monkeypatch.delenv("GMAIL_ADDRESS", raising=False)
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)
    monkeypatch.delenv("GMAIL_PASSWORD", raising=False)
    monkeypatch.delenv("GMAIL_OAUTH_TOKEN", raising=False)

    res = email_p.scan_inbox_for_opportunities()
    assert res["status"] == "DISCONNECTED"
    assert res["connected"] is False
    assert res["fabricated"] is False
    assert res["opportunities_found"] == 0
    assert res["opportunities"] == []
    assert "not configured" in res["message"]


def test_send_email_real_smtplib_delivery(temp_email, monkeypatch):
    """Verifies that send_email genuinely uses smtplib when SMTP credentials are configured."""
    from unittest.mock import MagicMock, patch

    email_p, _ = temp_email
    draft = email_p.draft_email(
        to="recipient@example.com",
        subject="SMTP Delivery Test",
        body="Testing real SMTP transmission.",
    )

    task_id = "task_smtp_test"
    raw_bytes = Path(draft["file_path"]).read_bytes()
    content_hash = hashlib.sha256(raw_bytes).hexdigest()
    exec_payload = {"draft_path": str(Path(draft["file_path"])), "sha256": content_hash}
    payload_hash = policy_gate.hash_payload(exec_payload)

    token, _ = policy_gate.generate_approval_token(
        task_id=task_id,
        power_id="send_email",
        payload_hash=payload_hash,
    )

    monkeypatch.setenv("SMTP_HOST", "smtp.testserver.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "testuser@testserver.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret_pass")

    mock_smtp_instance = MagicMock()
    mock_smtp_instance.__enter__.return_value = mock_smtp_instance

    with patch("smtplib.SMTP", return_value=mock_smtp_instance) as mock_smtp_class:
        send_res = email_p.send_email(
            draft_path=draft["file_path"],
            task_id=task_id,
            approval_token=token,
        )

        assert send_res["success"] is True
        assert send_res["status"] == "SENT"
        assert send_res["delivery_channel"] == "DELIVERED_VIA_SMTP"
        mock_smtp_class.assert_called_once_with("smtp.testserver.com", 587, timeout=15)
        mock_smtp_instance.starttls.assert_called_once()
        mock_smtp_instance.login.assert_called_once_with("testuser@testserver.com", "secret_pass")
        mock_smtp_instance.send_message.assert_called_once()


def test_derive_action_from_content_with_dates(temp_email):
    """Verifies regex date extraction works cleanly without NameError."""
    email_p, _ = temp_email
    action = email_p._derive_action_from_content(
        subject="Interview Invitation for Senior AI Engineer",
        sender="recruiter@tech.corp",
        body="We would like to invite you for an interview on Tuesday, Nov 15th at 2:00 PM IST.",
    )
    assert "interview invitation" in action.lower()
    assert "tuesday" in action.lower()

