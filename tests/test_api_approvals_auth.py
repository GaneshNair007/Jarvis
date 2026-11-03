"""
Comprehensive Security and Authorization Hardening Verification Suite.
Covers all 4 confirmed vulnerabilities for Milestone 3:
1. FINDING-P0-05: Zero Token Leakage in Refusal Payloads (JARVIS-SEC-001)
2. FINDING-P0-06: Fail-Closed Endpoint Admin Authentication Enforcement (JARVIS-SEC-002)
3. FINDING-P1-02: Single-Use Token Consumption & Replay Prevention (JARVIS-SEC-003)
4. FINDING-P1-03: 5-Tuple Cryptographic User Binding & Dual-Mode Compatibility (JARVIS-SEC-005)
"""

import pytest
import time
import uuid
import hmac
import hashlib
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient

from jarvis.config import settings
from jarvis.core.policy_gate import policy_gate
from jarvis.api.server import app, verify_expensive_call_token

client = TestClient(app)


# ==============================================================================
# 1. FINDING-P0-05: Zero Token Leakage in Refusal Payloads
# ==============================================================================

def test_p0_05_refusal_payload_never_leaks_token():
    """Verifies that PolicyGate.evaluate_execution refusal contains NO executable token."""
    task_id = f"tsk_p0_05_{uuid.uuid4().hex[:6]}"
    power_id = "delete_file"
    payload = {"path": "/var/data/confidential.db"}

    allowed, msg, req = policy_gate.evaluate_execution(
        task_id=task_id,
        power_id=power_id,
        privilege_level=5,
        payload=payload,
    )

    # 1. Action MUST be refused
    assert allowed is False
    assert "approval required" in msg.lower()
    assert req is not None

    # 2. Refusal dictionary MUST NOT contain executable tokens
    assert "token" not in req, "SECURITY DEFECT: Executable token leaked in refusal payload!"
    assert "approval_token" not in req, "SECURITY DEFECT: approval_token leaked in refusal payload!"

    # 3. Refusal record MUST indicate pending status with an approval_id
    assert req.get("status") == "PENDING"
    assert "approval_id" in req
    assert req.get("approval_id").startswith("appr_")
    assert req.get("power_id") == power_id
    assert req.get("payload_hash") == policy_gate.hash_payload(payload)


def test_p0_05_autonomous_token_extraction_and_bypass_fails():
    """Adversarial exploit test: Caller attempts to bootstrap execution from refusal data."""
    task_id = f"tsk_exploit_{uuid.uuid4().hex[:6]}"
    power_id = "format_disk"
    payload = {"target": "C:", "force": True}

    # Turn 1: Attempt unapproved execution
    allowed1, _, req1 = policy_gate.evaluate_execution(
        task_id=task_id, power_id=power_id, privilege_level=5, payload=payload
    )
    assert allowed1 is False

    # Turn 2a: Attempt to use the approval_id as an approval_token
    approval_id = req1["approval_id"]
    allowed2a, reason2a, _ = policy_gate.evaluate_execution(
        task_id=task_id, power_id=power_id, privilege_level=5, payload=payload, approval_token=approval_id
    )
    assert allowed2a is False
    assert "APPROVAL FAILED" in reason2a

    # Turn 2b: Attempt to extract req1.get("token") which is None
    allowed2b, reason2b, _ = policy_gate.evaluate_execution(
        task_id=task_id, power_id=power_id, privilege_level=5, payload=payload, approval_token=req1.get("token")
    )
    assert allowed2b is False


# ==============================================================================
# 2. FINDING-P0-06: Endpoint Admin Authentication Enforcement
# ==============================================================================

def test_p0_06_unauthenticated_resolve_endpoint_rejected():
    """Unauthenticated calls to /api/v1/approvals/{task_id}/resolve MUST fail with HTTP 401."""
    task_id = f"tsk_unauth_{uuid.uuid4().hex[:6]}"
    policy_gate.evaluate_execution(
        task_id=task_id, power_id="drop_database", privilege_level=5, payload={"db": "prod"}
    )

    res = client.post(
        f"/api/v1/approvals/{task_id}/resolve",
        json={"task_id": task_id, "approved": True, "user_id": "attacker"},
    )
    assert res.status_code == 401
    assert "WWW-Authenticate" in res.headers


def test_p0_06_invalid_token_resolve_endpoint_rejected():
    """Calls to /api/v1/approvals/{task_id}/resolve with invalid token MUST fail with HTTP 403."""
    task_id = f"tsk_invalid_{uuid.uuid4().hex[:6]}"
    policy_gate.evaluate_execution(
        task_id=task_id, power_id="drop_database", privilege_level=5, payload={"db": "prod"}
    )

    res = client.post(
        f"/api/v1/approvals/{task_id}/resolve",
        json={"task_id": task_id, "approved": True, "user_id": settings.jarvis_user_id},
        headers={"X-Admin-Token": "invalid_forged_secret_token"},
    )
    assert res.status_code == 403
    assert "Authorization failed" in res.json()["detail"]


