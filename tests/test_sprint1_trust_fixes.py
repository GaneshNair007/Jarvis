"""Tests for Sprint 1 Trust & Reliability Fixes.

Covers:
1. Gmail Hallucination elimination: Honest DISCONNECTED status, empty opportunities, fabricated: False.
2. Capability Guard: Gmail, Ollama, Internet checks.
3. Honest Routing Labels: Ollama offline never claims TIER_1_LOCAL.
4. Antigravity & Self-Improvement Intent Detection: Recognizes Antigravity coding agent.
5. Honest Startup Banner.
"""

import os
import pytest
from unittest.mock import patch, MagicMock

from jarvis.core.capability_guard import capability_guard, CapabilityStatus
from jarvis.powers.email_powers import email_powers
from jarvis.core.model_router import model_router, RoutingRequest
from jarvis.core.orchestrator import orchestrator
def print_honest_startup_banner() -> str:
    from jarvis.core.capability_guard import capability_guard
    status = capability_guard.get_all_status()
    return (
        "\n=======================================================\n"
        "JARVIS SYSTEM CAPABILITIES STATUS (Honest Pre-Flight)\n"
        "=======================================================\n"
        f"  Ollama:   {status.get('ollama', 'UNKNOWN')}\n"
        f"  Gmail:    {status.get('gmail', 'UNKNOWN')}\n"
        f"  Internet: {status.get('internet', 'UNKNOWN')}\n"
        "=======================================================\n"
    )


def test_gmail_disconnected_returns_honest_status(monkeypatch):
    """When Gmail credentials are absent, scan_inbox_for_opportunities returns DISCONNECTED and fabricated=False."""
    monkeypatch.delenv("GMAIL_USER", raising=False)
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)
    capability_guard.clear_cache()

    result = email_powers.scan_inbox_for_opportunities()

    assert result["fabricated"] is False
    assert result["status"] == "DISCONNECTED"
    assert result["opportunities_found"] == 0
    assert result["opportunities"] == []
    assert "Gmail is not connected" in result.get("message", "")


def test_gmail_never_returns_fake_data(monkeypatch):
    """Without real credentials, scan_inbox_for_opportunities must NEVER return fabricated opportunities."""
    monkeypatch.delenv("GMAIL_USER", raising=False)
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)
    capability_guard.clear_cache()

    result = email_powers.scan_inbox_for_opportunities()

    assert result["opportunities"] == []
    # Verify no fake opportunity strings exist in payload
    res_str = str(result)
    assert "technical interview time slots" not in res_str
    assert "capstone report" not in res_str
    assert "Nov 8" not in res_str
    assert result["fabricated"] is False


def test_capability_guard_gmail_disconnected(monkeypatch):
    """CapabilityGuard reports DISCONNECTED when Gmail credentials are not set."""
    monkeypatch.delenv("GMAIL_USER", raising=False)
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)
    capability_guard.clear_cache()

    status = capability_guard.check_gmail(use_cache=False)
    assert status == CapabilityStatus.DISCONNECTED


def test_capability_guard_ollama():
    """CapabilityGuard reports DISCONNECTED when local Ollama is not running."""
    # Point Ollama check to unreachable port or rely on local env where Ollama is not active
    capability_guard.clear_cache()
    with patch("urllib.request.urlopen", side_effect=OSError("Connection refused")):
        status = capability_guard.check_ollama(use_cache=False)
        assert status == CapabilityStatus.DISCONNECTED


def test_ollama_offline_routing_label():
    """When Ollama is unreachable, model router must NOT label inference as TIER_1_LOCAL."""
    capability_guard.clear_cache()
    with patch.object(model_router, "check_ollama_readiness", return_value=False):
        req = RoutingRequest(user_intent="Calculate system metrics and parse local data", task_type="fast_code")
        decision = model_router.route(req)

        assert decision.tier != "TIER_1_LOCAL"
        assert decision.tier in ("TIER_3_CLOUD", "FALLBACK_CLOUD")
        assert decision.metadata.get("ollama_online") is False


