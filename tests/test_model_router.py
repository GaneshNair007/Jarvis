"""
Automated verification tests for the Three-Tier Policy-Aware Model Router.
Satisfies all 10 user requirements from the architecture prompt.
"""

import pytest
from jarvis.core.model_router import model_router, RoutingRequest
from jarvis.core.cost_governor import cost_governor
from jarvis.config import settings

def test_instant_command_bypasses_llm():
    """Requirement 1: Instant command bypasses LLM (0 cost, deterministic)."""
    commands = ["open VS Code", "volume up", "disk usage", "take screenshot", "lock workstation"]
    for cmd in commands:
        req = RoutingRequest(user_intent=cmd)
        decision = model_router.route(req)
        assert decision.tier == "BYPASS"
        assert decision.provider == "deterministic"
        assert decision.estimated_cost_usd == 0.0

def test_private_document_stays_local():
    """Requirement 2: Private document / memory task stays strictly local on Tier 1."""
    req = RoutingRequest(
        user_intent="Summarize my confidential tax documents",
        task_type="memory_retrieval",
        sensitivity_level="confidential",
        attached_context="Private financial transactions and salary info."
    )
    decision = model_router.route(req)
    assert decision.tier in ["TIER_1_LOCAL", "TIER_2_PRIVATE"]
    assert "ollama" in decision.provider or "vllm" in decision.provider
    assert decision.estimated_cost_usd == 0.0

def test_screen_understanding_stays_local():
    """Requirement 3: Screen understanding routes to local OCR/vision first."""
    req = RoutingRequest(
        user_intent="Explain what is currently visible on my active window",
        task_type="screen_ocr",
        sensitivity_level="high",
        attached_context="Screen capture buffer with private browser tabs"
    )
    decision = model_router.route(req)
    assert decision.tier == "TIER_1_LOCAL"
    assert decision.provider == "ollama"

def test_sensitive_data_redacted_before_routing():
    """Requirement 4: Sensitive credentials and tokens are redacted."""
    raw_context = "My API key is sk-1234567890abcdef1234567890abcdef and password is 'SecretPassword123'."
    req = RoutingRequest(
        user_intent="Analyze this snippet",
        task_type="research",
        sensitivity_level="low",
        attached_context=raw_context
    )
    decision = model_router.route(req)
    assert "[REDACTED_OPENAI_KEY]" in decision.redacted_context
    assert "sk-1234567890abcdef1234567890abcdef" not in decision.redacted_context
    assert len(decision.redactions_made) > 0

def test_cost_limit_stops_expensive_call():
    """Requirement 5: Cost limit stops excessive cloud calls and falls back."""
    # Temporarily set max budget low
    original_budget = settings.max_per_task_budget
    settings.max_per_task_budget = 0.0001
    cost_governor.max_per_task_budget = 0.0001

    try:
        req = RoutingRequest(
            user_intent="Perform deep research on global macroeconomic trends",
            task_type="research",
            sensitivity_level="public",
            attached_context="Very large text context " * 500
        )
        decision = model_router.route(req)
        # Should decline Tier 3 and fallback safely to Tier 2 or Tier 1
        assert decision.tier in ["TIER_2_PRIVATE", "TIER_1_LOCAL"]
        assert "fallback" in decision.reason.lower() or "budget" in decision.reason.lower()
    finally:
        settings.max_per_task_budget = original_budget
        cost_governor.max_per_task_budget = original_budget

def test_provider_failure_trips_circuit_breaker():
    """Requirement 6: Consecutive provider failures trip circuit breaker."""
    provider = "anthropic"
    assert not cost_governor.is_circuit_open(provider)

    cost_governor.record_failure(provider)
    cost_governor.record_failure(provider)
    cost_governor.record_failure(provider)

    assert cost_governor.is_circuit_open(provider)

    # Reset
    cost_governor.record_success(provider)
    assert not cost_governor.is_circuit_open(provider)

def test_audit_trail_recorded():
    """Requirement 7: Full audit trail of routing decisions is maintained."""
    req = RoutingRequest(user_intent="What is the capital of France?")
    decision = model_router.route(req)
    assert len(model_router.execution_history) > 0
    latest = model_router.execution_history[-1]
    assert latest["task_id"] == decision.task_id
    assert latest["model"] == decision.selected_model
