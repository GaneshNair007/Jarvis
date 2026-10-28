"""
JARVIS Phase 1 Integration Foundation Test Suite
Validates all 12 core requirements:
  1. Connection status
  2. Missing credentials (returns setup guide, never fake success)
  3. Invalid credentials handling
  4. Permission denial & disabled state enforcement
  5. Approval requirement & frozen content hash
  6. Rate limiting enforcement
  7. Retry policy with exponential backoff
  8. Dry-run mode without external mutations
  9. Audit logging of all actions
 10. Kill switch immediate halt
 11. Sensitive-data redaction in credential manager
 12. Dangerous action blocking & approval verification
"""

import pytest
import time
from fastapi.testclient import TestClient

from jarvis.api.server import app
from jarvis.core.policy_gate import policy_gate
from integrations import (
    integration_registry,
    credential_manager,
    rate_limiter,
    default_retry_policy,
    RetryPolicy,
    IntegrationStatus,
)

@pytest.fixture
def client():
    # Ensure kill switch is reset before each test
    policy_gate.reset_kill_switch()
    integration_registry.reset_all_kill_switches()
    return TestClient(app)

# 1. Connection status
def test_connection_status(client):
    # GET /integrations
    res = client.get("/integrations")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 2
    iids = [i["integration_id"] for i in data["integrations"]]
    assert "system_diagnostics" in iids
    assert "github" in iids

    # GET /integrations/system_diagnostics
    sys_res = client.get("/integrations/system_diagnostics")
    assert sys_res.status_code == 200
    assert sys_res.json()["display_name"] == "System Diagnostics & Telemetry"

    # Disconnect & Connect
    dis_res = client.post("/integrations/system_diagnostics/disconnect")
    assert dis_res.status_code == 200
    assert dis_res.json()["connected"] is False

    con_res = client.post("/integrations/system_diagnostics/connect")
    assert con_res.status_code == 200
    assert con_res.json()["connected"] is True

