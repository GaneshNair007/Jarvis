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
    assert res.success is True
    assert res.fabricated is False
    assert len(res.evidence) >= 1
    assert res.evidence[0].source == "switch_bridge:send_room_message"
    assert res.data["status"] == "DISPATCHED"
    assert res.data["room_id"] == "dev-war-room"


def test_switch_request_room_approval_never_leaks_token():
    res = switch_integration.request_room_approval(
        task_id="task_deploy_prod_01",
        action_summary="Deploy production container to AWS ECS",
        power_id="deploy_aws_ecs",
        privilege_level=4,
    )
    assert res.success is True
    assert res.fabricated is False
    assert "token" not in res.data  # Critical security invariant
    assert res.data["status"] == "AWAITING_ROOM_APPROVAL"
    assert "approval_id" in res.data


def test_switch_broadcast_failover_event():
    res = switch_integration.broadcast_failover_event(
        primary_model="anthropic/claude-3.5-sonnet",
        fallback_model="deepseek/deepseek-r1",
        reason="HTTP 429 Rate Limit - Context preserved and hot-swapped",
    )
    assert res.success is True
    assert res.fabricated is False
    assert res.data["status"] == "FAILOVER_BROADCAST_COMPLETE"
    assert "HYDRA FAILOVER" in res.data["summary"]
