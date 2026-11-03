"""
Automated verification tests for Milestone 4: Runtime Reliability & Event Loop Repairs.
Validates:
- FINDING-P0-01: Non-blocking async inference via asyncio.to_thread
- FINDING-P0-02: Purge of 'Sleeping Agent' mock and fail-closed TaskExecutor
- FINDING-P0-03: Genuine response key extraction in /v1/chat/completions
- FINDING-P0-04: Flat router dict response extraction and Mem0 error filtering in graph/nodes.py
- FINDING-P1-10: openrouter/ prefix for deepseek-chat on cloud fallback
- FINDING-P1-09: Conversational greeting triage for 'hello', 'hi', 'hey'
"""

import asyncio
import inspect
import threading
import time
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jarvis.core.model_router import model_router, RoutingRequest, RoutingDecision
from jarvis.core.orchestrator import orchestrator
from jarvis.core.task_executor import TaskExecutor
from jarvis.core.task_graph import TaskGraph, TaskNode, TaskStatus
from jarvis.core.power_registry import power_registry
from jarvis.api.routes_assistants import chat_completions, ChatCompletionRequest, ChatMessage
import graph.nodes as graph_nodes


# =====================================================================
# 1. FINDING-P0-01: Async Inference Execution (Non-blocking)
# =====================================================================

@pytest.mark.asyncio
async def test_async_inference_offloaded_to_thread():
    """Verify that orchestrator.process_user_query runs inference off the main asyncio thread."""
    worker_threads = []

    def mock_inference(decision: Any, prompt: str, **kwargs: Any) -> Dict[str, Any]:
        worker_threads.append(threading.current_thread())
        return {
            "status": "success",
            "reply": "Generated response from thread",
            "selected_model": getattr(decision, "selected_model", "test-model"),
            "tier": getattr(decision, "tier", "TIER_3_CLOUD"),
        }

    mock_decision = RoutingDecision(
        task_id="tsk_test_async",
        tier="TIER_3_CLOUD",
        provider="openrouter",
        selected_model="openrouter/deepseek/deepseek-chat",
        reason="Test cloud execution",
        redacted_context="",
        redactions_made=[],
        estimated_cost_usd=0.001,
        requires_approval=False,
    )

    with patch.object(orchestrator.router, "route", return_value=mock_decision), \
         patch.object(orchestrator.router, "execute_inference", side_effect=mock_inference), \
         patch.object(orchestrator.policy, "evaluate_execution", return_value=(True, "Approved", None)):

        main_thread = threading.current_thread()
        result = await orchestrator.process_user_query(
            query="Analyze quantum computing architecture",
            task_id="tsk_test_async",
        )

        assert result["status"] == "COMPLETED"
        assert result["response"]["reply"] == "Generated response from thread"
        assert len(worker_threads) == 1
        # Inference MUST run on a background worker thread, NOT the main event loop thread
        assert worker_threads[0] != main_thread


@pytest.mark.asyncio
async def test_event_loop_remains_unblocked_during_inference():
    """
    Simulate a slow inference (200ms) and assert that a concurrent coroutine on the
    event loop runs and finishes without waiting for the inference to complete.
    """
    concurrent_task_ran_at = None

    def slow_blocking_inference(decision: Any, prompt: str, **kwargs: Any) -> Dict[str, Any]:
        # Synchronous blocking sleep representing heavy network/compute inference
        time.sleep(0.2)
        return {
            "status": "success",
            "reply": "Finished slow inference",
            "selected_model": "test-model",
            "tier": "TIER_3_CLOUD",
        }

    async def lightweight_concurrent_task():
        nonlocal concurrent_task_ran_at
        await asyncio.sleep(0.02)  # fast async yield
        concurrent_task_ran_at = time.time()

    mock_decision = RoutingDecision(
        task_id="tsk_slow",
        tier="TIER_3_CLOUD",
        provider="openrouter",
        selected_model="openrouter/deepseek/deepseek-chat",
        reason="Slow inference test",
        redacted_context="",
        redactions_made=[],
        estimated_cost_usd=0.001,
        requires_approval=False,
    )

    start_time = time.time()
    with patch.object(orchestrator.router, "route", return_value=mock_decision), \
         patch.object(orchestrator.router, "execute_inference", side_effect=slow_blocking_inference), \
         patch.object(orchestrator.policy, "evaluate_execution", return_value=(True, "Approved", None)):

        inf_coro = orchestrator.process_user_query(query="Explain relativity", task_id="tsk_slow")
        light_coro = lightweight_concurrent_task()

        await asyncio.gather(inf_coro, light_coro)
        total_time = time.time() - start_time

        assert concurrent_task_ran_at is not None
        # The lightweight concurrent task must complete significantly BEFORE the slow inference finishes
        elapsed_to_concurrent = concurrent_task_ran_at - start_time
        assert elapsed_to_concurrent < 0.15, f"Concurrent task blocked by inference: took {elapsed_to_concurrent:.3f}s"
        assert total_time >= 0.2


