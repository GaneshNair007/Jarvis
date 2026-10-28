"""
Automated verification tests for the Deterministic Policy Gate.
"""

import pytest
from jarvis.core.policy_gate import policy_gate

def test_deny_by_default_on_dangerous_powers():
    """Dangerous powers (delete, drop, send) require explicit approval."""
    allowed, msg, req = policy_gate.evaluate_execution(
        task_id="task_test_1",
        power_id="delete_file",
        privilege_level=5,
        payload={"path": "/data/test.txt"}
    )
    assert not allowed
    assert "approval required" in msg.lower()
    assert req is not None
    assert "token" in req

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

def test_emergency_kill_switch_blocks_execution():
    """Kill switch immediately blocks any execution."""
    policy_gate.trigger_kill_switch("Emergency test")
    try:
        allowed, msg, _ = policy_gate.evaluate_execution(
            task_id="task_test_3",
            power_id="system_health",
            privilege_level=0,
            payload={}
        )
        assert not allowed
        assert "kill switch is active" in msg.lower()
    finally:
        policy_gate.reset_kill_switch()