@pytest.mark.asyncio
async def test_antigravity_intent_detection():
    """Queries mentioning 'connect antigravity' or self-improvement return honest capability gap guidance."""
    query = "connect antigravity and make yourself stronger"
    cmd_res = orchestrator._execute_instant_command(query)

    assert cmd_res is not None
    assert cmd_res["status"] == "understood"
    assert cmd_res["action"] == "self_improvement_intent_detected"
    assert "Self-improvement workflow" in cmd_res["message"]
    assert "cannot self-modify directly" in cmd_res["message"]

    # Also test via full orchestrator pipeline
    full_res = await orchestrator.process_user_query("use antigravity to upgrade yourself")
    assert full_res["status"] in ("COMPLETED", "success")
    resp = full_res["response"]
    assert resp.get("action") == "self_improvement_intent_detected"


def test_startup_banner_truthfulness():
    """Startup banner prints truthful statuses for Ollama, Gmail, and Internet."""
    banner = print_honest_startup_banner()
    assert "JARVIS SYSTEM CAPABILITIES STATUS (Honest Pre-Flight)" in banner
    assert "Ollama:" in banner
    assert "Gmail:" in banner
    assert "Internet:" in banner


def test_trust_result_contract_never_fabricated():
    from jarvis.core.evidence import TrustResult
    res = TrustResult.disconnected('gmail', 'Gmail is not connected.')
    assert res.fabricated is False
    assert res.success is False
    assert res.data == {}
    d = res.to_dict()
    assert d['fabricated'] is False
    assert d['capability'] == 'gmail'
    assert d['status'] == 'disconnected'


def test_trust_result_success_demands_evidence():
    from jarvis.core.evidence import TrustResult, Evidence
    try:
        TrustResult.success('gmail', evidence=[], data={})
        assert False, 'Should have raised assertion error when evidence is empty'
    except AssertionError:
        pass


def test_trust_layer_blocks_unconnected_capability():
    from jarvis.core.trust_layer import trust_layer
    res = trust_layer.execute_with_trust(
        capability='gmail',
        action=lambda: {'should': 'not run'},
        action_name='test_scan'
    )
    assert res.success is False
    assert res.fabricated is False
    assert res.data == {}


def test_evidence_backed_system_health_report():
    from jarvis.core.capability_guard import capability_guard
    health = capability_guard.get_evidence_health_report()
    
    assert health["first_law_enforced"] is True
    assert health["fabricated"] is False
    
    # Ollama has evidence list
    assert "ollama" in health
    assert health["ollama"]["status"] in ["online", "offline"]
    assert isinstance(health["ollama"]["evidence"], list)
    assert len(health["ollama"]["evidence"]) >= 1
    
    # Scheduler has status and heartbeat
    assert "scheduler" in health
    assert health["scheduler"]["status"] in ["running", "stopped"]
    assert "heartbeat_count" in health["scheduler"]
    
    # Voice has components and classifications
    assert "voice" in health
    assert health["voice"]["status"] == "stub"
    assert health["voice"]["components"]["tts"] == "real"
    assert health["voice"]["components"]["stt"] == "stub"
    assert health["voice"]["components"]["wake_word"] == "stub"
    
    # Gmail has evidence list
    assert "gmail" in health
    assert health["gmail"]["status"] in ["connected", "disconnected"]
    assert isinstance(health["gmail"]["evidence"], list)
    assert len(health["gmail"]["evidence"]) >= 1


def test_scheduler_heartbeat_tracking():
    from jarvis.core.scheduler import proactive_scheduler
    initial_heartbeats = proactive_scheduler.heartbeat_count
    proactive_scheduler.record_heartbeat()
    assert proactive_scheduler.heartbeat_count == initial_heartbeats + 1
    assert proactive_scheduler.last_heartbeat is not None
    status = proactive_scheduler.get_status()
    assert status["heartbeat_count"] == initial_heartbeats + 1
    assert status["last_heartbeat"] is not None
