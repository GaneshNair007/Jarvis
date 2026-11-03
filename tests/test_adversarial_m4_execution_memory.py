"""
Milestone 4 Adversarial Test Suite: Fail-Closed Task Execution & Memory Defense
================================================================================
Empirical adversarial testing to verify:
1. `jarvis/core/task_executor.py` NEVER produces fake success:
   - Tasks requiring non-existent powers, unhandled tools, or broken tool functions
     fail closed with status="failed" and reason="NO_EXECUTABLE_HANDLER" or "TOOL_EXECUTION_ERROR".
   - Ungrounded reasoning with unavailable model responses, empty results, or exception
     dictionaries fails closed with zero fake success and zero asyncio.sleep(0.01) stubs.
   - Complete DAG TaskGraphs fail closed when dependency or execution errors occur.
2. `graph/nodes.py` strictly prevents Mem0 long-term memory poisoning:
   - Failure payloads (refusal emojis, action halts, inference errors, backend unavailability,
     raw dict strings, state errors) never trigger mem0_client.add.
   - Adversarial embedded failure tokens and error status payloads are evaluated.
3. `/v1/chat/completions` response formatting:
   - Genuine assistant replies (reply, message, text, content) are cleanly unpacked.
   - Raw error dicts or empty strings are not emitted as valid assistant replies.
"""

import asyncio
import inspect
import json
import re
import time
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jarvis.api.routes_assistants import chat_completions, ChatCompletionRequest, ChatMessage
from jarvis.core.model_router import model_router, RoutingDecision, RoutingRequest
from jarvis.core.orchestrator import orchestrator
from jarvis.core.power_registry import power_registry
from jarvis.core.task_executor import TaskExecutor
from jarvis.core.task_graph import TaskGraph, TaskNode, TaskStatus
import graph.nodes as graph_nodes


# =====================================================================
# 1. FAIL-CLOSED TASK EXECUTION & ANTI-FAKE-SUCCESS TESTS
# =====================================================================

