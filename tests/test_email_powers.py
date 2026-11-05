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


def test_email_send_with_valid_cryptographic_approval(temp_email):
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

    send_res = email_p.send_email(
        draft_path=draft["file_path"],
        task_id=task_id,
        approval_token=token,
    )

    assert send_res["success"] is True
    assert send_res["status"] == "SENT"
    assert Path(send_res["archive_path"]).exists()
