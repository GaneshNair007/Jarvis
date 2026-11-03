"""
Adversarial Stress Test Suite for API Approvals and Authorization Endpoints.
Challenger M3-2 verification harness for:
- POST /api/v1/approvals/{task_id}/resolve
- POST /tasks/{task_id}/approve
- POST /model/approve-expensive-call
- Expensive Call Token Cryptographic Binding & Confinement
"""

import hmac
import hashlib
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient

from jarvis.config import settings
from jarvis.core.policy_gate import policy_gate
from jarvis.core.state_machine import state_machine
from jarvis.api.server import app, generate_expensive_call_token, verify_expensive_call_token

client = TestClient(app)


# ==============================================================================
# 1. ADVERSARIAL CHALLENGES: /api/v1/approvals/{task_id}/resolve
# ==============================================================================

class TestAdversarialResolveEndpoint:
    """Stress testing /api/v1/approvals/{task_id}/resolve for auth bypass and tampering."""

    def test_unauthenticated_request_fails_closed(self):
        """Request without any authorization headers must return HTTP 401 with WWW-Authenticate."""
        res = client.post(
            "/api/v1/approvals/tsk_test_unauth/resolve",
            json={"task_id": "tsk_test_unauth", "approved": True, "user_id": settings.jarvis_user_id},
        )
        assert res.status_code == 401, f"Expected 401, got {res.status_code}: {res.text}"
        assert "WWW-Authenticate" in res.headers

    @pytest.mark.parametrize("blank_token", ["", "   ", "\t", "\n"])
    def test_blank_or_whitespace_admin_token_fails_closed(self, blank_token):
        """Empty or whitespace-only X-Admin-Token header must be rejected."""
        res = client.post(
            "/api/v1/approvals/tsk_test_blank/resolve",
            json={"task_id": "tsk_test_blank", "approved": True, "user_id": settings.jarvis_user_id},
            headers={"X-Admin-Token": blank_token},
        )
        assert res.status_code in (401, 403), f"Expected 401/403 for blank token, got {res.status_code}"

    @pytest.mark.parametrize("forged_token", [
        "admin",
        "secret",
        "dev_secret",
        "Bearer dev_secret_key_change_in_production_32b",
        "dev_secret_key_change_in_production_32b_extra",
        "dev_secret_key_change_in_production_32",
        "DEV_SECRET_KEY_CHANGE_IN_PRODUCTION_32B",
        "0" * 32,
        "'" + settings.jarvis_secret_key + "'",
        "None",
    ])
    def test_forged_admin_token_rejected_with_403(self, forged_token):
        """Attacker using forged or slightly altered tokens must receive HTTP 403 Forbidden."""
        res = client.post(
            "/api/v1/approvals/tsk_test_forged/resolve",
            json={"task_id": "tsk_test_forged", "approved": True, "user_id": settings.jarvis_user_id},
            headers={"X-Admin-Token": forged_token},
        )
        assert res.status_code == 403, f"Expected 403 for forged token '{forged_token}', got {res.status_code}"
        assert "Authorization failed" in res.json().get("detail", "")

    def test_spoofed_user_id_in_header_rejected(self):
        """Valid secret key provided with unauthorized X-Jarvis-User-Id header must fail."""
        res = client.post(
            "/api/v1/approvals/tsk_test_spoofed_hdr/resolve",
            json={"task_id": "tsk_test_spoofed_hdr", "approved": True, "user_id": settings.jarvis_user_id},
            headers={
                "X-Admin-Token": settings.jarvis_secret_key,
                "X-Jarvis-User-Id": "attacker_user",
            },
        )
        assert res.status_code == 403
        assert "not authorized as administrator" in res.json().get("detail", "")

    def test_spoofed_user_id_in_payload_rejected(self):
        """Valid secret key provided with mismatched user_id in payload body must fail."""
        # Create a pending approval
        task_id = f"tsk_spoof_body_{uuid.uuid4().hex[:6]}"
        policy_gate.evaluate_execution(
            task_id=task_id, power_id="delete_database", privilege_level=5, payload={"db": "test"}
        )

        res = client.post(
            f"/api/v1/approvals/{task_id}/resolve",
            json={"task_id": task_id, "approved": True, "user_id": "attacker_in_body"},
            headers={"X-Admin-Token": settings.jarvis_secret_key},
        )
        assert res.status_code == 403
        assert "does not match authenticated admin" in res.json().get("detail", "")

    def test_nonexistent_task_id_returns_404(self):
        """Resolving an unknown task_id with valid admin credentials returns 404."""
        nonexistent = f"tsk_nonexistent_{uuid.uuid4().hex[:8]}"
        res = client.post(
            f"/api/v1/approvals/{nonexistent}/resolve",
            json={"task_id": nonexistent, "approved": True, "user_id": settings.jarvis_user_id},
            headers={"X-Admin-Token": settings.jarvis_secret_key},
        )
        assert res.status_code == 404
        assert "No pending approval found" in res.json().get("detail", "")

    def test_denial_resolution_clears_pending_and_fails_closed(self):
        """Denying approval (approved=False) removes pending approval and returns REJECTED."""
        task_id = f"tsk_deny_{uuid.uuid4().hex[:6]}"
        policy_gate.evaluate_execution(
            task_id=task_id, power_id="format_filesystem", privilege_level=5, payload={"target": "D:"}
        )
        assert task_id in policy_gate.pending_approvals

        res = client.post(
            f"/api/v1/approvals/{task_id}/resolve",
            json={"task_id": task_id, "approved": False, "user_id": settings.jarvis_user_id},
            headers={"X-Admin-Token": settings.jarvis_secret_key},
        )
        assert res.status_code == 200
        assert res.json()["status"] == "REJECTED"
        assert "approval_token" not in res.json()
        assert task_id not in policy_gate.pending_approvals

        # Subsequent attempt to resolve again must fail with 404
        res_retry = client.post(
            f"/api/v1/approvals/{task_id}/resolve",
            json={"task_id": task_id, "approved": True, "user_id": settings.jarvis_user_id},
            headers={"X-Admin-Token": settings.jarvis_secret_key},
        )
        assert res_retry.status_code == 404

    @pytest.mark.parametrize("hostile_id", [
        "../../../etc/passwd",
        "tsk' OR '1'='1",
        "tsk<script>alert(1)</script>",
        "tsk%00nullbyte",
        "tsk" + "A" * 500,
    ])
    def test_hostile_task_id_fails_closed_without_500(self, hostile_id):
        """Hostile strings in task_id URL parameter must fail closed (404/422), never crash 500."""
        res = client.post(
            f"/api/v1/approvals/{hostile_id}/resolve",
            json={"task_id": hostile_id, "approved": True, "user_id": settings.jarvis_user_id},
            headers={"X-Admin-Token": settings.jarvis_secret_key},
        )
        assert res.status_code in (404, 422), f"Expected 404/422 for hostile id, got {res.status_code}"