# 2. Missing credentials returns setup guide, never fake success
def test_missing_credentials(client):
    # Ensure GitHub credential is not present
    credential_manager.clear_override("GITHUB_PERSONAL_ACCESS_TOKEN")
    gh = integration_registry.get("github")
    gh.enable()

    # Attempt execution without credentials
    res = client.post("/integrations/github/powers/github.list_repos/execute", json={
        "params": {}
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "UNCONFIGURED"
    assert "GITHUB_PERSONAL_ACCESS_TOKEN" in data["missing_credentials"]
    assert "setup_guide" in data
    assert "https://github.com/settings/tokens" in data["setup_guide"]["setup_url"]

    # Health check reflects UNCONFIGURED
    health_res = client.get("/integrations/github/health")
    assert health_res.status_code == 200
    assert health_res.json()["status"] == IntegrationStatus.UNCONFIGURED.value

# 3. Invalid credentials handling
def test_invalid_credentials():
    is_valid, missing = credential_manager.validate_credentials(["NON_EXISTENT_SECRET_XYZ"])
    assert is_valid is False
    assert "NON_EXISTENT_SECRET_XYZ" in missing

# 4. Permission denial & disabled state enforcement
def test_permission_denial_when_disabled(client):
    sys_integ = integration_registry.get("system_diagnostics")
    sys_integ.disable()

    # Attempt to execute power while integration is disabled
    res = client.post("/integrations/system_diagnostics/powers/system.health_probe/execute", json={
        "params": {}
    })
    assert res.status_code == 200
    assert res.json()["status"] == "DISABLED"
    assert "disabled" in res.json()["reason"]

    # Enable and verify it succeeds
    enable_res = client.post("/integrations/system_diagnostics/enable")
    assert enable_res.status_code == 200
    assert enable_res.json()["enabled"] is True

# 5. Approval requirement & frozen content hash
def test_approval_requirement_and_frozen_hash(client):
    sys_integ = integration_registry.get("system_diagnostics")
    sys_integ.enable()

    # Tier 2 action: system.clear_temp_cache requires human approval
    res = client.post("/integrations/system_diagnostics/powers/system.clear_temp_cache/execute", json={
        "params": {"target_dir": "scratch/temp_cache"}
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "AWAITING_APPROVAL"
    assert data["approval_required"] is True
    assert "approval_id" in data
    assert "content_hash" in data
    assert len(data["content_hash"]) == 64 # SHA-256 digest

    # Retrieve the approval token registered for this approval request
    approval_id = data["approval_id"]
    token = policy_gate.pending_approvals[approval_id]["token"]

    # Re-execute with approval token
    approved_res = client.post("/integrations/system_diagnostics/powers/system.clear_temp_cache/execute", json={
        "params": {"target_dir": "scratch/temp_cache"},
        "approval_token": token
    })
    assert approved_res.status_code == 200
    app_data = approved_res.json()
    assert app_data["status"] == "SUCCESS"
    assert app_data["result"]["action"] == "purged_scratch_cache"

# 6. Rate limiting enforcement
def test_rate_limiting():
    test_id = "test_rate_limiter_integ"
    rate_limiter.set_limit(test_id, requests_per_minute=2)
    rate_limiter.reset(test_id)

    # Call 1: Allowed
    assert rate_limiter.record_call(test_id) is True
    # Call 2: Allowed
    assert rate_limiter.record_call(test_id) is True
    # Call 3: Blocked by rate limiter
    assert rate_limiter.record_call(test_id) is False
    allowed, wait_sec = rate_limiter.check_rate_limit(test_id)
    assert allowed is False
    assert wait_sec > 0.0

    # Reset
    rate_limiter.reset(test_id)
    assert rate_limiter.record_call(test_id) is True

# 7. Retry policy with exponential backoff
def test_retry_policy():
    call_counts = {"count": 0}

    def flaky_func():
        call_counts["count"] += 1
        if call_counts["count"] < 3:
            raise ConnectionResetError("Transient network drop")
        return "success"

    policy = RetryPolicy(max_retries=3, initial_delay_sec=0.01, jitter=False)
    result = policy.execute(flaky_func)
    assert result == "success"
    assert call_counts["count"] == 3

    # Permanent error must NOT be retried
    def unauth_func():
        raise PermissionError("Unauthorized policy_halt")

    with pytest.raises(PermissionError):
        policy.execute(unauth_func)

# 8. Dry-run mode without external mutations
def test_dry_run_mode(client):
    sys_integ = integration_registry.get("system_diagnostics")
    sys_integ.enable()

    res = client.post("/integrations/system_diagnostics/powers/system.clear_temp_cache/dry-run", json={
        "params": {"target_dir": "scratch/logs"}
    })
    assert res.status_code == 200
    plan = res.json()
    assert plan["status"] == "DRY_RUN_READY"
    assert plan["power_id"] == "system.clear_temp_cache"
    assert plan["tier"] == 2
    assert plan["approval_required"] is True
    assert "content_hash" in plan
    assert "simulated_params" in plan

# 9. Audit logging of all actions
def test_audit_logging(client):
    sys_integ = integration_registry.get("system_diagnostics")
    sys_integ.enable()

    # Execute health probe
    client.post("/integrations/system_diagnostics/powers/system.health_probe/execute", json={
        "params": {}
    })

    # Retrieve audit events for this integration
    audit_res = client.get("/integrations/system_diagnostics/audit")
    assert audit_res.status_code == 200
    audit_data = audit_res.json()
    assert audit_data["total_events"] > 0
    actions = [e["action"] for e in audit_data["events"]]
    assert any("EXECUTE_system.health_probe" in a for a in actions)

# 10. Kill switch immediate halt
def test_kill_switch(client):
    sys_integ = integration_registry.get("system_diagnostics")
    sys_integ.enable()

    # Trip integration kill switch
    sys_integ.trip_kill_switch(reason="Test Emergency Operator Command")
    assert sys_integ.kill_switched is True

    # Any power execution must be blocked immediately
    res = client.post("/integrations/system_diagnostics/powers/system.health_probe/execute", json={
        "params": {}
    })
    assert res.status_code == 200
    assert res.json()["status"] == "BLOCKED"
    assert "Kill switch is actively triggered" in res.json()["reason"]

    # Reset kill switch
    sys_integ.reset_kill_switch()
    assert sys_integ.kill_switched is False

# 11. Sensitive-data redaction in credential manager
def test_sensitive_data_redaction():
    masked = credential_manager.mask_secret("ghp_9876543210abcdefghij")
    assert masked == "ghp****ghij"
    assert "9876543210" not in masked

    raw_dict = {
        "user": "ganesh",
        "api_key": "secret_key_12345678",
        "nested": {"token": "my_bearer_token_9999"}
    }
    redacted = credential_manager.redact_dict(raw_dict)
    assert redacted["user"] == "ganesh"
    assert "12345678" not in redacted["api_key"]
    assert "bearer_token" not in redacted["nested"]["token"]

# 12. Dangerous action blocking & approval verification
def test_dangerous_action_blocking(client):
    # Setup temporary credentials for GitHub
    credential_manager.set_override("GITHUB_PERSONAL_ACCESS_TOKEN", "ghp_test_token_12345678")
    gh = integration_registry.get("github")
    gh.enable()
    gh.connect()

    # Attempting to execute Tier 3 merge_pr without approval
    res = client.post("/integrations/github/powers/github.merge_pr/execute", json={
        "params": {"pr_number": 101}
    })
    assert res.status_code == 200
    assert res.json()["status"] == "AWAITING_APPROVAL"
    assert res.json()["approval_required"] is True

    # Supplying a forged/invalid token
    invalid_res = client.post("/integrations/github/powers/github.merge_pr/execute", json={
        "params": {"pr_number": 101},
        "approval_token": "forged_token_xyz"
    })
    assert invalid_res.status_code == 200
    assert invalid_res.json()["status"] == "APPROVAL_INVALID"

    credential_manager.clear_override("GITHUB_PERSONAL_ACCESS_TOKEN")