def test_p0_06_user_impersonation_resolve_endpoint_rejected():
    """Admin credentials supplied with mismatched X-Jarvis-User-Id header MUST fail with HTTP 403."""
    task_id = f"tsk_impers_{uuid.uuid4().hex[:6]}"
    policy_gate.evaluate_execution(
        task_id=task_id, power_id="drop_database", privilege_level=5, payload={"db": "prod"}
    )

    res = client.post(
        f"/api/v1/approvals/{task_id}/resolve",
        json={"task_id": task_id, "approved": True, "user_id": "impostor"},
        headers={
            "X-Admin-Token": settings.jarvis_secret_key,
            "X-Jarvis-User-Id": "impostor",
        },
    )
    assert res.status_code == 403


def test_p0_06_authenticated_resolve_endpoint_issues_valid_token():
    """Authenticated administrator approval issues a valid, user-bound HMAC execution token."""
    task_id = f"tsk_auth_{uuid.uuid4().hex[:6]}"
    payload = {"db": "analytics"}
    policy_gate.evaluate_execution(
        task_id=task_id, power_id="drop_database", privilege_level=5, payload=payload
    )

    # Submit resolution with valid X-Admin-Token
    auth_headers = {"X-Admin-Token": settings.jarvis_secret_key}
    res = client.post(
        f"/api/v1/approvals/{task_id}/resolve",
        json={"task_id": task_id, "approved": True, "user_id": settings.jarvis_user_id},
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "APPROVED"
    assert "approval_token" in data

    # Verify that the issued token executes successfully through PolicyGate
    token = data["approval_token"]
    allowed, msg, _ = policy_gate.evaluate_execution(
        task_id=task_id,
        power_id="drop_database",
        privilege_level=5,
        payload=payload,
        approval_token=token,
        user_id=settings.jarvis_user_id,
    )
    assert allowed is True
    assert "approved execution" in msg.lower()


def test_p0_06_tasks_approve_endpoint_requires_auth():
    """POST /tasks/{task_id}/approve enforces verify_admin_user."""
    task_id = f"tsk_approve_route_{uuid.uuid4().hex[:6]}"
    policy_gate.evaluate_execution(
        task_id=task_id, power_id="delete_file", privilege_level=5, payload={"path": "/data/test"}
    )

    # 1. Unauthenticated request fails with 401
    res_unauth = client.post(
        f"/tasks/{task_id}/approve",
        json={"approved": True, "notes": "Approved by user"},
    )
    assert res_unauth.status_code == 401

    # 2. Authenticated request succeeds with 200
    res_auth = client.post(
        f"/tasks/{task_id}/approve",
        json={"approved": True, "notes": "Approved by user", "user_id": settings.jarvis_user_id},
        headers={"Authorization": f"Bearer {settings.jarvis_secret_key}"},
    )
    assert res_auth.status_code == 200
    assert res_auth.json()["status"] == "APPROVED"
    assert "approval_token" in res_auth.json()


def test_p0_06_expensive_call_approval_requires_auth_and_issues_hmac():
    """POST /model/approve-expensive-call requires admin auth and returns HMAC token."""
    task_id = f"tsk_exp_{uuid.uuid4().hex[:6]}"
    target_model = "claude-3-7-sonnet"

    # 1. Unauthenticated fails with 401
    res_unauth = client.post(
        "/model/approve-expensive-call",
        json={"task_id": task_id, "target_model": target_model, "approved": True},
    )
    assert res_unauth.status_code == 401

    # 2. Authenticated succeeds with HMAC token
    res_auth = client.post(
        "/model/approve-expensive-call",
        json={"task_id": task_id, "target_model": target_model, "approved": True},
        headers={"X-Admin-Token": settings.jarvis_secret_key},
    )
    assert res_auth.status_code == 200
    data = res_auth.json()
    assert data["status"] == "approved"
    assert data["token"].startswith("exp_hmac_")
    assert "expires_at" in data

    # 3. Verify cryptographic token helper
    token = data["token"]
    valid, reason = verify_expensive_call_token(token, task_id, target_model, user_id=settings.jarvis_user_id)
    assert valid is True
    assert "valid and verified" in reason

    # 4. Tampered model fails verification
    valid_tampered, reason_tampered = verify_expensive_call_token(token, task_id, "gpt-4o", user_id=settings.jarvis_user_id)
    assert valid_tampered is False
    assert "Invalid cryptographic signature" in reason_tampered


# ==============================================================================
# 3. FINDING-P1-02: Single-Use Token Consumption & Replay Prevention
# ==============================================================================

def test_p1_02_approval_token_single_use_consumption():
    """Verifies that an approval token cannot be replayed after initial execution."""
    task_id = f"tsk_replay_{uuid.uuid4().hex[:6]}"
    power_id = "wipe_system"
    payload = {"disk": "/dev/sda"}
    payload_hash = policy_gate.hash_payload(payload)

    token, _ = policy_gate.generate_approval_token(task_id, power_id, payload_hash)

    # Execution 1: Legitimate first-time execution succeeds
    allowed1, _, _ = policy_gate.evaluate_execution(
        task_id=task_id, power_id=power_id, privilege_level=5, payload=payload, approval_token=token
    )
    assert allowed1 is True

    # Execution 2: Replay of identical token MUST fail
    allowed2, reason2, _ = policy_gate.evaluate_execution(
        task_id=task_id, power_id=power_id, privilege_level=5, payload=payload, approval_token=token
    )
    assert allowed2 is False
    assert "already been consumed" in reason2.lower()


def test_p1_02_concurrent_token_replay_race_condition():
    """Adversarial stress test: 10 threads attempt simultaneous replay of a single token."""
    task_id = f"tsk_race_{uuid.uuid4().hex[:6]}"
    power_id = "deploy_production"
    payload = {"version": "v2.0.0"}
    payload_hash = policy_gate.hash_payload(payload)

    token, _ = policy_gate.generate_approval_token(task_id, power_id, payload_hash)

    results = []

    def _execute():
        return policy_gate.evaluate_execution(
            task_id=task_id, power_id=power_id, privilege_level=5, payload=payload, approval_token=token
        )

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(_execute) for _ in range(10)]
        for f in futures:
            results.append(f.result()[0])

    # Exactly ONE invocation must succeed; 9 must fail closed
    assert results.count(True) == 1, f"Expected exactly 1 execution success, got {results.count(True)}"
    assert results.count(False) == 9