# ==============================================================================
# 2. ADVERSARIAL CHALLENGES: /tasks/{task_id}/approve
# ==============================================================================

class TestAdversarialTaskApproveEndpoint:
    """Stress testing /tasks/{task_id}/approve for authorization enforcement."""

    def test_unauthenticated_approve_fails_closed(self):
        """POST /tasks/{task_id}/approve without auth must return 401."""
        res = client.post(
            "/tasks/tsk_test_unauth/approve",
            json={"approved": True, "notes": "approve this"},
        )
        assert res.status_code == 401

    @pytest.mark.parametrize("forged_header", [
        {"X-Admin-Token": "bad_token"},
        {"Authorization": "Bearer bad_secret"},
        {"Authorization": "Bearer "},
        {"X-Admin-Token": ""},
    ])
    def test_bad_auth_headers_fail_closed(self, forged_header):
        """Invalid bearer or X-Admin-Token headers must fail with 401 or 403."""
        res = client.post(
            "/tasks/tsk_test_bad_auth/approve",
            json={"approved": True, "notes": "approve this"},
            headers=forged_header,
        )
        assert res.status_code in (401, 403)

    def test_user_impersonation_in_body_fails_closed(self):
        """Authenticating with valid admin token but providing rogue user_id in body fails with 403."""
        task_id = f"tsk_rogue_body_{uuid.uuid4().hex[:6]}"
        policy_gate.evaluate_execution(
            task_id=task_id, power_id="restart_service", privilege_level=4, payload={"svc": "nginx"}
        )

        res = client.post(
            f"/tasks/{task_id}/approve",
            json={"approved": True, "notes": "sneaky", "user_id": "malicious_user"},
            headers={"X-Admin-Token": settings.jarvis_secret_key},
        )
        assert res.status_code == 403
        assert "does not match authenticated admin" in res.json().get("detail", "")

    def test_approve_denial_transitions_state_machine_and_cleans_up(self):
        """Denying approval via /tasks/{task_id}/approve sets REJECTED and removes pending approval."""
        task_id = f"tsk_deny_route_{uuid.uuid4().hex[:6]}"
        state_machine.create_task(task_id=task_id, initial_status="POLICY_CHECK")
        policy_gate.evaluate_execution(
            task_id=task_id, power_id="reboot_cluster", privilege_level=5, payload={"force": True}
        )
        assert task_id in policy_gate.pending_approvals

        res = client.post(
            f"/tasks/{task_id}/approve",
            json={"approved": False, "notes": "Rejected by ops supervisor", "user_id": settings.jarvis_user_id},
            headers={"X-Admin-Token": settings.jarvis_secret_key},
        )
        assert res.status_code == 200
        assert res.json()["status"] == "REJECTED"
        assert task_id not in policy_gate.pending_approvals
        assert state_machine.get_task_state(task_id) == "REJECTED"


