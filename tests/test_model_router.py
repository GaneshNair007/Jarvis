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
        attached_context="Private financial transactions and salary info.",
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
        attached_context="Screen capture buffer with private browser tabs",
    )
    decision = model_router.route(req)
    assert decision.tier == "TIER_1_LOCAL"
    assert decision.provider == "ollama"


def test_sensitive_data_redacted_before_routing():
    """Requirement 4: Sensitive credentials and tokens are redacted."""
    raw_context = "My API key is sk-1234567890abcdef1234567890abcdef and password is 'SecretPassword123'."
    req = RoutingRequest(
        user_intent="Analyze this snippet", task_type="research", sensitivity_level="low", attached_context=raw_context
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
            attached_context="Very large text context " * 500,
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


def test_greeting_is_conversational_not_a_deterministic_bypass():
    decision = model_router.route(RoutingRequest(user_intent="Hey Jarvis"))
    assert decision.tier != "BYPASS"


def test_workspace_shortcuts_are_deterministic_commands():
    for command in ["/brief", "/due", "/quest", "/capture fact User prefers local-first AI"]:
        assert model_router.is_instant_command(command)


def test_model_status_reports_ollama_reachability(monkeypatch):
    monkeypatch.setattr(model_router, "check_ollama_readiness", lambda use_cache=False: False)
    status = model_router.get_status()
    assert status["tier_1_local"]["reachable"] is False
    assert status["tier_1_local"]["status"] == "unavailable"


def test_natural_language_opportunity_requests_are_routed_for_live_search():
    for prompt in [
        "find internships",
        "search upcoming hackathons",
        "show me AI jobs",
        "get me scholarships",
    ]:
        assert model_router.is_instant_command(prompt)


def test_model_router_executes_selected_tool_and_returns_final_answer(monkeypatch):
    import json
    import sys
    from types import SimpleNamespace
    from jarvis.core.model_router import ModelRouter, RoutingDecision

    router = ModelRouter()
    monkeypatch.setattr(router, "check_ollama_readiness", lambda use_cache=True: True)
    monkeypatch.setattr(
        "jarvis.security.ten_layer_shield.jarvis_security_suite.sanitize_outbound_prompt",
        lambda value: value,
    )

    from jarvis.core import power_binder as power_binder_module

    offered_tools = [
        {
            "type": "function",
            "function": {
                "name": "browser_search",
                "description": "Search the live web",
                "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
            },
        }
    ]
    monkeypatch.setattr(
        power_binder_module.power_binder,
        "select_tools_for_query",
        lambda query, limit=5, max_privilege_level=1: offered_tools,
    )
    executed = []

    def fake_execute(name, arguments):
        executed.append((name, arguments))
        return {
            "success": True,
            "tool": name,
            "result": {
                "status": "completed",
                "results": [{"title": "Official hackathon page", "url": "https://example.org/hackathon"}],
            },
        }

    monkeypatch.setattr(power_binder_module.power_binder, "execute_tool", fake_execute)

    first_message = SimpleNamespace(
        content=None,
        tool_calls=[
            SimpleNamespace(
                id="call_001",
                function=SimpleNamespace(
                    name="browser_search",
                    arguments=json.dumps({"query": "AI hackathons India"}),
                ),
            )
        ],
    )
    final_message = SimpleNamespace(content="I found one official hackathon page.", tool_calls=None)
    responses = [
        SimpleNamespace(
            choices=[SimpleNamespace(message=first_message)],
            usage=SimpleNamespace(prompt_tokens=40, completion_tokens=8),
        ),
        SimpleNamespace(
            choices=[SimpleNamespace(message=final_message)],
            usage=SimpleNamespace(prompt_tokens=60, completion_tokens=15),
        ),
    ]
    calls = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        return responses.pop(0)

    fake_litellm = SimpleNamespace(
        completion=fake_completion,
        completion_cost=lambda completion_response: 0.0,
    )
    monkeypatch.setitem(sys.modules, "litellm", fake_litellm)

    decision = RoutingDecision(
        task_id="tool_task_001",
        tier="TIER_1_LOCAL",
        provider="ollama",
        selected_model="llama3.1",
        reason="Local model available",
        redacted_context="",
        redactions_made=[],
        estimated_cost_usd=0.0,
        requires_approval=False,
    )
    result = router.execute_inference(decision, "What are the latest AI hackathons in India?")

    assert result["status"] == "completed"
    assert result["reply"] == "I found one official hackathon page."
    assert result["tools_executed"] == 1
    assert result["tool_results"][0]["success"] is True
    assert executed == [("browser_search", {"query": "AI hackathons India"})]
    assert len(calls) == 2
    assert "tools" in calls[0]
    assert "tools" not in calls[1]
    assert calls[1]["messages"][-1]["role"] == "tool"


def test_offline_model_is_not_reported_as_success(monkeypatch):
    from jarvis.core.model_router import ModelRouter, RoutingDecision

    router = ModelRouter()
    monkeypatch.setattr(router, "check_ollama_readiness", lambda use_cache=True: False)
    monkeypatch.setattr(settings, "jarvis_env", "test")
    decision = RoutingDecision(
        task_id="offline_task_001",
        tier="TIER_1_LOCAL",
        provider="ollama",
        selected_model="llama3.1",
        reason="Local-first",
        redacted_context="",
        redactions_made=[],
        estimated_cost_usd=0.0,
        requires_approval=False,
    )
    result = router.execute_inference(decision, "Explain eigenvectors.")

    assert result["status"] == "unavailable"
    assert result["error"] == "LOCAL_MODEL_UNAVAILABLE"
    assert result["tokens_used"] == 0
    assert "No model inference was performed" in result["reply"]


def test_failed_tool_result_marks_inference_partial_failure(monkeypatch):
    import json
    import sys
    from types import SimpleNamespace
    from jarvis.core.model_router import ModelRouter, RoutingDecision

    router = ModelRouter()
    monkeypatch.setattr(router, "check_ollama_readiness", lambda use_cache=True: True)
    monkeypatch.setattr(
        "jarvis.security.ten_layer_shield.jarvis_security_suite.sanitize_outbound_prompt",
        lambda value: value,
    )
    from jarvis.core import power_binder as power_binder_module

    offered_tools = [
        {
            "type": "function",
            "function": {
                "name": "browser_search",
                "description": "Search",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            },
        }
    ]
    monkeypatch.setattr(
        power_binder_module.power_binder,
        "select_tools_for_query",
        lambda query, limit=5, max_privilege_level=1: offered_tools,
    )
    monkeypatch.setattr(
        power_binder_module.power_binder,
        "execute_tool",
        lambda name, arguments: {"success": False, "tool": name, "error": "SEARCH_PROVIDER_UNAVAILABLE"},
    )
    messages = [
        SimpleNamespace(
            content=None,
            tool_calls=[
                SimpleNamespace(
                    id="call_failed",
                    function=SimpleNamespace(
                        name="browser_search",
                        arguments=json.dumps({"query": "hackathons"}),
                    ),
                )
            ],
        ),
        SimpleNamespace(content="The search provider is unavailable.", tool_calls=None),
    ]
    responses = [
        SimpleNamespace(choices=[SimpleNamespace(message=messages[0])], usage=None),
        SimpleNamespace(choices=[SimpleNamespace(message=messages[1])], usage=None),
    ]
    monkeypatch.setitem(
        sys.modules,
        "litellm",
        SimpleNamespace(
            completion=lambda **_kwargs: responses.pop(0),
            completion_cost=lambda completion_response: 0.0,
        ),
    )
    decision = RoutingDecision(
        task_id="partial_tool_task",
        tier="TIER_1_LOCAL",
        provider="ollama",
        selected_model="llama3.1",
        reason="Local-first",
        redacted_context="",
        redactions_made=[],
        estimated_cost_usd=0.0,
        requires_approval=False,
    )

    result = router.execute_inference(decision, "Search the latest hackathons.")

    assert result["status"] == "partial_failure"
    assert result["error"] == "ONE_OR_MORE_TOOLS_FAILED"
    assert result["tools_executed"] == 0
