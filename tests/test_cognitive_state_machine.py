"""
JARVIS Cognitive State Machine & Milestone M1 Verification Suite
Validates:
1. Unified 15-field state schema (JarvisState / BrainState) and Pydantic models.
2. 6-tier error taxonomy, classification, and remediation strategy.
3. SqliteCheckpointSaver durable persistence, thread resumption, and crash recovery.
4. 8 cognitive nodes (perceive, recall, plan, policy, act, verify, reflect, remember).
5. 8-node cyclic LangGraph compilation, fast-path routing, policy approval gates,
   bounded reflection loops, and thread checkpoint persistence.
"""

from __future__ import annotations

import sqlite3
import time
import uuid
import pytest
from unittest.mock import MagicMock, patch

from jarvis.brain.state import (
    JarvisState,
    BrainState,
    InputEvent,
    PlanStep,
    RetrievedMemory,
    ToolExecutionRecord,
    EvidenceItem,
    PolicyDecisionState,
    ApprovalState,
    CognitiveError,
    CostLedger,
)
from jarvis.brain.errors import (
    CognitiveErrorCode,
    TransientNetworkError,
    SessionExpiredError,
    PolicyDeniedError,
    AIUsageLimitError,
    InsufficientEvidenceError,
    PermanentFailureError,
    classify_error,
    get_remediation_strategy,
)
from jarvis.brain.checkpointer import SqliteCheckpointSaver
from graph.nodes import (
    perceive,
    recall,
    plan,
    policy,
    act,
    verify,
    reflect,
    remember,
    memory_retrieval,
    policy_check,
    model_router,
    memory_update,
)
from graph.jarvis_graph import (
    build_jarvis_graph,
    get_jarvis_graph,
    _after_recall,
    _after_policy,
    _after_verify,
    _after_reflect,
)


# ── 1. State Schema & Pydantic Validation Tests ──────────────────────────────