class TestTaskExecutorFailClosed:
    """Verifies that jarvis/core/task_executor.py strictly fails closed and never fakes success."""

    @pytest.mark.asyncio
    async def test_missing_tool_in_power_registry_fails_closed(self):
        """Task requiring non-existent power must fail closed with NO_EXECUTABLE_HANDLER."""
        executor = TaskExecutor()
        task = TaskNode(
            task_id="tsk_adv_missing_tool",
            parent_goal="adv_goal_1",
            name="Missing Tool Attack",
            description="Attempt to execute unregistered power",
            department="Security",
            tool_requirements=["phantom_nonexistent_power_v99"],
        )

        res = await executor._default_agent_execution(task, {})

        assert res["status"] == "failed"
        assert res["reason"] == "NO_EXECUTABLE_HANDLER"
        assert "not registered" in res["error"]
        assert res["tools_used"] == []
        assert res["fabricated"] is False
        assert len(res["evidence"]) == 0

    @pytest.mark.asyncio
    async def test_tool_registered_with_none_handler_fails_closed(self):
        """Tool in power_registry with handler=None must fail closed with NO_EXECUTABLE_HANDLER."""
        executor = TaskExecutor()
        tool_name = "adv_power_none_handler"
        power_registry.initial_powers[tool_name] = {
            "power_id": tool_name,
            "name": tool_name,
            "description": "Registered power with None handler",
            "category": "test",
            "handler": None,
        }

        try:
            task = TaskNode(
                task_id="tsk_adv_none_handler",
                parent_goal="adv_goal_2",
                name="None Handler Task",
                description="Power has null handler",
                department="Engineering",
                tool_requirements=[tool_name],
            )
            res = await executor._default_agent_execution(task, {})

            assert res["status"] == "failed"
            assert res["reason"] == "NO_EXECUTABLE_HANDLER"
            assert "no executable handler" in res["error"]
            assert res["tools_used"] == []
            assert res["fabricated"] is False
        finally:
            power_registry.initial_powers.pop(tool_name, None)

    @pytest.mark.asyncio
    async def test_tool_registered_with_non_callable_handler_fails_closed(self):
        """Tool in power_registry with a non-callable string handler must fail closed."""
        executor = TaskExecutor()
        tool_name = "adv_power_str_handler"
        power_registry.initial_powers[tool_name] = {
            "power_id": tool_name,
            "name": tool_name,
            "description": "Registered power with string handler",
            "category": "test",
            "handler": "not_a_callable_function",
        }

        try:
            task = TaskNode(
                task_id="tsk_adv_str_handler",
                parent_goal="adv_goal_3",
                name="String Handler Task",
                description="Power has string handler",
                department="Engineering",
                tool_requirements=[tool_name],
            )
            # In task_executor.py: handler is power.get("handler"), which is truthy string.
            # Then line 165: res = handler(...) if callable(handler) else None.
            # Because it's not callable, res=None. But handler was truthy!
            # Let's verify whether it properly fails closed.
            res = await executor._default_agent_execution(task, {})
            # If a tool handler cannot execute, it MUST NOT report success!
            assert res["status"] == "failed", f"Expected failure on non-callable handler, got: {res}"
        finally:
            power_registry.initial_powers.pop(tool_name, None)

    @pytest.mark.asyncio
    async def test_broken_tool_sync_exception_fails_closed(self):
        """Tool raising synchronous exception must fail closed with TOOL_EXECUTION_ERROR."""
        executor = TaskExecutor()
        tool_name = "adv_broken_sync_tool"

        def broken_handler(**kwargs):
            raise RuntimeError("Hardware sensor explosion: DivisionByZero")

        power_registry.initial_powers[tool_name] = {
            "power_id": tool_name,
            "name": tool_name,
            "description": "Broken sync tool",
            "category": "test",
            "handler": broken_handler,
        }

        try:
            task = TaskNode(
                task_id="tsk_adv_broken_sync",
                parent_goal="adv_goal_4",
                name="Broken Sync Task",
                description="Tool throws runtime error",
                department="Engineering",
                tool_requirements=[tool_name],
            )
            res = await executor._default_agent_execution(task, {})

            assert res["status"] == "failed"
            assert res["reason"] == "TOOL_EXECUTION_ERROR"
            assert "Hardware sensor explosion" in res["error"]
            assert res["fabricated"] is False
        finally:
            power_registry.initial_powers.pop(tool_name, None)

    @pytest.mark.asyncio
    async def test_broken_tool_async_exception_fails_closed(self):
        """Tool raising asynchronous exception must fail closed with TOOL_EXECUTION_ERROR."""
        executor = TaskExecutor()
        tool_name = "adv_broken_async_tool"

        async def broken_async_handler(**kwargs):
            await asyncio.sleep(0.01)
            raise ConnectionResetError("Remote telemetry socket abruptly closed")

        power_registry.initial_powers[tool_name] = {
            "power_id": tool_name,
            "name": tool_name,
            "description": "Broken async tool",
            "category": "test",
            "handler": broken_async_handler,
        }

        try:
            task = TaskNode(
                task_id="tsk_adv_broken_async",
                parent_goal="adv_goal_5",
                name="Broken Async Task",
                description="Tool coroutine throws connection reset",
                department="Engineering",
                tool_requirements=[tool_name],
            )
            res = await executor._default_agent_execution(task, {})

            assert res["status"] == "failed"
            assert res["reason"] == "TOOL_EXECUTION_ERROR"
            assert "Remote telemetry socket abruptly closed" in res["error"]
            assert res["fabricated"] is False
        finally:
            power_registry.initial_powers.pop(tool_name, None)

    @pytest.mark.asyncio
    async def test_multi_tool_chain_fails_closed_on_second_tool_failure(self):
        """If tool 1 succeeds but tool 2 fails, overall task execution must fail closed."""
        executor = TaskExecutor()
        tool1 = "adv_multi_tool_ok"
        tool2 = "adv_multi_tool_fail"

        power_registry.initial_powers[tool1] = {
            "power_id": tool1,
            "name": tool1,
            "category": "test",
            "handler": lambda **kw: {"step1": "ok"},
        }
        power_registry.initial_powers[tool2] = {
            "power_id": tool2,
            "name": tool2,
            "category": "test",
            "handler": lambda **kw: (_ for _ in ()).throw(ValueError("Step 2 corrupted")),
        }

        try:
            task = TaskNode(
                task_id="tsk_adv_chain_fail",
                parent_goal="adv_goal_6",
                name="Chain Fail Task",
                description="Multi-tool pipeline where second fails",
                department="Engineering",
                tool_requirements=[tool1, tool2],
            )
            res = await executor._default_agent_execution(task, {})

            assert res["status"] == "failed"
            assert res["reason"] == "TOOL_EXECUTION_ERROR"
            assert "Step 2 corrupted" in res["error"]
            # Tool 1 was executed before failure, but task overall did NOT succeed
            assert tool1 in res["tools_used"]
            assert tool2 not in res["tools_used"]
        finally:
            power_registry.initial_powers.pop(tool1, None)
            power_registry.initial_powers.pop(tool2, None)

    @pytest.mark.asyncio
    async def test_tool_returning_error_payload_fails_closed_or_reports_failure(self):
        """
        Adversarial Boundary Test:
        When a tool handler returns a dictionary reporting explicit failure (e.g. {'status': 'error'}),
        the task executor must NOT blindly report top-level success.
        """
        executor = TaskExecutor()
        tool_name = "adv_tool_returns_error_dict"

        power_registry.initial_powers[tool_name] = {
            "power_id": tool_name,
            "name": tool_name,
            "category": "test",
            "handler": lambda **kw: {"status": "error", "error": "Disk full, write failed"},
        }

        try:
            task = TaskNode(
                task_id="tsk_adv_error_dict",
                parent_goal="adv_goal_7",
                name="Tool Returning Error Dict",
                description="Handler returns error dict without throwing exception",
                department="Storage",
                tool_requirements=[tool_name],
            )
            res = await executor._default_agent_execution(task, {})

            # Invariant: If a tool reported an error dictionary, top-level status must NOT be success
            assert res["status"] != "success", (
                f"VULNERABILITY DETECTED: TaskExecutor reported top-level status='success' "
                f"even though tool returned an explicit failure payload: {res.get('tool_results')}"
            )
        finally:
            power_registry.initial_powers.pop(tool_name, None)

    @pytest.mark.asyncio
    async def test_ungrounded_reasoning_unavailable_fails_closed(self):
        """Ungrounded reasoning when model inference is unavailable must fail closed."""
        executor = TaskExecutor()
        task = TaskNode(
            task_id="tsk_adv_unavail_inf",
            parent_goal="adv_goal_8",
            name="Reasoning Unavailable Task",
            description="Pure reasoning with unavailable inference",
            department="Strategy",
            tool_requirements=[],
        )

        unavail_payload = {
            "task_id": "tsk_adv_unavail_inf",
            "status": "unavailable",
            "error": "Ollama offline and cloud gateways unreachable",
            "reply": "AI Backend Unavailable",
        }

        with patch.object(model_router, "execute_inference", return_value=unavail_payload):
            res = await executor._default_agent_execution(task, {})

            assert res["status"] == "failed"
            assert res["reason"] == "NO_EXECUTABLE_HANDLER"
            assert "unavailable" in res["error"].lower()
            assert res["tools_used"] == []

    @pytest.mark.asyncio
    async def test_ungrounded_reasoning_error_status_fails_closed(self):
        """Ungrounded reasoning with status='error' must fail closed with NO_EXECUTABLE_HANDLER."""
        executor = TaskExecutor()
        task = TaskNode(
            task_id="tsk_adv_err_status",
            parent_goal="adv_goal_9",
            name="Reasoning Error Status",
            description="Pure reasoning with error status",
            department="Strategy",
            tool_requirements=[],
        )

        err_payload = {
            "task_id": "tsk_adv_err_status",
            "status": "error",
            "error": "Model quota exhausted 402",
        }

        with patch.object(model_router, "execute_inference", return_value=err_payload):
            res = await executor._default_agent_execution(task, {})

            assert res["status"] == "failed"
            assert res["reason"] == "NO_EXECUTABLE_HANDLER"
            assert "Model quota exhausted" in res["error"]

    @pytest.mark.asyncio
    async def test_ungrounded_reasoning_failed_status_fails_closed(self):
        """Ungrounded reasoning with status='failed' must fail closed with NO_EXECUTABLE_HANDLER."""
        executor = TaskExecutor()
        task = TaskNode(
            task_id="tsk_adv_failed_status",
            parent_goal="adv_goal_10",
            name="Reasoning Failed Status",
            description="Pure reasoning with failed status",
            department="Strategy",
            tool_requirements=[],
        )

        failed_payload = {
            "task_id": "tsk_adv_failed_status",
            "status": "failed",
            "error": "Authentication failure: invalid token",
        }

        with patch.object(model_router, "execute_inference", return_value=failed_payload):
            res = await executor._default_agent_execution(task, {})

            assert res["status"] == "failed"
            assert res["reason"] == "NO_EXECUTABLE_HANDLER"
            assert "Authentication failure" in res["error"]

    @pytest.mark.asyncio
    async def test_ungrounded_reasoning_exception_dict_fails_closed(self):
        """Ungrounded reasoning with an error key dict (no status key) must fail closed."""
        executor = TaskExecutor()
        task = TaskNode(
            task_id="tsk_adv_exc_dict",
            parent_goal="adv_goal_11",
            name="Reasoning Exception Dict",
            description="Pure reasoning with raw error dict",
            department="Strategy",
            tool_requirements=[],
        )

        exc_dict = {"error": "Connection abruptly aborted by peer"}

        with patch.object(model_router, "execute_inference", return_value=exc_dict):
            res = await executor._default_agent_execution(task, {})

            assert res["status"] == "failed"
            assert res["reason"] == "NO_EXECUTABLE_HANDLER"
            assert "Connection abruptly aborted" in res["error"]

    @pytest.mark.asyncio
    async def test_ungrounded_reasoning_empty_result_fails_closed(self):
        """
        Adversarial Invariant Test:
        When model inference returns an empty dictionary ({}), the TaskExecutor
        MUST NOT claim success or fabricate 'Cognitive execution cycle complete.'
        """
        executor = TaskExecutor()
        task = TaskNode(
            task_id="tsk_adv_empty_dict",
            parent_goal="adv_goal_12",
            name="Empty Result Task",
            description="Inference produces empty result",
            department="Strategy",
            tool_requirements=[],
        )

        with patch.object(model_router, "execute_inference", return_value={}):
            res = await executor._default_agent_execution(task, {})

            # Invariant: Empty inference response must fail closed, NEVER claim success!
            assert res["status"] != "success", (
                f"VULNERABILITY DETECTED: Empty model inference result {{}} produced fake success: {res}"
            )
            assert res.get("response") != "Cognitive execution cycle complete.", (
                "VULNERABILITY DETECTED: Fake canned completion string fabricated on empty model result."
            )

    @pytest.mark.asyncio
    async def test_ungrounded_reasoning_empty_reply_string_fails_closed(self):
        """
        Adversarial Invariant Test:
        When model inference returns an empty reply string (''), the TaskExecutor
        MUST NOT claim success or fabricate 'Cognitive execution cycle complete.'
        """
        executor = TaskExecutor()
        task = TaskNode(
            task_id="tsk_adv_empty_reply",
            parent_goal="adv_goal_13",
            name="Empty Reply String Task",
            description="Inference produces empty reply string",
            department="Strategy",
            tool_requirements=[],
        )

        with patch.object(model_router, "execute_inference", return_value={"status": "completed", "reply": ""}):
            res = await executor._default_agent_execution(task, {})

            assert res["status"] != "success", (
                f"VULNERABILITY DETECTED: Empty reply string produced fake success: {res}"
            )
            assert res.get("response") != "Cognitive execution cycle complete.", (
                "VULNERABILITY DETECTED: Fake canned completion string fabricated on empty reply."
            )

    @pytest.mark.asyncio
    async def test_ungrounded_reasoning_none_reply_fails_closed(self):
        """
        Adversarial Invariant Test:
        When model inference returns reply=None, the TaskExecutor MUST NOT fabricate success.
        """
        executor = TaskExecutor()
        task = TaskNode(
            task_id="tsk_adv_none_reply",
            parent_goal="adv_goal_14",
            name="None Reply Task",
            description="Inference produces None reply",
            department="Strategy",
            tool_requirements=[],
        )

        with patch.object(model_router, "execute_inference", return_value={"status": "completed", "reply": None}):
            res = await executor._default_agent_execution(task, {})

            assert res["status"] != "success", (
                f"VULNERABILITY DETECTED: reply=None produced fake success: {res}"
            )

    def test_no_sleeping_agent_or_fake_success_in_task_executor(self):
        """Verify TaskExecutor source code contains zero asyncio.sleep(0.01) mocks in execution path."""
        source = inspect.getsource(TaskExecutor._default_agent_execution)
        assert "asyncio.sleep(0.01)" not in source, "Found asyncio.sleep(0.01) sleeping agent mock in _default_agent_execution!"
        assert "sleep(" not in source, "Found sleep call in _default_agent_execution!"

    @pytest.mark.asyncio
    async def test_task_graph_dag_execution_fail_closed_on_broken_task(self):
        """Complete TaskGraph execution must report status=FAILED when a task fails closed."""
        executor = TaskExecutor()
        graph = TaskGraph(goal_id="adv_goal_dag_failure")

        # Task 1: requires missing tool -> will fail
        t1 = TaskNode(
            task_id="dag_t1",
            parent_goal="adv_goal_dag_failure",
            name="Missing Tool Step",
            description="Requires non-existent tool",
            department="Engineering",
            tool_requirements=["nonexistent_tool_alpha"],
        )
        # Task 2: depends on Task 1
        t2 = TaskNode(
            task_id="dag_t2",
            parent_goal="adv_goal_dag_failure",
            name="Dependent Step",
            description="Depends on t1",
            department="Engineering",
            dependencies=["dag_t1"],
        )

        graph.add_node(t1)
        graph.add_node(t2)

        report = await executor.run(graph, timeout=5.0)

        assert report.status == TaskStatus.FAILED
        assert report.failed_tasks >= 1
        assert report.completed_tasks == 0
        assert graph.nodes["dag_t1"].status == TaskStatus.FAILED