# =====================================================================
# 2. FINDING-P0-02: Purge 'Sleeping Agent' & Enforce Fail-Closed Execution
# =====================================================================

@pytest.mark.asyncio
async def test_task_executor_fails_closed_when_tool_not_registered():
    """If task requires a tool not in power_registry, it must fail closed with NO_EXECUTABLE_HANDLER."""
    executor = TaskExecutor()
    task = TaskNode(
        task_id="tsk_missing_tool",
        parent_goal="goal_m4_test",
        name="Missing Tool Task",
        description="Task requiring missing tool",
        department="Engineering",
        tool_requirements=["nonexistent_secret_tool_404"],
    )

    result = await executor._default_agent_execution(task, {})

    assert result["status"] == "failed"
    assert result["reason"] == "NO_EXECUTABLE_HANDLER"
    assert "not registered" in result["error"]
    assert result["tools_used"] == []


@pytest.mark.asyncio
async def test_task_executor_fails_closed_when_tool_has_no_handler():
    """If tool is registered in power_registry without executable handler, fail closed."""
    executor = TaskExecutor()
    tool_name = "power_without_handler"
    power_registry.initial_powers[tool_name] = {
        "power_id": tool_name,
        "name": tool_name,
        "description": "Power without a handler",
        "category": "test",
        "handler": None,
    }

    try:
        task = TaskNode(
            task_id="tsk_nohandler",
            parent_goal="goal_m4_test",
            name="No Handler Task",
            description="Task with unexecutable tool",
            department="Engineering",
            tool_requirements=[tool_name],
        )

        result = await executor._default_agent_execution(task, {})

        assert result["status"] == "failed"
        assert result["reason"] == "NO_EXECUTABLE_HANDLER"
        assert "no executable handler" in result["error"]
    finally:
        power_registry.initial_powers.pop(tool_name, None)


@pytest.mark.asyncio
async def test_task_executor_fails_closed_when_inference_unavailable():
    """If no tools required and model inference is unavailable, fail closed."""
    executor = TaskExecutor()
    task = TaskNode(
        task_id="tsk_pure_reasoning",
        parent_goal="goal_m4_test",
        name="Reasoning Task",
        description="Reasoning without tools",
        department="Strategy",
        tool_requirements=[],
    )

    unavailable_inf = {
        "status": "unavailable",
        "error": "Ollama connection refused and cloud fallbacks uncontactable.",
        "reply": "AI Backend Unavailable",
    }

    with patch.object(model_router, "execute_inference", return_value=unavailable_inf):
        result = await executor._default_agent_execution(task, {})

        assert result["status"] == "failed"
        assert result["reason"] == "NO_EXECUTABLE_HANDLER"
        assert "uncontactable" in result["error"].lower() or "unavailable" in result["error"].lower()


