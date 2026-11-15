"""
Unit & Contract Tests for JARVIS Switch Integration
Enforces First Law compliance and multi-agent room messaging.
"""

import pytest
from integrations.switch.switch_integration import switch_integration


def test_switch_integration_metadata():
    assert switch_integration.integration_id == "switch_bridge"
    assert switch_integration.category == "collaboration"
    assert "Switch" in switch_integration.display_name


def test_switch_send_room_message_returns_trust_result():
    res = switch_integration.send_room_message(
        message="JARVIS Sovereign Conductor online via Switch protocol.",
        room_id="dev-war-room",
    )
    # First Law: Unimplemented network transports fail honestly (no fabricated success)
    assert res.success is False
    assert res.fabricated is False
    assert "error" in res.data
    assert "Switch transport is not implemented" in res.data["error"]


def test_switch_request_room_approval_never_leaks_token():
    res = switch_integration.request_room_approval(
        task_id="task_deploy_prod_01",
        action_summary="Deploy production container to AWS ECS",
        power_id="deploy_aws_ecs",
        privilege_level=4,
    )
    # First Law & Zero-Leak: fails honestly without fabricating delivery, never leaks token
    assert res.success is False
    assert res.fabricated is False
    assert "token" not in res.data  # Critical security invariant
    assert "Switch approval-card transport is not implemented" in res.data["error"]


def test_switch_broadcast_failover_event():
    res = switch_integration.broadcast_failover_event(
        primary_model="anthropic/claude-3.5-sonnet",
        fallback_model="deepseek/deepseek-r1",
        reason="HTTP 429 Rate Limit - Context preserved and hot-swapped",
    )
    # First Law: fails honestly without fabricating delivery
    assert res.success is False
    assert res.fabricated is False
    assert "error" in res.data
    assert "Switch failover-event transport is not implemented" in res.data["error"]