# ==============================================================================
# 3. ADVERSARIAL CHALLENGES: /model/approve-expensive-call & Token Spoofing
# ==============================================================================

class TestAdversarialExpensiveCallApproval:
    """Stress testing /model/approve-expensive-call and cryptographic token forgery."""

    def test_unauthenticated_expensive_call_approval_fails_closed(self):
        """Unauthenticated request to /model/approve-expensive-call must fail with 401."""
        res = client.post(
            "/model/approve-expensive-call",
            json={"task_id": "tsk_exp_1", "target_model": "claude-3-7-sonnet", "approved": True},
        )
        assert res.status_code == 401

    def test_unauthenticated_rejection_also_fails_closed(self):
        """Even an approved=False call without auth must fail with 401, not bypass auth."""
        res = client.post(
            "/model/approve-expensive-call",
            json={"task_id": "tsk_exp_1", "target_model": "claude-3-7-sonnet", "approved": False},
        )
        assert res.status_code == 401

    def test_legacy_predictable_token_format_is_rejected(self):
        """Legacy plaintext format 'exp_app_{timestamp}' must NOT be verified as valid."""
        legacy_token = f"exp_app_{int(time.time())}"
        valid, reason = verify_expensive_call_token(
            token=legacy_token,
            task_id="tsk_test",
            target_model="claude-3-7-sonnet",
            user_id=settings.jarvis_user_id,
        )
        assert valid is False
        assert "missing exp_hmac_ prefix" in reason

    def test_forged_hmac_signature_fails_verification(self):
        """Random or attacker-computed signature fails verification."""
        forged_sig = "a" * 64
        expiry = int(time.time() + 900)
        forged_token = f"exp_hmac_{forged_sig}.{expiry}"

        valid, reason = verify_expensive_call_token(
            token=forged_token,
            task_id="tsk_test",
            target_model="claude-3-7-sonnet",
            user_id=settings.jarvis_user_id,
        )
        assert valid is False
        assert "Invalid cryptographic signature" in reason

    def test_expired_expensive_call_token_fails_verification(self):
        """Token with an expired timestamp (even if correctly signed) fails verification."""
        past_expiry = int(time.time() - 100)
        user = settings.jarvis_user_id
        task_id = "tsk_expired"
        model = "gpt-4o"
        message = f"expensive:{user}:{task_id}:{model}:{past_expiry}".encode("utf-8")
        sig = hmac.new(settings.jarvis_secret_key.encode("utf-8"), message, hashlib.sha256).hexdigest()
        expired_token = f"exp_hmac_{sig}.{past_expiry}"

        valid, reason = verify_expensive_call_token(
            token=expired_token,
            task_id=task_id,
            target_model=model,
            user_id=user,
        )
        assert valid is False
        assert "expired" in reason.lower()

    def test_cross_model_token_substitution_fails_verification(self):
        """A valid expensive token issued for a cheaper model cannot authorize a more expensive model."""
        task_id = f"tsk_cross_model_{uuid.uuid4().hex[:6]}"
        token, _ = generate_expensive_call_token(
            task_id=task_id,
            target_model="deepseek/deepseek-chat",
            user_id=settings.jarvis_user_id,
        )

        # Attacker tries to use this token for claude-3-7-sonnet
        valid, reason = verify_expensive_call_token(
            token=token,
            task_id=task_id,
            target_model="anthropic/claude-3-7-sonnet",
            user_id=settings.jarvis_user_id,
        )
        assert valid is False
        assert "Invalid cryptographic signature" in reason

    def test_cross_task_token_substitution_fails_verification(self):
        """A valid expensive token issued for task A cannot authorize task B."""
        token, _ = generate_expensive_call_token(
            task_id="task_original",
            target_model="claude-3-7-sonnet",
            user_id=settings.jarvis_user_id,
        )

        valid, reason = verify_expensive_call_token(
            token=token,
            task_id="task_hijacked",
            target_model="claude-3-7-sonnet",
            user_id=settings.jarvis_user_id,
        )
        assert valid is False
        assert "Invalid cryptographic signature" in reason

    def test_cross_user_token_substitution_fails_verification(self):
        """A valid expensive token issued for admin cannot be verified for another user."""
        token, _ = generate_expensive_call_token(
            task_id="task_user_test",
            target_model="claude-3-7-sonnet",
            user_id="authorized_admin",
        )

        valid, reason = verify_expensive_call_token(
            token=token,
            task_id="task_user_test",
            target_model="claude-3-7-sonnet",
            user_id="impostor",
        )
        assert valid is False
        assert "Invalid cryptographic signature" in reason

    @pytest.mark.parametrize("malformed", [
        "",
        None,
        12345,
        "exp_hmac_",
        "exp_hmac_nosig",
        "exp_hmac_sig_without_dot",
        "exp_hmac_sig.notanumber",
        "exp_hmac_" + "a" * 64 + ".9999999999999999999999999999999999999999",
    ])
    def test_malformed_token_fails_gracefully(self, malformed):
        """Malformed or non-string tokens return (False, reason) without unhandled exceptions."""
        valid, reason = verify_expensive_call_token(
            token=malformed,
            task_id="tsk_malformed",
            target_model="claude-3-7-sonnet",
        )
        assert valid is False