# ==============================================================================
# 4. FINDING-P1-03: Cryptographic User Binding & Backward Compatibility
# ==============================================================================

def test_p1_03_token_cryptographically_binds_user_id():
    """Verifies that an HMAC token signed for Alice is rejected when evaluated under Bob."""
    task_id = f"tsk_user_bind_{uuid.uuid4().hex[:6]}"
    power_id = "execute_trade"
    payload = {"symbol": "BTCUSD", "qty": 1.5}
    payload_hash = policy_gate.hash_payload(payload)

    # Token generated specifically for 'alice'
    token_alice, _ = policy_gate.generate_approval_token(
        task_id=task_id, power_id=power_id, payload_hash=payload_hash, user_id="alice"
    )

    # 1. Verification under 'alice' succeeds
    valid_alice, _ = policy_gate.verify_approval_token(
        task_id=task_id, power_id=power_id, payload_hash=payload_hash, token=token_alice, user_id="alice"
    )
    assert valid_alice is True

    # 2. Verification under 'bob' FAILS
    valid_bob, reason_bob = policy_gate.verify_approval_token(
        task_id=task_id, power_id=power_id, payload_hash=payload_hash, token=token_alice, user_id="bob"
    )
    assert valid_bob is False
    assert "Invalid cryptographic signature" in reason_bob

    # 3. Evaluation under 'bob' via PolicyGate FAILS
    allowed, msg, _ = policy_gate.evaluate_execution(
        task_id=task_id,
        power_id=power_id,
        privilege_level=5,
        payload=payload,
        approval_token=token_alice,
        user_id="bob",
    )
    assert allowed is False
    assert "APPROVAL FAILED" in msg


def test_p1_03_default_user_graceful_fallback():
    """Verifies that omitting user_id defaults to settings.jarvis_user_id without breakage."""
    task_id = f"tsk_default_user_{uuid.uuid4().hex[:6]}"
    power_id = "send_email"
    payload = {"recipient": "ceo@example.com", "subject": "Quarterly Report"}
    payload_hash = policy_gate.hash_payload(payload)

    # Token generated without specifying user_id
    token, _ = policy_gate.generate_approval_token(task_id, power_id, payload_hash)

    # Verification without specifying user_id succeeds
    valid, reason = policy_gate.verify_approval_token(task_id, power_id, payload_hash, token)
    assert valid is True
    assert "valid and verified" in reason


def test_p1_03_legacy_4_element_token_backward_compatibility():
    """Verifies that legacy 4-element tokens verify successfully under backward compatibility."""
    task_id = f"tsk_legacy_{uuid.uuid4().hex[:6]}"
    power_id = "shutdown_host"
    payload = {"force": True}
    payload_hash = policy_gate.hash_payload(payload)
    expiry = int(time.time() + 900)

    # Construct raw legacy 4-tuple HMAC: f"{task_id}:{power_id}:{payload_hash}:{expiry}"
    legacy_msg = f"{task_id}:{power_id}:{payload_hash}:{expiry}".encode("utf-8")
    legacy_sig = hmac.new(settings.jarvis_secret_key.encode("utf-8"), legacy_msg, hashlib.sha256).hexdigest()
    legacy_token = f"{legacy_sig}.{expiry}"

    # PolicyGate must accept legacy token with compatibility status
    valid, reason = policy_gate.verify_approval_token(task_id, power_id, payload_hash, legacy_token)
    assert valid is True
    assert "legacy format" in reason or "valid and verified" in reason
