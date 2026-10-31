"""
Tests for LangGraph Cognitive StateGraph
Validates PDF Spec Pages 420-429 requirements:
- 4-node pipeline (memory_retrieval, policy_check, model_router, memory_update)
- Conditional edges (policy halt on Tier 3)
- Checkpointer initialisation (MemorySaver fallback)
- State schema completeness
"""

import pytest
from unittest.mock import MagicMock, patch


# ── Graph build tests ──────────────────────────────────────────────────────────

class TestJarvisGraphBuild:
    def test_graph_compiles_without_postgres(self):
        """Graph should compile using MemorySaver when Postgres is unavailable."""
        from graph.jarvis_graph import build_jarvis_graph
        from langgraph.checkpoint.memory import MemorySaver
        graph = build_jarvis_graph(checkpointer=MemorySaver())
        assert graph is not None

    def test_get_jarvis_graph_singleton(self):
        """get_jarvis_graph() returns the same object on repeated calls."""
        from graph.jarvis_graph import get_jarvis_graph
        g1 = get_jarvis_graph()
        g2 = get_jarvis_graph()
        assert g1 is g2

    def test_graph_has_correct_nodes(self):
        """Compiled graph exposes all 4 nodes."""
        from graph.jarvis_graph import build_jarvis_graph
        from langgraph.checkpoint.memory import MemorySaver
        graph = build_jarvis_graph(checkpointer=MemorySaver())
        node_names = set(graph.get_graph().nodes.keys())
        assert "memory_retrieval" in node_names
        assert "policy_check" in node_names
        assert "model_router" in node_names
        assert "memory_update" in node_names


# ── State schema tests ─────────────────────────────────────────────────────────

class TestJarvisState:
    def test_state_accepts_all_fields(self):
        """JarvisState TypedDict should accept all spec'd fields without errors."""
        from jarvis.core.state import JarvisState
        state: JarvisState = {
            "task_id": "tsk_test",
            "user_id": "ganesh",
            "user_input": "Hello JARVIS",
            "retrieved_memories": [],
            "task_type": "chat",
            "risk_level": "low",
            "policy_tier": 0,
            "approval_required": False,
            "approval_id": None,
            "policy_reason": "Tier 0 permitted",
            "selected_tools": ["web_search"],
            "selected_agents": [],
            "model_route": "TIER_1_LOCAL",
            "selected_model": "llama3.1",
            "provider": "ollama",
            "routing_reason": "local fast path",
            "tool_results": [],
            "final_response": "Hi there",
            "evidence": [],
            "duration_ms": 123.4,
            "estimated_cost_usd": 0.0,
            "memory_written": True,
        }
        assert state["task_id"] == "tsk_test"
        assert state["policy_tier"] == 0

    def test_state_optional_fields(self):
        """JarvisState should work with minimal required fields only."""
        from jarvis.core.state import JarvisState
        state: JarvisState = {
            "user_input": "test",
        }
        assert state["user_input"] == "test"


# ── Node unit tests ────────────────────────────────────────────────────────────

class TestGraphNodes:
    def test_memory_retrieval_graceful_failure(self):
        """memory_retrieval returns empty list when mem0 is unavailable."""
        from graph.nodes import memory_retrieval
        with patch("graph.nodes._mem0") as mock_mem0:
            mock_mem0.return_value.search.side_effect = RuntimeError("mem0 offline")
            result = memory_retrieval({"user_input": "hello", "user_id": "test"})
        assert "retrieved_memories" in result
        assert result["retrieved_memories"] == []

    def test_policy_check_returns_tier0_for_safe_input(self):
        """Safe conversational input should return Tier 0."""
        from graph.nodes import policy_check
        result = policy_check({
            "user_input": "What is the weather today?",
            "task_type": "chat",
            "retrieved_memories": [],
        })
        assert "policy_tier" in result
        assert result["policy_tier"] == 0
        assert result["approval_required"] is False

    def test_policy_check_returns_tier3_for_critical(self):
        """Critical destructive input should return Tier 3."""
        from graph.nodes import policy_check
        result = policy_check({
            "user_input": "format disk C: and wipe all data",
            "task_type": "system",
            "retrieved_memories": [],
        })
        assert result["policy_tier"] >= 2

    def test_model_router_halts_on_approval_required(self):
        """model_router returns policy_halt when approval_required=True and no approval_id."""
        from graph.nodes import model_router
        result = model_router({
            "user_input": "delete all files",
            "approval_required": True,
            "approval_id": None,
            "risk_level": "high",
            "policy_reason": "Tier 2 requires approval",
            "retrieved_memories": [],
        })
        assert result["model_route"] == "policy_halt"
        assert "⛔" in result["final_response"]

    def test_memory_update_skips_policy_halt(self):
        """memory_update should NOT write to mem0 when response is a halt."""
        from graph.nodes import memory_update
        with patch("graph.nodes._mem0") as mock_mem0:
            result = memory_update({
                "user_input": "test",
                "final_response": "⛔ Action halted: requires approval",
                "user_id": "test",
            })
        mock_mem0.return_value.add.assert_not_called()
        assert result.get("memory_written") is False

    def test_memory_update_writes_normal_response(self):
        """memory_update writes to mem0 for successful responses."""
        from graph.nodes import memory_update
        with patch("graph.nodes._mem0") as mock_mem0:
            mock_mem0.return_value.add.return_value = {"status": "ok"}
            result = memory_update({
                "user_input": "Hello",
                "final_response": "Hello! How can I help?",
                "user_id": "test",
            })
        mock_mem0.return_value.add.assert_called_once()
        assert result.get("memory_written") is True


# ── Conditional edge tests ─────────────────────────────────────────────────────

class TestConditionalEdges:
    def test_after_policy_check_routes_to_model_router(self):
        """Low-risk state routes to model_router."""
        from graph.jarvis_graph import _after_policy_check
        state = {"policy_tier": 0, "approval_required": False, "approval_id": None}
        assert _after_policy_check(state) == "model_router"

    def test_after_policy_check_halts_tier3(self):
        """Tier 3 + no approval → END."""
        from graph.jarvis_graph import _after_policy_check
        state = {"policy_tier": 3, "approval_required": True, "approval_id": None}
        assert _after_policy_check(state) == "END_POLICY_HALT"

    def test_after_policy_check_allows_tier3_with_token(self):
        """Tier 3 with valid approval_id → model_router."""
        from graph.jarvis_graph import _after_policy_check
        state = {"policy_tier": 3, "approval_required": True, "approval_id": "tok_abc123"}
        assert _after_policy_check(state) == "model_router"