@pytest.mark.asyncio
async def test_task_executor_succeeds_with_real_tool_execution():
    """When a registered tool executes cleanly, task succeeds with verifiable receipts."""
    executor = TaskExecutor()
    tool_name = "pwr_real_test_calculator"

    def calc_handler(task: TaskNode, context: Dict[str, Any]) -> Dict[str, Any]:
        return {"computed": 42}

    power_registry.initial_powers[tool_name] = {
        "power_id": tool_name,
        "name": tool_name,
        "description": "Calculator power",
        "category": "math",
        "handler": calc_handler,
    }

    try:
        task = TaskNode(
            task_id="tsk_calc",
            parent_goal="goal_m4_test",
            name="Compute Answer",
            description="Run calculation",
            department="Engineering",
            tool_requirements=[tool_name],
        )

        result = await executor._default_agent_execution(task, {})

        assert result["status"] == "success"
        assert tool_name in result["tools_used"]
        assert result["tool_results"][tool_name] == {"computed": 42}
        assert len(result["evidence"]) == 1
        assert result["evidence"][0]["action"] == "execute_power"
        assert result["fabricated"] is False
    finally:
        power_registry.initial_powers.pop(tool_name, None)


def test_task_executor_no_sleeping_agent_mock():
    """Verify source code of _default_agent_execution does NOT contain asyncio.sleep mock."""
    source = inspect.getsource(TaskExecutor._default_agent_execution)
    assert "asyncio.sleep(0.01)" not in source
    assert 'status": "success"' not in source.split("Step 1")[0]  # No early fake success


# =====================================================================
# 3. FINDING-P0-03: Drop-In OpenAI Route Response Key Extraction
# =====================================================================

@pytest.mark.asyncio
async def test_routes_assistants_openai_genuine_response():
    """Verify /v1/chat/completions extracts genuine model response from orchestrator."""
    fake_model_reply = "Quantum computing harnesses superposition and entanglement for computation."

    mock_orchestrator_res = {
        "task_id": "chat_12345",
        "status": "COMPLETED",
        "tier": "TIER_3_CLOUD",
        "response": {
            "status": "success",
            "reply": fake_model_reply,
            "model": "openrouter/deepseek/deepseek-chat",
        },
    }

    req = ChatCompletionRequest(
        model="gpt-4o",
        messages=[ChatMessage(role="user", content="Explain quantum computing in one sentence.")],
    )

    with patch.object(orchestrator, "process_user_query", new_callable=AsyncMock) as mock_process:
        mock_process.return_value = mock_orchestrator_res

        res = await chat_completions(req)

        assert res["choices"][0]["message"]["content"] == fake_model_reply
        assert res["choices"][0]["message"]["content"] != "JARVIS processed query."


@pytest.mark.asyncio
async def test_routes_assistants_openai_string_response_format():
    """Verify /v1/chat/completions works when response is a raw string or dict with message."""
    mock_orchestrator_res = {
        "task_id": "chat_67890",
        "status": "COMPLETED",
        "tier": "BYPASS",
        "response": {
            "type": "assistant_info",
            "message": "Hello Ganesh! I am JARVIS.",
        },
    }

    req = ChatCompletionRequest(
        model="gpt-4o",
        messages=[ChatMessage(role="user", content="hello")],
    )

    with patch.object(orchestrator, "process_user_query", new_callable=AsyncMock) as mock_process:
        mock_process.return_value = mock_orchestrator_res

        res = await chat_completions(req)

        assert res["choices"][0]["message"]["content"] == "Hello Ganesh! I am JARVIS."


# =====================================================================
# 4. FINDING-P0-04: LangGraph Flat Dict Parsing & Mem0 Error Exclusion
# =====================================================================