# =====================================================================
# 2. MEM0 LONG-TERM MEMORY POISONING DEFENSE TESTS
# =====================================================================

class TestMem0MemoryPoisoningDefense:
    """Verifies that graph/nodes.py strictly prevents Mem0 long-term memory poisoning."""

    @pytest.mark.parametrize(
        "failure_response,description",
        [
            ("⛔ Policy Violation: Shell command blocked", "Refusal emoji at start"),
            ("Action halted: Administrator approval required", "Action halted prefix"),
            ("Inference error: Rate limit exceeded (429)", "Inference error prefix"),
            ("Model routing error: Tier 3 Cloud uncontactable", "Model routing error prefix"),
            ("AI Backend Unavailable: Ollama socket timeout", "AI Backend Unavailable prefix"),
            ("Execution failed: Subprocess exited with code 127", "Execution failed prefix"),
            ("{'task_id': 'tsk_1', 'status': 'unavailable', 'error': 'offline'}", "Stringified unavailable dict (single quote)"),
            ('{"task_id": "tsk_2", "status": "unavailable", "error": "timeout"}', "JSON stringified unavailable dict"),
            ("{'task_id': 'tsk_3', 'status': 'failed', 'error': 'auth_err'}", "Stringified failed dict (single quote)"),
            ('{"task_id": "tsk_4", "status": "failed", "error": "auth_err"}', "JSON stringified failed dict"),
        ],
    )
    def test_memory_update_rejects_standard_failure_payloads(self, failure_response, description):
        """Verify memory_update rejects standard failure strings and never calls mem0_client.add."""
        mock_mem0 = MagicMock()
        with patch.object(graph_nodes, "_mem0", return_value=mock_mem0):
            state = {
                "user_input": "Execute system test command",
                "final_response": failure_response,
            }

            res = graph_nodes.memory_update(state)

            assert res["memory_written"] is False, f"Memory write allowed for failure payload ({description}): {failure_response}"
            mock_mem0.add.assert_not_called()

    @pytest.mark.parametrize(
        "state_override,description",
        [
            ({"errors": ["Rate limit 429"]}, "Non-empty errors list"),
            ({"model_route": "error"}, "model_route == 'error'"),
            ({"status": "unavailable"}, "status == 'unavailable'"),
            ({"status": "failed"}, "status == 'failed'"),
            ({"status": "error"}, "status == 'error'"),
        ],
    )
    def test_memory_update_rejects_error_state_flags(self, state_override, description):
        """Verify memory_update respects state error flags even if final_response looks benign."""
        mock_mem0 = MagicMock()
        with patch.object(graph_nodes, "_mem0", return_value=mock_mem0):
            base_state = {
                "user_input": "Show me database records",
                "final_response": "Here is some partial data before the crash occurred.",
            }
            base_state.update(state_override)

            res = graph_nodes.memory_update(base_state)

            assert res["memory_written"] is False, f"Memory write allowed when state has {description}"
            mock_mem0.add.assert_not_called()

    def test_memory_update_rejects_empty_user_input_or_response(self):
        """Verify memory_update does not write empty turns to Mem0."""
        mock_mem0 = MagicMock()
        with patch.object(graph_nodes, "_mem0", return_value=mock_mem0):
            # Empty user input
            res1 = graph_nodes.memory_update({"user_input": "", "final_response": "Valid response"})
            assert res1["memory_written"] is False
            mock_mem0.add.assert_not_called()

            # Empty response
            res2 = graph_nodes.memory_update({"user_input": "Valid input", "final_response": ""})
            assert res2["memory_written"] is False
            mock_mem0.add.assert_not_called()

    def test_memory_update_allows_clean_successful_turn(self):
        """Verify memory_update writes valid turns to Mem0 when no errors or failure indicators exist."""
        mock_mem0 = MagicMock()
        with patch.object(graph_nodes, "_mem0", return_value=mock_mem0):
            state = {
                "user_input": "What is Python?",
                "final_response": "Python is an interpreted, high-level, general-purpose programming language.",
                "status": "COMPLETED",
            }

            res = graph_nodes.memory_update(state)

            assert res["memory_written"] is True
            mock_mem0.add.assert_called_once()
            call_kwargs = mock_mem0.add.call_args.kwargs
            assert len(call_kwargs["messages"]) == 2
            assert call_kwargs["messages"][0]["content"] == "What is Python?"
            assert call_kwargs["messages"][1]["content"] == "Python is an interpreted, high-level, general-purpose programming language."

    @pytest.mark.parametrize(
        "embedded_failure,description",
        [
            ("Warning from system: ⛔ Policy Violation occurred", "Embedded refusal emoji not at start"),
            ("System notification: Action halted by security officer", "Embedded 'Action halted' not at start"),
            ("Fatal diagnosis: AI Backend Unavailable on host", "Embedded 'AI Backend Unavailable' not at start"),
            ("Process exited with code 1: Execution failed", "Embedded 'Execution failed' not at start"),
        ],
    )
    def test_memory_update_adversarial_embedded_failure_phrases(self, embedded_failure, description):
        """
        Adversarial Boundary Test:
        Checks if failure tokens embedded in the middle of final_response (rather than startswith)
        can bypass memory_update filtering and poison Mem0.
        """
        mock_mem0 = MagicMock()
        with patch.object(graph_nodes, "_mem0", return_value=mock_mem0):
            state = {
                "user_input": "Perform privileged administrative task",
                "final_response": embedded_failure,
            }

            res = graph_nodes.memory_update(state)

            # Invariant: A response containing refusal emoji or halt indicators MUST NOT be written to Mem0
            assert res["memory_written"] is False, (
                f"VULNERABILITY DETECTED: Embedded failure token bypassed startswith filter and wrote to Mem0! "
                f"Payload ({description}): '{embedded_failure}'"
            )
            mock_mem0.add.assert_not_called()

    @pytest.mark.parametrize(
        "error_dict_string,description",
        [
            ("{'task_id': 'tsk_err', 'status': 'error', 'error': 'DatabaseConnectionRefused'}", "Python dict string with status='error'"),
            ('{"task_id": "tsk_err", "status": "error", "error": "DatabaseConnectionRefused"}', "JSON dict string with status='error'"),
        ],
    )
    def test_memory_update_adversarial_error_status_dict_strings(self, error_dict_string, description):
        """
        Adversarial Boundary Test:
        Checks if stringified dictionaries with status='error' (rather than 'unavailable' or 'failed')
        are caught and excluded from Mem0.
        """
        mock_mem0 = MagicMock()
        with patch.object(graph_nodes, "_mem0", return_value=mock_mem0):
            state = {
                "user_input": "Query database status",
                "final_response": error_dict_string,
            }

            res = graph_nodes.memory_update(state)

            # Invariant: Raw error dict strings MUST NOT be stored as assistant knowledge in Mem0
            assert res["memory_written"] is False, (
                f"VULNERABILITY DETECTED: Stringified error dictionary with status='error' wrote to Mem0! "
                f"Payload ({description}): '{error_dict_string}'"
            )
            mock_mem0.add.assert_not_called()


