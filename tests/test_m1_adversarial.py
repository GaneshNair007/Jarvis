"""
Milestone M1 Adversarial Stress Test Suite
Author: challenger_phase1_m1_1 (Cognitive Loop Adversarial Verifier)
Purpose: Empirical stress-testing of 8-node cognitive loop, input fuzzing,
         reflection loop bounds, fast-path determinism, and SQLite checkpointer recovery.
"""

from __future__ import annotations

import os
import tempfile
import uuid
from typing import List
from unittest.mock import patch
import pytest

from jarvis.brain.state import JarvisState, InputEvent
from jarvis.brain.checkpointer import SqliteCheckpointSaver
from graph.nodes import perceive, plan, act, reflect, verify
from graph.jarvis_graph import build_jarvis_graph, _after_recall, _after_reflect


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Input Fuzzing to Perceive Node
# ═══════════════════════════════════════════════════════════════════════════════


class TestPerceiveInputFuzzing:
    """Adversarial input fuzzing for the perceive node."""

    def test_perceive_empty_string(self):
        """Empty string input should be normalized without crashing."""
        state = {"user_input": ""}
        out = perceive(state)
        assert out["user_input"] == ""
        assert out["goal"] == ""
        assert isinstance(out["input_event"], dict)
        assert out["input_event"]["text"] == ""
        assert out["is_fast_path"] is False

    def test_perceive_10k_character_payload(self):
        """Massive 10,000-character payload should not cause buffer or memory failures."""
        large_payload = "Jarvis, perform analysis. " + ("A" * 10000)
        state = {"user_input": large_payload}
        out = perceive(state)
        assert len(out["user_input"]) == len(large_payload)
        assert out["goal"] == large_payload
        assert out["input_event"]["text"] == large_payload
        assert out["is_fast_path"] is False

    def test_perceive_unicode_multilingual_and_emojis(self):
        """Stress-test diverse Unicode scripts, emojis, and control sequences."""
        fuzz_samples = [
            "مرحبا يا جارفिस! كيف حالك اليوم؟",  # Arabic RTL
            "贾维斯，请检查服务器健康状态。",  # Simplified Chinese
            "नमस्ते जार्विस, सिस्टम स्थिति क्या है?",  # Devanagari (Hindi)
            "Привет, Джарвис! Проверь память.",  # Cyrillic
            "🚀🔥💻 System check 👨‍💻👩‍🚀 with ZWJ sequences 🏳️‍🌈",  # Complex emojis
            "\x00\r\n\t\x08test\x1b[31m colored ANSI escape",  # Control & escape sequences
            "<script>alert('xss')</script>' OR '1'='1' --",  # Injection strings
        ]
        for sample in fuzz_samples:
            out = perceive({"user_input": sample})
            assert out["input_event"]["text"] == sample.strip()
            assert out["goal"] == sample.strip()

    def test_perceive_missing_keys_graceful_defaults(self):
        """Perceive node should handle empty or completely arbitrary dictionaries gracefully."""
        out = perceive({"arbitrary_unknown_key": 9999, "nested": {"a": 1}})
        assert out["user_input"] == ""
        assert out["goal"] == ""
        assert out["user_id"] == "ganesh"
        assert out["task_id"].startswith("tsk_")
        assert out["trace_id"].startswith("trc_")
        assert out["is_fast_path"] is False

    def test_perceive_messages_fallback_and_malformed_messages(self):
        """Perceive should extract user_input from messages list if user_input is missing."""
        # Valid message dict
        state1 = {"messages": [{"role": "user", "content": "hello"}]}
        assert perceive(state1)["user_input"] == "hello"

        # Message with None content
        state2 = {"messages": [{"role": "user", "content": None}]}
        assert perceive(state2)["user_input"] == ""

        # Malformed message without content key
        state3 = {"messages": [{"no_content": True}]}
        assert perceive(state3)["user_input"] == ""

    def test_perceive_non_string_user_input_raises_attribute_error(self):
        """
        EMPIRICAL FINDING: Passing a non-string object (such as a dictionary)
        directly in state['user_input'] causes unhandled AttributeError in perceive
        due to (user_input or '').strip() assumption.
        """
        with pytest.raises(AttributeError, match="'dict' object has no attribute 'strip'"):
            perceive({"user_input": {"text": "malformed_dict"}})


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Fast-Path Determinism & Routing Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestFastPathDeterminism:
    """Adversarial verification of fast-path routing and planner bypass."""

    @pytest.mark.parametrize(
        "query",
        [
            "hi",
            "hello",
            "hey",
            "ping",
            "status",
            "health",
            "system health",
            "telemetry",
            "system telemetry",
            "lock screen",
            "screenshot",
            "  STATUS  ",  # Whitespace & uppercase
            "HeLLo",
        ],
    )
    def test_fast_path_bypasses_plan_node(self, query):
        """Fast-path queries must deterministically bypass the planner in graph execution."""
        saver = SqliteCheckpointSaver(db_path=":memory:")
        graph = build_jarvis_graph(checkpointer=saver)

        thread_id = f"th_fast_{uuid.uuid4().hex[:8]}"
        config = {"configurable": {"thread_id": thread_id}}

        executed_nodes: List[str] = []
        for event in graph.stream({"user_input": query, "user_id": "ganesh"}, config=config):
            node_name = list(event.keys())[0]
            executed_nodes.append(node_name)

        # Confirm exact order: perceive -> recall -> policy -> act -> verify -> reflect -> remember
        assert "plan" not in executed_nodes, f"Plan node was unexpectedly executed for fast-path query: {query}"
        assert executed_nodes == ["perceive", "recall", "policy", "act", "verify", "reflect", "remember"]

    def test_complex_query_strictly_executes_plan_node(self):
        """Non-fast-path complex queries must route through the plan node."""
        saver = SqliteCheckpointSaver(db_path=":memory:")
        graph = build_jarvis_graph(checkpointer=saver)

        thread_id = f"th_complex_{uuid.uuid4().hex[:8]}"
        config = {"configurable": {"thread_id": thread_id}}

        executed_nodes: List[str] = []
        for event in graph.stream(
            {"user_input": "Analyze market trends and draft a research paper", "user_id": "ganesh"},
            config=config,
        ):
            node_name = list(event.keys())[0]
            executed_nodes.append(node_name)

        assert "plan" in executed_nodes, "Plan node was skipped for a complex multi-step request!"
        assert executed_nodes == ["perceive", "recall", "plan", "policy", "act", "verify", "reflect", "remember"]


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Reflection Loop Bounded Termination
# ═══════════════════════════════════════════════════════════════════════════════