# ==============================================================================
# 4. CROSS-SYSTEM CRYPTOGRAPHIC CONFINEMENT & RACE RESILIENCE
# ==============================================================================

class TestCrossSystemConfinement:
    """Stress testing cross-domain token contamination and concurrent resolution race."""

    def test_expensive_token_cannot_bypass_policy_gate(self):
        """An expensive call HMAC token cannot be used to execute a privileged power."""
        task_id = f"tsk_confine_{uuid.uuid4().hex[:6]}"
        expensive_token, _ = generate_expensive_call_token(
            task_id=task_id, target_model="claude-3-7-sonnet", user_id=settings.jarvis_user_id
        )

        allowed, msg, _ = policy_gate.evaluate_execution(
            task_id=task_id,
            power_id="delete_file",
            privilege_level=5,
            payload={"path": "/critical/file.txt"},
            approval_token=expensive_token,
            user_id=settings.jarvis_user_id,
        )
        assert allowed is False
        assert "APPROVAL FAILED" in msg

    def test_policy_gate_token_cannot_authorize_expensive_call(self):
        """A policy gate execution token cannot be accepted as an expensive call token."""
        task_id = f"tsk_confine_pg_{uuid.uuid4().hex[:6]}"
        policy_token, _ = policy_gate.generate_approval_token(
            task_id=task_id, power_id="delete_file", payload_hash="hash123", user_id=settings.jarvis_user_id
        )

        valid, reason = verify_expensive_call_token(
            token=policy_token,
            task_id=task_id,
            target_model="claude-3-7-sonnet",
            user_id=settings.jarvis_user_id,
        )
        assert valid is False
        assert "missing exp_hmac_ prefix" in reason

    def test_concurrent_resolution_of_same_pending_approval(self):
        """Concurrent resolution requests to /api/v1/approvals/{task_id}/resolve succeed safely."""
        task_id = f"tsk_race_resolve_{uuid.uuid4().hex[:6]}"
        policy_gate.evaluate_execution(
            task_id=task_id, power_id="drop_table", privilege_level=5, payload={"table": "users"}
        )

        results = []

        def _resolve():
            return client.post(
                f"/api/v1/approvals/{task_id}/resolve",
                json={"task_id": task_id, "approved": True, "user_id": settings.jarvis_user_id},
                headers={"X-Admin-Token": settings.jarvis_secret_key},
            )

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(_resolve) for _ in range(5)]
            for f in futures:
                results.append(f.result())

        # All concurrent approvals of this pending request should return 200 with matching approval_token
        tokens = set()
        for res in results:
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "APPROVED"
            tokens.add(data["approval_token"])

        # Exactly 1 consistent token issued
        assert len(tokens) == 1, f"Expected 1 consistent token, got {len(tokens)}"