# =====================================================================
# 3. DROP-IN OPENAI ROUTE RESPONSE FORMAT SAFETY TESTS
# =====================================================================

class TestOpenAIRouteResponseFormatSafety:
    """Verifies that /v1/chat/completions strictly formats responses and never emits raw error dicts."""

    @pytest.mark.asyncio
    async def test_routes_assistants_valid_reply_unpacked(self):
        """Verify normal model reply key is cleanly unpacked into OpenAI content."""
        fake_reply = "Quantum superposition enables simultaneous state computation."
        mock_res = {
            "task_id": "chat_ok_1",
            "status": "COMPLETED",
            "tier": "TIER_3_CLOUD",
            "response": {
                "status": "success",
                "reply": fake_reply,
                "model": "openrouter/deepseek/deepseek-chat",
            },
        }

        req = ChatCompletionRequest(
            model="gpt-4o",
            messages=[ChatMessage(role="user", content="Explain quantum superposition.")],
        )

        with patch.object(orchestrator, "process_user_query", new_callable=AsyncMock, return_value=mock_res):
            out = await chat_completions(req)

            assert out["choices"][0]["message"]["content"] == fake_reply
            assert out["choices"][0]["finish_reason"] == "stop"

    @pytest.mark.asyncio
    async def test_routes_assistants_instant_command_message_unpacked(self):
        """Verify assistant greeting message key is cleanly unpacked into OpenAI content."""
        greeting_text = "Hello Ganesh! I am JARVIS, your personal autonomous AI assistant."
        mock_res = {
            "task_id": "chat_ok_2",
            "status": "COMPLETED",
            "tier": "BYPASS",
            "response": {
                "type": "assistant_info",
                "message": greeting_text,
            },
        }

        req = ChatCompletionRequest(
            model="gpt-4o",
            messages=[ChatMessage(role="user", content="hello")],
        )

        with patch.object(orchestrator, "process_user_query", new_callable=AsyncMock, return_value=mock_res):
            out = await chat_completions(req)

            assert out["choices"][0]["message"]["content"] == greeting_text

    @pytest.mark.asyncio
    @pytest.mark.parametrize("key_name", ["text", "content"])
    async def test_routes_assistants_fallback_text_and_content_keys(self, key_name):
        """Verify 'text' and 'content' keys in response dict are cleanly extracted."""
        expected_content = f"Response extracted from {key_name} key."
        mock_res = {
            "task_id": f"chat_key_{key_name}",
            "status": "COMPLETED",
            "response": {key_name: expected_content},
        }

        req = ChatCompletionRequest(
            model="gpt-4o",
            messages=[ChatMessage(role="user", content="test")],
        )

        with patch.object(orchestrator, "process_user_query", new_callable=AsyncMock, return_value=mock_res):
            out = await chat_completions(req)

            assert out["choices"][0]["message"]["content"] == expected_content

    @pytest.mark.asyncio
    async def test_routes_assistants_does_not_emit_raw_error_dict(self):
        """
        Adversarial Invariant Test:
        When orchestrator returns an error response dictionary (e.g. {'status': 'error', 'error': 'Rate limit'}),
        /v1/chat/completions MUST NOT emit a stringified Python dictionary as the assistant message content.
        """
        err_res = {
            "task_id": "chat_err_1",
            "status": "FAILED",
            "response": {
                "status": "error",
                "error": "Rate limit exceeded (429): Quota exhausted",
            },
        }

        req = ChatCompletionRequest(
            model="gpt-4o",
            messages=[ChatMessage(role="user", content="compute complex model")],
        )

        with patch.object(orchestrator, "process_user_query", new_callable=AsyncMock, return_value=err_res):
            out = await chat_completions(req)
            content = out["choices"][0]["message"]["content"]

            # Invariant: Raw python error dict strings MUST NOT be emitted as valid assistant replies!
            assert not content.startswith("{'"), (
                f"VULNERABILITY DETECTED: /v1/chat/completions emitted raw Python error dict string: {content}"
            )
            assert not content.startswith('{"status": "error"'), (
                f"VULNERABILITY DETECTED: /v1/chat/completions emitted raw JSON error dict string: {content}"
            )

    @pytest.mark.asyncio
    async def test_routes_assistants_does_not_emit_empty_dict_string(self):
        """
        Adversarial Invariant Test:
        When orchestrator returns an empty response dict ({}), /v1/chat/completions
        MUST NOT emit '{}' as assistant message content.
        """
        empty_res = {
            "task_id": "chat_empty_1",
            "status": "COMPLETED",
            "response": {},
        }

        req = ChatCompletionRequest(
            model="gpt-4o",
            messages=[ChatMessage(role="user", content="test")],
        )

        with patch.object(orchestrator, "process_user_query", new_callable=AsyncMock, return_value=empty_res):
            out = await chat_completions(req)
            content = out["choices"][0]["message"]["content"]

            assert content != "{}", (
                f"VULNERABILITY DETECTED: /v1/chat/completions emitted empty dict string '{{}}' as reply content."
            )

    @pytest.mark.asyncio
    async def test_routes_assistants_does_not_emit_empty_dict_on_top_level_error(self):
        """
        Adversarial Invariant Test:
        When orchestrator returns a top-level error (without 'response' key),
        /v1/chat/completions MUST NOT emit '{}'.
        """
        top_err = {
            "task_id": "chat_top_err",
            "status": "ERROR",
            "error": "Service unavailable: model gateway down",
        }

        req = ChatCompletionRequest(
            model="gpt-4o",
            messages=[ChatMessage(role="user", content="test")],
        )

        with patch.object(orchestrator, "process_user_query", new_callable=AsyncMock, return_value=top_err):
            out = await chat_completions(req)
            content = out["choices"][0]["message"]["content"]

            assert content != "{}", (
                f"VULNERABILITY DETECTED: /v1/chat/completions defaulted to '{{}}' on top-level orchestrator error."
            )