class TestReflectionLoopBounds:
    """Stress-tests reflection loop bounded termination under continuous errors."""

    def test_continuous_transient_network_errors_halt_at_max_3_retries(self):
        """
        Forces continuous TRANSIENT_NETWORK failures.
        Empirically verifies:
        - Exactly 3 retry attempts are made back to the act node.
        - Reflection count reaches 4 (1 initial + 3 retries).
        - State machine halts safely without infinite recursion and routes to remember -> END.
        """
        saver = SqliteCheckpointSaver(db_path=":memory:")
        graph = build_jarvis_graph(checkpointer=saver)

        thread_id = f"th_err_transient_{uuid.uuid4().hex[:8]}"
        config = {"configurable": {"thread_id": thread_id}}

        node_visits: List[str] = []
        with patch(
            "jarvis.core.model_router.ModelRouter.execute_inference",
            side_effect=Exception("Connection timed out: 504 Gateway Timeout"),
        ):
            for event in graph.stream({"user_input": "ping", "user_id": "ganesh"}, config=config):
                node = list(event.keys())[0]
                node_visits.append(node)

        # Count node visits
        act_count = node_visits.count("act")
        reflect_count = node_visits.count("reflect")
        remember_count = node_visits.count("remember")

        # Initial run + 3 retries = 4 act executions
        assert act_count == 4, f"Expected exactly 4 act visits (1 initial + 3 retries), got {act_count}"
        # 4 reflect visits before termination
        assert reflect_count == 4, f"Expected 4 reflect evaluations, got {reflect_count}"
        # Safe termination to remember node
        assert remember_count == 1, "Graph failed to terminate at remember node"
        assert node_visits[-1] == "remember"

        # Check final state
        final_state = graph.get_state(config).values
        assert final_state["reflection_count"] == 4
        assert "Operation failed after 3 recovery attempts" in final_state["final_response"]
        assert any(e.get("code") == "PERMANENT_FAILURE" for e in final_state.get("errors", []))

    def test_continuous_insufficient_evidence_errors_halt_at_max_3_retries(self):
        """
        Forces continuous INSUFFICIENT_EVIDENCE failures.
        Empirically verifies that replanning loop halts at exactly 3 retries and routes to remember.
        """
        saver = SqliteCheckpointSaver(db_path=":memory:")
        graph = build_jarvis_graph(checkpointer=saver)

        thread_id = f"th_err_evidence_{uuid.uuid4().hex[:8]}"
        config = {"configurable": {"thread_id": thread_id}}

        node_visits: List[str] = []
        with patch(
            "jarvis.core.model_router.ModelRouter.execute_inference",
            side_effect=Exception("Insufficient evidence: missing verification document"),
        ):
            for event in graph.stream(
                {"user_input": "Verify security compliance report", "user_id": "ganesh"},
                config=config,
            ):
                node = list(event.keys())[0]
                node_visits.append(node)

        plan_count = node_visits.count("plan")
        reflect_count = node_visits.count("reflect")

        # Initial plan + 3 replans = 4 plan executions
        assert plan_count == 4, f"Expected 4 plan executions (1 initial + 3 replans), got {plan_count}"
        assert reflect_count == 4
        assert node_visits[-1] == "remember"

    def test_unrecoverable_error_immediately_halts_without_retrying(self):
        """Non-recoverable errors (e.g., POLICY_DENIED) must transition to remember with 0 retries."""
        saver = SqliteCheckpointSaver(db_path=":memory:")
        graph = build_jarvis_graph(checkpointer=saver)

        thread_id = f"th_fatal_{uuid.uuid4().hex[:8]}"
        config = {"configurable": {"thread_id": thread_id}}

        node_visits: List[str] = []
        with patch(
            "jarvis.core.model_router.ModelRouter.execute_inference",
            side_effect=Exception("Execution halted: emergency kill_switch active"),
        ):
            for event in graph.stream({"user_input": "status", "user_id": "ganesh"}, config=config):
                node = list(event.keys())[0]
                node_visits.append(node)

        # Fatal error should only invoke act and reflect once
        assert node_visits.count("act") == 1
        assert node_visits.count("reflect") == 1
        assert node_visits.count("remember") == 1

    def test_multi_turn_reflection_count_persistence_finding(self):
        """
        EMPIRICAL FINDING: On multi-turn threads, reflection_count is not reset
        by perceive(), causing subsequent turns to inherit exhausted reflection counts.
        """
        saver = SqliteCheckpointSaver(db_path=":memory:")
        graph = build_jarvis_graph(checkpointer=saver)
        thread_id = f"th_leak_{uuid.uuid4().hex[:8]}"
        config = {"configurable": {"thread_id": thread_id}}

        # Turn 1: hits max retries due to transient errors
        with patch(
            "jarvis.core.model_router.ModelRouter.execute_inference",
            side_effect=Exception("Connection timed out"),
        ):
            res1 = graph.invoke({"user_input": "turn 1 query", "user_id": "ganesh"}, config=config)

        assert res1["reflection_count"] == 4

        # Turn 2: Starts with reflection_count=4 from Turn 1.
        # When an error occurs on Turn 2, reflect() immediately increments to 5 (> 3)
        # and halts Turn 2 on the FIRST error with 0 retries.
        turn2_nodes: List[str] = []
        with patch(
            "jarvis.core.model_router.ModelRouter.execute_inference",
            side_effect=Exception("Connection timed out"),
        ):
            for event in graph.stream({"user_input": "turn 2 query", "user_id": "ganesh"}, config=config):
                turn2_nodes.append(list(event.keys())[0])

        assert turn2_nodes.count("act") == 1, (
            "Turn 2 had 0 retries because reflection_count leaked from Turn 1!"
        )
        assert turn2_nodes.count("reflect") == 1


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Checkpointer Resumption & State Recovery Across Separate Instances
# ═══════════════════════════════════════════════════════════════════════════════