class TestCognitiveStateSchema:
    def test_jarvis_state_all_15_mandatory_fields(self):
        """JarvisState TypedDict accepts and retains all 15 required cognitive fields."""
        state: JarvisState = {
            # 1. Identity & Tracking
            "user_id": "ganesh",
            "session_id": "ses_001",
            "trace_id": "trc_alpha",
            "task_id": "tsk_001",
            # 2. Perception & Intent
            "input_event": {"event_id": "evt_1", "text": "Deploy system"},
            "user_input": "Deploy system",
            "goal": "Deploy system",
            "messages": [],
            # 3. Context & Working Memory
            "retrieved_memories": ["Mem 1"],
            "retrieved_memory_records": [{"id": "m1", "content": "Mem 1"}],
            "scratchpad": "Analyzing deployment requirements",
            # 4. Planning & Routing
            "plan": [{"step_id": "s1", "description": "Check pre-requisites"}],
            "current_step_index": 0,
            "is_fast_path": False,
            "selected_tools": ["deploy_tool"],
            # 5. Security & Approvals
            "policy_tier": 2,
            "risk_level": "high",
            "policy_decision": {"tier": 2, "approval_required": True},
            "approvals": {"status": "PENDING"},
            # 6. Execution & Telemetry
            "tool_calls": [],
            "tool_results": [],
            "final_response": "Pending approval",
            "duration_ms": 12.5,
            # 7. Verification & Evidence
            "evidence": [{"source": "system", "claim": "Pre-check passed"}],
            "confidence": 0.95,
            # 8. Learning, Reflection & Governance
            "errors": [],
            "reflection_count": 0,
            "cost": {"total_tokens": 150},
            "estimated_cost_usd": 0.002,
            "memory_written": False,
        }
        assert state["user_id"] == "ganesh"
        assert state["confidence"] == 0.95
        assert len(state["plan"]) == 1

    def test_brain_state_is_jarvis_state_alias(self):
        """BrainState is a canonical alias for JarvisState."""
        assert BrainState is JarvisState

    def test_pydantic_component_models(self):
        """Validates all Pydantic state sub-models."""
        event = InputEvent(text="Hello", modality="text")
        assert event.text == "Hello"
        assert event.event_id.startswith("evt_")

        step = PlanStep(description="Run test", tool="pytest")
        assert step.status == "pending"
        assert step.step_id.startswith("stp_")

        mem = RetrievedMemory(content="User prefers Python", category="preference")
        assert mem.is_explicit is True
        assert mem.score == 0.0

        rec = ToolExecutionRecord(tool_name="web_search", arguments={"q": "test"})
        assert rec.status == "invoked"
        assert rec.call_id.startswith("call_")

        ev = EvidenceItem(source="file_check", claim="File exists")
        assert ev.confidence == 1.0

        pol = PolicyDecisionState(tier=1, risk_level="low", reason="Read-only")
        assert pol.tier == 1

        appr = ApprovalState(status="PENDING", action_summary="Delete table")
        assert appr.status == "PENDING"

        err = CognitiveError(code="TRANSIENT_NETWORK", message="503 Unavailable", recoverable=True)
        assert err.recoverable is True

        cost = CostLedger(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        assert cost.total_tokens == 150


# ── 2. 6-Tier Error Taxonomy Tests ───────────────────────────────────────────


class TestErrorTaxonomy:
    def test_error_code_enum_values(self):
        """Verifies the 6 authoritative error codes."""
        assert CognitiveErrorCode.TRANSIENT_NETWORK == "TRANSIENT_NETWORK"
        assert CognitiveErrorCode.SESSION_EXPIRED == "SESSION_EXPIRED"
        assert CognitiveErrorCode.POLICY_DENIED == "POLICY_DENIED"
        assert CognitiveErrorCode.AI_USAGE_LIMIT == "AI_USAGE_LIMIT"
        assert CognitiveErrorCode.INSUFFICIENT_EVIDENCE == "INSUFFICIENT_EVIDENCE"
        assert CognitiveErrorCode.PERMANENT_FAILURE == "PERMANENT_FAILURE"

    def test_classify_structured_exceptions(self):
        """Validates classification of typed cognitive exceptions."""
        e1 = TransientNetworkError("Ollama host is warming up")
        c1 = classify_error(e1)
        assert c1.code == "TRANSIENT_NETWORK"
        assert c1.recoverable is True

        e2 = SessionExpiredError("HMAC approval token expired")
        c2 = classify_error(e2)
        assert c2.code == "SESSION_EXPIRED"
        assert c2.recoverable is True

        e3 = PolicyDeniedError("Emergency kill switch active")
        c3 = classify_error(e3)
        assert c3.code == "POLICY_DENIED"
        assert c3.recoverable is False

        e4 = AIUsageLimitError("Daily cloud budget cap reached")
        c4 = classify_error(e4)
        assert c4.code == "AI_USAGE_LIMIT"
        assert c4.recoverable is False

        e5 = InsufficientEvidenceError("Search returned 0 results")
        c5 = classify_error(e5)
        assert c5.code == "INSUFFICIENT_EVIDENCE"
        assert c5.recoverable is True

        e6 = PermanentFailureError("Syntax error in payload")
        c6 = classify_error(e6)
        assert c6.code == "PERMANENT_FAILURE"
        assert c6.recoverable is False

    def test_classify_string_patterns(self):
        """Validates pattern detection from arbitrary exception strings."""
        assert classify_error("Connection timed out after 30000ms").code == "TRANSIENT_NETWORK"
        assert classify_error("stale token: signature expired").code == "SESSION_EXPIRED"
        assert classify_error("Execution forbidden: emergency kill_switch").code == "POLICY_DENIED"
        assert classify_error("Cost governor circuit breaker tripped").code == "AI_USAGE_LIMIT"
        assert classify_error("Missing evidence for assertion").code == "INSUFFICIENT_EVIDENCE"
        assert classify_error("Unexpected token in JSON").code == "PERMANENT_FAILURE"

    def test_remediation_strategy_mapping(self):
        """Validates remediation target routing and backoff configuration."""
        err_transient = CognitiveError(code="TRANSIENT_NETWORK", message="Timeout", recoverable=True, retry_count=1)
        strat1 = get_remediation_strategy(err_transient)
        assert strat1["target_node"] == "act"
        assert strat1["can_retry"] is True
        assert strat1["backoff_sec"] == 2

        err_evidence = CognitiveError(code="INSUFFICIENT_EVIDENCE", message="Empty", recoverable=True, retry_count=0)
        strat2 = get_remediation_strategy(err_evidence)
        assert strat2["target_node"] == "plan"
        assert strat2["can_retry"] is True

        err_fatal = CognitiveError(code="POLICY_DENIED", message="Halt", recoverable=False)
        strat3 = get_remediation_strategy(err_fatal)
        assert strat3["target_node"] == "remember"
        assert strat3["can_retry"] is False


# ── 3. SQLite Checkpoint Saver Persistence & Recovery Tests ───────────────────


class TestSqliteCheckpointer:
    def test_sqlite_saver_in_memory_persistence(self):
        """SqliteCheckpointSaver persists and retrieves checkpoints."""
        saver = SqliteCheckpointSaver(db_path=":memory:")
        config = {"configurable": {"thread_id": "th_test", "checkpoint_ns": ""}}

        checkpoint = {
            "v": 1,
            "id": "chk_001",
            "ts": "2026-11-01T12:00:00Z",
            "channel_values": {"status": "ok", "count": 42},
            "channel_versions": {"status": 1, "count": 1},
            "versions_seen": {},
        }
        metadata = {"source": "unit_test", "step": 1}

        saved_config = saver.put(config, checkpoint, metadata, {})
        assert saved_config["configurable"]["checkpoint_id"] == "chk_001"

        retrieved = saver.get_tuple(config)
        assert retrieved is not None
        assert retrieved.checkpoint["id"] == "chk_001"
        assert retrieved.checkpoint["channel_values"]["count"] == 42
        assert retrieved.metadata["step"] == 1

    def test_sqlite_saver_crash_recovery_across_instances(self, tmp_path):
        """Simulates process restart/crash by reading checkpoints from a new instance."""
        db_file = tmp_path / "checkpoints.db"

        # 1. Instance 1 writes checkpoint
        saver1 = SqliteCheckpointSaver(db_path=str(db_file))
        config = {"configurable": {"thread_id": "th_crash", "checkpoint_ns": ""}}
        checkpoint = {
            "v": 1,
            "id": "chk_crash_1",
            "ts": "2026-11-01T12:00:00Z",
            "channel_values": {"state_payload": "persisted_value"},
            "channel_versions": {"state_payload": 1},
            "versions_seen": {},
        }
        saver1.put(config, checkpoint, {"step": "pre_crash"}, {})

        # 2. Instance 2 connects to the same SQLite file and recovers
        saver2 = SqliteCheckpointSaver(db_path=str(db_file))
        recovered = saver2.get_tuple(config)
        assert recovered is not None
        assert recovered.checkpoint["id"] == "chk_crash_1"
        assert recovered.checkpoint["channel_values"]["state_payload"] == "persisted_value"

    def test_sqlite_saver_list_and_delete(self):
        """SqliteCheckpointSaver supports listing and deleting thread history."""
        saver = SqliteCheckpointSaver(db_path=":memory:")
        config = {"configurable": {"thread_id": "th_list", "checkpoint_ns": ""}}

        for i in range(3):
            cp = {
                "v": 1,
                "id": f"chk_{i:03d}",
                "ts": "2026-11-01T12:00:00Z",
                "channel_values": {"step": i},
                "channel_versions": {"step": i},
                "versions_seen": {},
            }
            saver.put(config, cp, {"idx": i}, {})

        history = list(saver.list(config))
        assert len(history) == 3
        # Most recent checkpoint first
        assert history[0].checkpoint["id"] == "chk_002"

        # Delete thread
        saver.delete_thread("th_list")
        assert saver.get_tuple(config) is None


# ── 4. Cognitive Nodes Unit Tests ─────────────────────────────────────────────


class TestCognitiveNodes:
    def test_perceive_normalizes_and_detects_fast_path(self):
        """perceive node sets goal, input_event, and detects fast-path queries."""
        state = {"user_input": "system health"}
        out = perceive(state)
        assert out["goal"] == "system health"
        assert out["is_fast_path"] is True
        assert out["input_event"]["text"] == "system health"
        assert "trace_id" in out

    def test_perceive_complex_query_not_fast_path(self):
        """perceive node marks non-trivial requests as complex."""
        state = {"user_input": "Decompose sales records into quarterly PDF reports"}
        out = perceive(state)
        assert out["is_fast_path"] is False

    def test_recall_populates_memories_and_records(self):
        """recall node retrieves memories and populates structured records."""
        with patch("graph.nodes._mem0") as mock_mem0:
            mock_mem0.return_value.search.return_value = [{"id": "m1", "memory": "Prefers dark mode"}]
            out = recall({"goal": "What is my UI preference?", "user_id": "ganesh"})
        assert "Prefers dark mode" in out["retrieved_memories"]
        assert len(out["retrieved_memory_records"]) == 1
        assert out["retrieved_memory_records"][0]["content"] == "Prefers dark mode"

    def test_plan_caps_tools_to_12(self):
        """plan node enforces 6 GB VRAM budget by capping active tools to 12."""
        tools = [f"tool_{i}" for i in range(25)]
        out = plan({"goal": "Run deep diagnostics", "is_fast_path": False, "selected_tools": tools})
        assert len(out["selected_tools"]) <= 12
        assert len(out["plan"]) >= 2

    def test_policy_halts_on_kill_switch(self):
        """policy node triggers immediate security halt when kill switch is active."""
        with patch("graph.nodes._policy_gate") as mock_gate:
            mock_gate.return_value.is_kill_switch_active.return_value = True
            out = policy({"goal": "safe read query"})
        assert out["policy_tier"] == 3
        assert out["risk_level"] == "critical"
        assert out["approval_required"] is True
        assert "ACTIVE" in out["policy_reason"]
        assert len(out["errors"]) == 1
        assert out["errors"][0]["code"] == "POLICY_DENIED"

    def test_act_halts_unapproved_tier2(self):
        """act node generates policy halt response when approval is required but missing."""
        out = act(
            {
                "goal": "delete production database",
                "approval_required": True,
                "approval_id": None,
                "policy_reason": "Tier 2 destructive operation",
            }
        )
        assert out["model_route"] == "policy_halt"
        assert "⛔" in out["final_response"]
        assert "explicit human cryptographic approval" in out["final_response"]

    def test_verify_produces_evidence_item(self):
        """verify node validates execution output and produces EvidenceItem."""
        out = verify(
            {
                "goal": "What is 2 + 2?",
                "final_response": "4",
                "plan": [{"step_id": "s1", "status": "pending"}],
            }
        )
        assert out["confidence"] == 1.0
        assert len(out["evidence"]) == 1
        assert out["plan"][0]["status"] == "completed"

    def test_reflect_bounds_loops_at_3(self):
        """reflect node limits recovery attempts to 3 and marks permanent failure."""
        err = CognitiveError(code="TRANSIENT_NETWORK", message="Timeout", recoverable=True).model_dump()
        state = {
            "errors": [err],
            "reflection_count": 3,
            "final_response": "Trying",
        }
        out = reflect(state)
        assert out["reflection_count"] == 4
        assert "Max reflections (3) exceeded" in out["scratchpad"]
        assert any(e["code"] == "PERMANENT_FAILURE" for e in out["errors"])

    def test_remember_skips_policy_halt(self):
        """remember node skips long-term memory write when execution halted."""
        with patch("graph.nodes._mem0") as mock_mem0:
            out = remember(
                {
                    "user_input": "dangerous action",
                    "final_response": "⛔ Action halted: Tier 2 requires approval",
                    "user_id": "ganesh",
                }
            )
        assert out["memory_written"] is False
        mock_mem0.return_value.add.assert_not_called()


# ── 5. Compiled 8-Node StateGraph Integration Tests ──────────────────────────


class TestCognitiveStateMachineGraph:
    def test_8_node_graph_has_all_nodes(self):
        """Compiled StateGraph contains all 8 cognitive nodes and legacy aliases."""
        saver = SqliteCheckpointSaver(db_path=":memory:")
        graph = build_jarvis_graph(checkpointer=saver)
        node_names = set(graph.get_graph().nodes.keys())

        # 8 Cognitive Nodes
        assert "perceive" in node_names
        assert "recall" in node_names
        assert "plan" in node_names
        assert "policy" in node_names
        assert "act" in node_names
        assert "verify" in node_names
        assert "reflect" in node_names
        assert "remember" in node_names

        # Legacy compatibility nodes
        assert "memory_retrieval" in node_names
        assert "policy_check" in node_names
        assert "model_router" in node_names
        assert "memory_update" in node_names

    def test_fast_path_routing_bypasses_plan(self):
        """Fast-path queries route directly to policy, bypassing planner."""
        assert _after_recall({"is_fast_path": True}) == "policy"
        assert _after_recall({"is_fast_path": False}) == "plan"

    def test_policy_routing_halts_tier3_without_token(self):
        """_after_policy halts Tier 3 operations lacking approval token."""
        state_halt = {"policy_tier": 3, "approval_required": True, "approval_id": None}
        assert _after_policy(state_halt) == "END_POLICY_HALT"

        state_approved = {
            "policy_tier": 3,
            "approval_required": True,
            "approval_id": "tok_valid",
            "approvals": {"status": "APPROVED"},
        }
        assert _after_policy(state_approved) == "act"

        state_tier0 = {"policy_tier": 0, "approval_required": False, "approval_id": None}
        assert _after_policy(state_tier0) == "act"

    def test_reflect_routing_remedies_transient_and_evidence(self):
        """_after_reflect routes recoverable errors back to plan or act."""
        state_retry_act = {
            "reflection_count": 1,
            "errors": [{"code": "TRANSIENT_NETWORK", "recoverable": True}],
        }
        assert _after_reflect(state_retry_act) == "act"

        state_replan = {
            "reflection_count": 1,
            "errors": [{"code": "INSUFFICIENT_EVIDENCE", "recoverable": True}],
        }
        assert _after_reflect(state_replan) == "plan"

        state_exceeded = {
            "reflection_count": 4,
            "errors": [{"code": "TRANSIENT_NETWORK", "recoverable": True}],
        }
        assert _after_reflect(state_exceeded) == "remember"

    def test_end_to_end_8_node_graph_execution(self):
        """End-to-end execution of a safe query through the full 8-node state machine."""
        saver = SqliteCheckpointSaver(db_path=":memory:")
        graph = build_jarvis_graph(checkpointer=saver)

        thread_id = f"th_{uuid.uuid4().hex[:8]}"
        initial_state = {
            "user_input": "Hello JARVIS, status report please.",
            "user_id": "ganesh",
            "task_type": "chat",
        }

        final_state = graph.invoke(
            initial_state,
            config={"configurable": {"thread_id": thread_id}},
        )

        # Verify cognitive cycle outputs
        assert "goal" in final_state
        assert "trace_id" in final_state
        assert "policy_tier" in final_state
        assert "final_response" in final_state
        assert "confidence" in final_state
        assert final_state["confidence"] >= 0.9
        assert len(final_state.get("evidence", [])) >= 1

        # Verify state was checkpointed in SQLite
        chk_tuple = saver.get_tuple({"configurable": {"thread_id": thread_id}})
        assert chk_tuple is not None
        assert chk_tuple.checkpoint["channel_values"]["user_id"] == "ganesh"