def test_graph_nodes_extracts_flat_router_dict():
    """Verify graph.nodes.model_router correctly extracts reply from flat router dict."""
    flat_router_result = {
        "task_id": "tsk_graph_1",
        "status": "success",
        "tier": "TIER_3_CLOUD",
        "model": "openrouter/deepseek/deepseek-chat",
        "reply": "This is a clean, unpacked response string from router.",
    }

    mock_decision = RoutingDecision(
        task_id="tsk_graph_1",
        tier="TIER_3_CLOUD",
        provider="openrouter",
        selected_model="openrouter/deepseek/deepseek-chat",
        reason="Test",
        redacted_context="",
        redactions_made=[],
        estimated_cost_usd=0.001,
        requires_approval=False,
    )

    test_state = {
        "task_id": "tsk_graph_1",
        "user_input": "Test question",
        "risk_level": "low",
        "retrieved_memories": [],
    }

    with patch.object(graph_nodes._router(), "route", return_value=mock_decision), \
         patch.object(graph_nodes._router(), "execute_inference", return_value=flat_router_result):

        out = graph_nodes.model_router(test_state)

        assert out["final_response"] == "This is a clean, unpacked response string from router."
        assert not out["final_response"].startswith("{'")  # Must NOT be raw stringified Python dict


def test_graph_nodes_memory_update_does_not_poison_mem0():
    """Verify graph.nodes.memory_update skips writing to Mem0 if errors or unavailable state occur."""
    mock_mem0 = MagicMock()

    with patch.object(graph_nodes, "_mem0", return_value=mock_mem0):
        # Case 1: Unavailable error response string
        state_unavailable = {
            "user_input": "Test query",
            "final_response": "AI Backend Unavailable: Local inference daemon is offline",
            "status": "unavailable",
        }
        res1 = graph_nodes.memory_update(state_unavailable)
        assert res1["memory_written"] is False
        mock_mem0.add.assert_not_called()

        # Case 2: State has errors list
        state_with_errors = {
            "user_input": "Test query 2",
            "final_response": "Some partial answer",
            "errors": ["Action failed due to network timeout"],
        }
        res2 = graph_nodes.memory_update(state_with_errors)
        assert res2["memory_written"] is False
        mock_mem0.add.assert_not_called()

        # Case 3: Raw dict string containing unavailable
        state_dict_error = {
            "user_input": "Test query 3",
            "final_response": "{'task_id': 'tsk_1', 'status': 'unavailable', 'error': 'AuthFailed'}",
        }
        res3 = graph_nodes.memory_update(state_dict_error)
        assert res3["memory_written"] is False
        mock_mem0.add.assert_not_called()

        # Case 4: Genuine successful response writes to Mem0
        state_success = {
            "user_input": "What is Python?",
            "final_response": "Python is a high-level programming language.",
            "status": "COMPLETED",
        }
        res4 = graph_nodes.memory_update(state_success)
        assert res4["memory_written"] is True
        mock_mem0.add.assert_called_once()


# =====================================================================
# 5. FINDING-P1-10: openrouter/ Model Prefix on Cloud Fallback
# =====================================================================

def test_deepseek_model_prefix_on_ollama_offline():
    """When Ollama is offline, model_router.route() must assign openrouter/deepseek/deepseek-chat."""
    with patch.object(model_router, "check_ollama_readiness", return_value=False):
        req = RoutingRequest(
            task_id="tsk_prefix_check",
            user_intent="Explain microservice event-driven patterns",
            task_type="reasoning",
        )
        decision = model_router.route(req)

        assert decision.tier == "FALLBACK_CLOUD"
        assert decision.provider == "openrouter"
        assert decision.selected_model == "openrouter/deepseek/deepseek-chat"
        assert decision.selected_model.startswith("openrouter/")


# =====================================================================
# 6. FINDING-P1-09: Conversational Greeting Triage
# =====================================================================

@pytest.mark.asyncio
async def test_greeting_triage_orchestrator():
    """Greetings ('hello', 'hi', 'hey') must return helpful assistant greeting, not generic OS dispatch."""
    greetings = ["hello", "hi", "hey", "hello jarvis", "hi jarvis"]

    for greeting in greetings:
        res = orchestrator._execute_instant_command(greeting)
        assert res["type"] == "assistant_info"
        assert "Hello Ganesh" in res["message"]
        assert "Instant command" not in res["message"]

    # End-to-end through process_user_query
    e2e_res = await orchestrator.process_user_query("hello")
    assert e2e_res["status"] == "COMPLETED"
    assert e2e_res["tier"] == "BYPASS"
    assert "Hello Ganesh" in e2e_res["response"]["message"]