class TestSqliteCheckpointerRecovery:
    """Empirical verification of checkpoint persistence and recovery across separate instances."""

    def test_process_interruption_and_state_restoration(self, tmp_path):
        """
        Simulates process crash/restart:
        1. Instance 1 executes Turn 1 and commits checkpoints to SQLite file.
        2. Instance 1 is closed and discarded.
        3. Instance 2 is initialized with a fresh connection to the same SQLite file.
        4. State is verified via get_state() on the new graph instance.
        5. Turn 2 executes cleanly on the recovered graph.
        """
        db_file = tmp_path / "jarvis_recovery_test.db"
        thread_id = f"th_persist_{uuid.uuid4().hex[:8]}"
        config = {"configurable": {"thread_id": thread_id}}

        # ── Turn 1: Process Instance 1 ───────────────────────────────────────
        saver1 = SqliteCheckpointSaver(db_path=str(db_file))
        graph1 = build_jarvis_graph(checkpointer=saver1)

        res1 = graph1.invoke(
            {"user_input": "Set my favorite editor to Neovim", "user_id": "ganesh"},
            config=config,
        )
        assert res1["user_id"] == "ganesh"
        assert "Neovim" in res1["user_input"]
        trace_id_1 = res1["trace_id"]

        # Simulate abrupt process interruption: close and destroy saver1 and graph1
        saver1._conn.close()
        del graph1
        del saver1

        # ── Recovery & Turn 2: Process Instance 2 ────────────────────────────
        saver2 = SqliteCheckpointSaver(db_path=str(db_file))
        graph2 = build_jarvis_graph(checkpointer=saver2)

        # Verify state restoration via get_state()
        snapshot = graph2.get_state(config)
        assert snapshot is not None, "get_state() returned None after process restart!"
        assert snapshot.values["user_id"] == "ganesh"
        assert "Neovim" in snapshot.values["user_input"]
        assert snapshot.values["trace_id"] == trace_id_1
        assert snapshot.values["confidence"] >= 0.9
        assert len(snapshot.values.get("evidence", [])) >= 1

        # Execute Turn 2 on the restored graph
        res2 = graph2.invoke(
            {"user_input": "status", "user_id": "ganesh"},
            config=config,
        )
        assert res2["is_fast_path"] is True

        # Verify updated snapshot has Turn 2 values
        snapshot2 = graph2.get_state(config)
        assert snapshot2.values["user_input"] == "status"

        # Check total checkpoints recorded across both instances
        history = list(saver2.list(config))
        assert len(history) >= 2, "Expected multiple checkpoints persisted across instances"

        saver2._conn.close()

    def test_sqlite_saver_wal_mode_and_table_schema(self, tmp_path):
        """Verifies WAL pragma and schema compliance with Alembic revision 0003."""
        db_file = tmp_path / "schema_check.db"
        saver = SqliteCheckpointSaver(db_path=str(db_file))

        cursor = saver._conn.cursor()
        cursor.execute("PRAGMA journal_mode;")
        journal_mode = cursor.fetchone()[0]
        assert journal_mode.lower() == "wal", f"Expected WAL mode, got {journal_mode}"

        # Check tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cursor.fetchall()}
        assert "graph_checkpoints" in tables
        assert "graph_checkpoint_writes" in tables

        saver._conn.close()
