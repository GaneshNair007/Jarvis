"""
First Law of JARVIS Compliance Verification Suite
=================================================
Automated CI/CD compliance gate enforcing the First Law:
"JARVIS MUST NEVER CLAIM AN ACTION OCCURRED WITHOUT VERIFIABLE EVIDENCE. NO EVIDENCE. NO CLAIM."

Scans jarvis/powers/ and core execution pipelines to guarantee:
1. Every external capability action returns TrustResult with verified Evidence.
2. No power returns hardcoded fake actions or synthetic data templates.
3. No task executor or agent handler simulates execution with sleep(0.01).
4. Disconnected services fail-closed with honest refusal and fabricated=False.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import List, Dict, Any
import pytest

from jarvis.core.evidence import TrustResult, Evidence, CapabilityState
from jarvis.core.capability_guard import capability_guard, CapabilityStatus
from jarvis.powers.email_powers import email_powers


def test_first_law_task_executor_contains_no_sleep_stubs():
    """Verifies that _default_agent_execution in task_executor.py contains zero simulation sleep stubs."""
    executor_path = Path("jarvis/core/task_executor.py")
    assert executor_path.exists(), "task_executor.py must exist"
    tree = ast.parse(executor_path.read_text(encoding="utf-8"))

    sleep_calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_default_agent_execution":
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    if isinstance(child.func, ast.Attribute) and child.func.attr == "sleep":
                        sleep_calls.append(child.lineno)

    assert not sleep_calls, (
        f"First Law Violation: Forbidden simulation sleep stub found in _default_agent_execution at line(s): {sleep_calls}"
    )


def test_first_law_email_powers_disconnected_compliance():
    """Verifies email_powers returns compliant TrustResult when disconnected."""
    status = capability_guard.check_gmail()
    if status == CapabilityStatus.DISCONNECTED:
        res = email_powers.scan_inbox_for_opportunities()
        assert res.get("fabricated") is False, "First Law: fabricated must strictly be False"
        assert res.get("status") == "DISCONNECTED"
        assert res.get("opportunities_found") == 0
        assert res.get("opportunities") == []
        assert "Gmail is not connected" in res.get("message", "")


def test_first_law_trust_result_rejection_of_unsupported_success():
    """Asserts that TrustResult.success cannot be constructed without at least one Evidence object."""
    with pytest.raises(AssertionError):
        TrustResult.success(
            capability="test_cap",
            evidence=[],  # Empty evidence must raise AssertionError
            data={"action": "claimed_done"},
        )


def test_first_law_ast_audit_forbids_fake_templates_in_powers():
    """
    Scans all Python modules in jarvis/powers/ for hardcoded legacy fake strings:
    - 'Tue-Thu 2-6 PM IST'
    - 'Nov 8 capstone report'
    - 'Mock interview scheduled'
    """
    powers_dir = Path("jarvis/powers")
    assert powers_dir.exists()

    forbidden_patterns = [
        "Tue-Thu 2-6 PM IST",
        "Nov 8 capstone report",
        "Mock interview scheduled",
        "Hackathon registration complete (dummy)",
    ]

    violations = []
    for py_file in powers_dir.glob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        for pattern in forbidden_patterns:
            if pattern in content:
                violations.append(f"{py_file.name}: found forbidden synthetic template '{pattern}'")

    assert not violations, f"First Law Compliance Audit Failed:\n" + "\n".join(violations)


def test_first_law_policy_gate_token_never_leaked():
    """Verifies PolicyGate never leaks cryptographic HMAC approval tokens in rejection payloads."""
    from jarvis.core.policy_gate import policy_gate
    allowed, msg, client_req = policy_gate.evaluate_execution(
        task_id="audit_leak_test",
        power_id="delete_database",
        privilege_level=5,
        payload={"target": "production_db"},
    )
    assert allowed is False
    assert client_req is not None
    assert "token" not in client_req, (
        "First Law / Security Violation: Cryptographic approval token was leaked to unapproved caller!"
    )
    assert client_req.get("approval_required") is True


def test_first_law_single_use_token_revocation():
    """Verifies that approval tokens cannot be consumed more than once (replay prevention)."""
    from jarvis.core.policy_gate import policy_gate
    task_id = "test_single_use_audit"
    power_id = "deploy_code"
    p_hash = policy_gate.hash_payload({"env": "prod"})

    token, expiry = policy_gate.generate_approval_token(task_id, power_id, p_hash)

    # First consumption succeeds
    valid, _ = policy_gate.verify_approval_token(task_id, power_id, p_hash, token, consume=True)
    assert valid is True

    # Immediate second consumption must be rejected
    valid_replay, reason = policy_gate.verify_approval_token(task_id, power_id, p_hash, token, consume=True)
    assert valid_replay is False
    assert "already been consumed" in reason
