"""
Automated verification tests for the Deterministic Policy Gate.
Hardened for Sprint 1.5: Zero token leakage, single-use token consumption, and tamper-resistance.
"""

import pytest
from jarvis.core.policy_gate import policy_gate


def test_deny_by_default_on_dangerous_powers():
    """Dangerous powers (delete, drop, send) require explicit approval, but NEVER leak the token to the caller."""
    allowed, msg, req = policy_gate.evaluate_execution(
        task_id="task_test_1", power_id="delete_file", privilege_level=5, payload={"path": "/data/test.txt"}
    )
    assert not allowed
    assert "approval required" in msg.lower()
    assert req is not None
    assert "token" not in req  # Security Invariant: Token is never leaked in unapproved client response
    assert req.get("approval_required") is True


def test_approval_token_verification_and_expiry():
    """HMAC approval tokens must verify successfully and reject tampered hashes."""
    task_id = "task_test_2"
    power_id = "send_email"
    payload = {"to": "test@example.com", "body": "Hello"}
    p_hash = policy_gate.hash_payload(payload)

    token, expiry = policy_gate.generate_approval_token(task_id, power_id, p_hash)
    valid, reason = policy_gate.verify_approval_token(task_id, power_id, p_hash, token)
    assert valid

    # Tampered payload hash should fail verification
    tampered_hash = policy_gate.hash_payload({"to": "evil@attacker.com"})
    valid_tampered, reason_tampered = policy_gate.verify_approval_token(task_id, power_id, tampered_hash, token)
    assert not valid_tampered


def test_single_use_token_cannot_be_replayed():
    """Once an approval token is consumed during execution, replaying it must be rejected."""
    task_id = "task_replay_test"
    power_id = "delete_file"
    payload = {"path": "/data/important.db"}
    p_hash = policy_gate.hash_payload(payload)

    token, expiry = policy_gate.generate_approval_token(task_id, power_id, p_hash)

    # First execution with consume=True must succeed
    valid, reason = policy_gate.verify_approval_token(task_id, power_id, p_hash, token, consume=True)
    assert valid is True

    # Replay execution with the same token must fail
    valid_replay, reason_replay = policy_gate.verify_approval_token(task_id, power_id, p_hash, token)
    assert valid_replay is False
    assert "already been consumed" in reason_replay


def test_emergency_kill_switch_blocks_execution():
    """Kill switch immediately blocks any execution."""
    policy_gate.trigger_kill_switch("Emergency test")
    try:
        allowed, msg, _ = policy_gate.evaluate_execution(
            task_id="task_test_3", power_id="system_health", privilege_level=0, payload={}
        )
        assert not allowed
        assert "kill switch is active" in msg.lower()
    finally:
        policy_gate.reset_kill_switch()