# ==============================================================================
# 5. ADVANCED ADVERSARIAL CHALLENGES: Prefixed Routes, Injections & Method Fuzzing
# ==============================================================================

class TestAdvancedAdversarialVectors:
    """Rigorous empirical penetration tests for prefixed routes, injection, and method attacks."""

    # 1. Prefixed Route: /api/v1/tasks/{task_id}/approve
    def test_prefixed_tasks_approve_unauthenticated_fails_closed(self):
        """POST /api/v1/tasks/{task_id}/approve without auth must return 401."""
        res = client.post(
            "/api/v1/tasks/tsk_prefix_unauth/approve",
            json={"approved": True, "notes": "unauthorized attempt"},
        )
        assert res.status_code == 401

    def test_prefixed_tasks_approve_forged_token_fails_closed(self):
        """POST /api/v1/tasks/{task_id}/approve with bad auth must return 403."""
        res = client.post(
            "/api/v1/tasks/tsk_prefix_forged/approve",
            json={"approved": True, "notes": "forged attempt"},
            headers={"X-Admin-Token": "bad_token_123"},
        )
        assert res.status_code == 403

    def test_prefixed_tasks_approve_user_impersonation_fails_closed(self):
        """POST /api/v1/tasks/{task_id}/approve with user impersonation must return 403."""
        res = client.post(
            "/api/v1/tasks/tsk_prefix_impersonate/approve",
            json={"approved": True, "notes": "impersonated", "user_id": "malicious_user"},
            headers={"X-Admin-Token": settings.jarvis_secret_key},
        )
        assert res.status_code == 403

    def test_prefixed_tasks_approve_authenticated_succeeds(self):
        """POST /api/v1/tasks/{task_id}/approve with valid admin credentials succeeds."""
        task_id = f"tsk_prefix_auth_{uuid.uuid4().hex[:6]}"
        policy_gate.evaluate_execution(
            task_id=task_id, power_id="delete_file", privilege_level=5, payload={"path": "/tmp/test"}
        )

        res = client.post(
            f"/api/v1/tasks/{task_id}/approve",
            json={"approved": True, "notes": "authorized via prefix", "user_id": settings.jarvis_user_id},
            headers={"X-Admin-Token": settings.jarvis_secret_key},
        )
        assert res.status_code == 200
        assert res.json()["status"] == "APPROVED"
        assert "approval_token" in res.json()

    # 2. Empty / Malformed Auth Credentials
    @pytest.mark.parametrize("header", [
        {"Authorization": "Basic dXNlcjpwYXNz"},
        {"Authorization": "Digest username=admin"},
        {"Authorization": "Bearer"},
        {"Authorization": "Bearer    "},
        {"Authorization": ""},
    ])
    def test_empty_or_non_bearer_auth_headers_fail_closed(self, header):
        """Non-bearer or malformed Authorization headers fail closed with 401."""
        res = client.post(
            "/api/v1/approvals/tsk_test/resolve",
            json={"task_id": "tsk_test", "approved": True},
            headers=header,
        )
        assert res.status_code == 401

    # 3. SQL Injection & Format String Payloads in Notes and User IDs
    @pytest.mark.parametrize("sqli_payload", [
        "' OR '1'='1",
        "admin'--",
        "'; DROP TABLE tasks; --",
        "UNION SELECT 1, 'admin', 'pass' --",
        "%s%s%s%s%n",
        "${7*7}",
        "{{7*7}}",
        "<!--#exec cmd=\"ls\"-->",
    ])
    def test_sqli_and_format_payloads_in_task_approve_fail_closed(self, sqli_payload):
        """SQLi / format payloads in req.user_id fail closed with 403 (or 404 for unknown task)."""
        res = client.post(
            "/tasks/tsk_sqli_test/approve",
            json={"approved": True, "notes": sqli_payload, "user_id": sqli_payload},
            headers={"X-Admin-Token": settings.jarvis_secret_key},
        )
        # Should be rejected because sqli_payload != admin_user (403), never 500
        assert res.status_code == 403
        assert "does not match authenticated admin" in res.json().get("detail", "")

    # 4. HTTP Method Fuzzing (Fail-Closed 405)
    @pytest.mark.parametrize("method,endpoint", [
        ("GET", "/api/v1/approvals/tsk_fuzz/resolve"),
        ("PUT", "/api/v1/approvals/tsk_fuzz/resolve"),
        ("DELETE", "/api/v1/approvals/tsk_fuzz/resolve"),
        ("PATCH", "/api/v1/approvals/tsk_fuzz/resolve"),
        ("GET", "/model/approve-expensive-call"),
        ("PUT", "/model/approve-expensive-call"),
        ("DELETE", "/model/approve-expensive-call"),
        ("PATCH", "/model/approve-expensive-call"),
        ("PUT", "/tasks/tsk_fuzz/approve"),
        ("DELETE", "/tasks/tsk_fuzz/approve"),
        ("PATCH", "/tasks/tsk_fuzz/approve"),
    ])
    def test_unsupported_http_methods_fail_closed(self, method, endpoint):
        """Invoking unapproved HTTP methods against endpoints yields 405 Method Not Allowed."""
        res = client.request(method, endpoint)
        assert res.status_code == 405

    # 5. Delimiter Injection Attack in Expensive Call Token
    def test_expensive_call_token_delimiter_injection_rejected(self):
        """Attacker attempting colon delimiter injection cannot forge authorization for another model."""
        task_id = "tsk_legit"
        injected_target = "gpt-4o:expensive_model:9999999999"

        # Generate token with colon in model string
        token, expiry = generate_expensive_call_token(
            task_id=task_id, target_model=injected_target, user_id=settings.jarvis_user_id
        )

        # Verification for the hijacked model 'expensive_model' must FAIL
        valid, reason = verify_expensive_call_token(
            token=token,
            task_id=task_id,
            target_model="expensive_model",
            user_id=settings.jarvis_user_id,
        )
        assert valid is False
        assert "Invalid cryptographic signature" in reason

    # 6. Expensive Call User Signature Spoofing in Body
    def test_expensive_call_user_signature_in_body_cannot_bypass_admin_user(self):
        """Passing user_signature='attacker' in body does not override admin_user identity."""
        task_id = f"tsk_sig_spoof_{uuid.uuid4().hex[:6]}"
        res = client.post(
            "/model/approve-expensive-call",
            json={
                "task_id": task_id,
                "target_model": "claude-3-7-sonnet",
                "approved": True,
                "user_signature": "attacker",
            },
            headers={"X-Admin-Token": settings.jarvis_secret_key},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["authorized_by"] == settings.jarvis_user_id
        # Token is bound to authenticated admin_user, NOT the attacker string in body
        valid, _ = verify_expensive_call_token(
            token=data["token"],
            task_id=task_id,
            target_model="claude-3-7-sonnet",
            user_id=settings.jarvis_user_id,
        )
        assert valid is True
        valid_attacker, _ = verify_expensive_call_token(
            token=data["token"],
            task_id=task_id,
            target_model="claude-3-7-sonnet",
            user_id="attacker",
        )
        assert valid_attacker is False

