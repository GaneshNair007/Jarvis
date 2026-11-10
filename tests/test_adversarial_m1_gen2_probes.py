"""
Adversarial Empirical Verification Suite for Milestone 1 (Generation 2)
========================================================================
Author: challenger_m1_gen2_1 (Empirical Adversarial Challenger)
Target: Iron Man JARVIS Personal AI Operating System

Covers Challenge Focus:
1. Empirically verify multi-turn memory continuity, session isolation, and SQLite disk persistence across process/engine restarts.
2. Adversarially probe [BYPASS] restriction:
   - Complex conversational queries ("what is python", "search for internships", "draft an email") are NOT intercepted as bypass shortcuts.
   - Pure deterministic OS commands ("open notepad", "volume up", "volume mute", "take screenshot") cleanly execute with tier="BYPASS".
   - Empirical probe of bare "mute" vs "volume mute".
   - Boundary stress-testing: greedy prefix matching on "open ..." and "launch ...".
3. End-to-end multi-turn pipeline context recall across consecutive turns.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from jarvis.core.model_router import model_router, RoutingRequest
from jarvis.core.orchestrator import JarvisOrchestrator
from jarvis.memory.models import Base
from jarvis.memory.conversation_service import ConversationService


# =============================================================================
# 1. Multi-Turn Memory Continuity, Session Isolation & SQLite Disk Persistence
# =============================================================================

class TestSqliteMultiTurnPersistenceAndIsolation:
    """Empirical verification of SQLite file persistence across engine restarts and cross-session isolation."""

    def test_sqlite_persistence_across_engine_restart(self, tmp_path):
        """Verifies that dialogue history persists to a SQLite database file on disk
        and is completely recoverable after the SQLAlchemy engine and session factory
        are disposed and re-instantiated.
        """
        db_file = tmp_path / "persistent_memory_test.db"
        db_url = f"sqlite:///{db_file}"

        # Phase 1: Initialize service and populate multi-turn dialogue
        engine_1 = create_engine(db_url, poolclass=NullPool, echo=False)
        Base.metadata.create_all(bind=engine_1)
        session_factory_1 = sessionmaker(bind=engine_1, expire_on_commit=False)
        service_1 = ConversationService(engine=engine_1, session_factory=session_factory_1)

        session_id = "sess_persist_001"
        service_1.get_or_create_conversation(session_id, title="Quantum Research Session")

        # Turn 1
        service_1.append_message(session_id, role="user", content="I am researching topological quantum memory.")
        service_1.append_message(
            session_id,
            role="assistant",
            content="Topological quantum memory uses Majorana zero modes for fault-tolerant qubits.",
            model="ollama/llama3.1",
        )

        # Turn 2
        service_1.append_message(session_id, role="user", content="What particles does it use for fault tolerance?")
        service_1.append_message(
            session_id,
            role="assistant",
            content="It uses non-Abelian anyons, specifically Majorana zero modes.",
            model="ollama/llama3.1",
        )

        # Confirm written to disk
        assert db_file.exists(), "SQLite database file must physically exist on disk"
        engine_1.dispose()

        # Phase 2: Simulate complete application restart with a fresh engine instance
        engine_2 = create_engine(db_url, poolclass=NullPool, echo=False)
        session_factory_2 = sessionmaker(bind=engine_2, expire_on_commit=False)
        service_2 = ConversationService(engine=engine_2, session_factory=session_factory_2)

        # Retrieve recovered context
        recovered = service_2.get_recent_context(session_id, limit=10)
        assert len(recovered) == 4, f"Expected 4 messages recovered from disk, got {len(recovered)}"

        # Verify exact chronological ordering and content integrity
        assert recovered[0]["role"] == "user"
        assert "topological quantum memory" in recovered[0]["content"]
        assert recovered[1]["role"] == "assistant"
        assert "Majorana zero modes" in recovered[1]["content"]
        assert recovered[2]["role"] == "user"
        assert "fault tolerance" in recovered[2]["content"]
        assert recovered[3]["role"] == "assistant"
        assert "non-Abelian anyons" in recovered[3]["content"]

        # Formatted prompt output check
        formatted = service_2.format_context_for_prompt(session_id)
        assert "Recent Dialogue History:" in formatted
        assert "User: I am researching topological quantum memory." in formatted
        assert "Assistant: Topological quantum memory" in formatted

        engine_2.dispose()

    def test_strict_cross_session_isolation(self, tmp_path):
        """Verifies that multiple concurrent sessions in the same SQLite database
        maintain 100% isolation with zero message leakage or cross-talk.
        """
        db_file = tmp_path / "session_isolation_test.db"
        engine = create_engine(f"sqlite:///{db_file}", poolclass=NullPool, echo=False)
        Base.metadata.create_all(bind=engine)
        session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        service = ConversationService(engine=engine, session_factory=session_factory)

        session_alice = "session_alice_research"
        session_bob = "session_bob_finance"

        # Alice's dialogue
        service.append_message(session_alice, role="user", content="Alice: Designing Helios distributed OS.")
        service.append_message(session_alice, role="assistant", content="Alice assistant: Helios OS acknowledged.")

        # Bob's dialogue
        service.append_message(session_bob, role="user", content="Bob: Analyzing portfolio NVDA allocation.")
        service.append_message(session_bob, role="assistant", content="Bob assistant: NVDA allocation at 25%.")

        # Verify Alice's context contains only Alice's data
        alice_history = service.get_recent_context(session_alice, limit=10)
        assert len(alice_history) == 2
        for msg in alice_history:
            assert "Bob" not in msg["content"]
            assert "NVDA" not in msg["content"]
            assert "Alice" in msg["content"]

        # Verify Bob's context contains only Bob's data
        bob_history = service.get_recent_context(session_bob, limit=10)
        assert len(bob_history) == 2
        for msg in bob_history:
            assert "Alice" not in msg["content"]
            assert "Helios" not in msg["content"]
            assert "Bob" in msg["content"]

        # Nonexistent session must return empty list
        empty_history = service.get_recent_context("nonexistent_session_id", limit=10)
        assert empty_history == []

        engine.dispose()


# =============================================================================
# 2. [BYPASS] Restriction & Deterministic OS Shortcut Probing
# =============================================================================

class TestBypassRestrictionAndRoutingEmpirical:
    """Empirically tests that complex queries are NOT bypassed, while OS controls properly bypass."""

    @pytest.mark.parametrize(
        "conversational_query",
        [
            "what is python",
            "search for internships",
            "draft an email",
            "draft an email to the hiring manager",
            "explain quantum computing and its applications",
            "how do I configure docker containers for postgres",
            "search for GSoC machine learning opportunities",
            "summarize my recent meetings",
            "what is the meaning of life",
            "hi jarvis what is on my schedule today",
            "help me solve an algorithms problem",
        ],
    )
    def test_complex_conversational_queries_do_not_bypass(self, conversational_query):
        """Adversarial Probe:
        Asserts that conversational, reasoning, search, and email requests NEVER trigger
        the instantaneous zero-LLM deterministic [BYPASS] path.
        """
        # 1. Fast match check
        is_instant = model_router.is_instant_command(conversational_query)
        assert is_instant is False, (
            f"Vulnerability: Query '{conversational_query}' was falsely flagged as instant deterministic shortcut!"
        )

        # 2. Router route decision check
        req = RoutingRequest(
            task_id="probe_" + uuid.uuid4().hex[:6],
            user_intent=conversational_query,
            sensitivity_level="low",
            task_type="conversational",
        )
        decision = model_router.route(req)
        assert decision.tier != "BYPASS", (
            f"Vulnerability: Routing decision for '{conversational_query}' returned tier=BYPASS!"
        )
        assert decision.tier in ["TIER_1_LOCAL", "TIER_2_PRIVATE", "TIER_3_CLOUD", "FALLBACK_CLOUD"]

    @pytest.mark.parametrize(
        "deterministic_os_command",
        [
            "open notepad",
            "launch calc",
            "close chrome",
            "switch to explorer",
            "volume up",
            "volume down",
            "volume mute",
            "brightness 50",
            "lock screen",
            "lock workstation",
            "sleep",
            "take screenshot",
            "screenshot",
            "system health report",
            "disk usage",
            "docker ps",
            "hud telemetry",
        ],
    )
    def test_deterministic_os_commands_trigger_bypass(self, deterministic_os_command):
        """Verifies that genuine deterministic OS commands are recognized as instant shortcuts
        and routed cleanly to tier="BYPASS".
        """
        assert model_router.is_instant_command(deterministic_os_command) is True, (
            f"Expected '{deterministic_os_command}' to be recognized as instant command"
        )

        req = RoutingRequest(
            task_id="os_probe_" + uuid.uuid4().hex[:6],
            user_intent=deterministic_os_command,
            sensitivity_level="low",
        )
        decision = model_router.route(req)
        assert decision.tier == "BYPASS"
        assert decision.provider == "deterministic"
        assert decision.selected_model == "none-deterministic-command"

    def test_bare_mute_vs_volume_mute_behavior(self):
        """Empirical Probe of 'mute':
        Demonstrates that 'volume mute' is the recognized deterministic instant shortcut,
        while bare 'mute' is routed as standard conversational input.
        """
        assert model_router.is_instant_command("volume mute") is True
        # Bare 'mute' does not match r"^volume\s+(up|down|mute|\d+)$"
        assert model_router.is_instant_command("mute") is False

    def test_adversarial_boundary_open_and_launch_greedy_matching(self):
        """Adversarial Finding Documentation:
        Empirically probes the boundary vulnerability where sentences prefixed with
        'open' or 'launch' match r"^open\\s+[\\w\\s\\.-]+$" or r"^launch\\s+[\\w\\s\\.-]+$".
        Documents which phrasing patterns leak into BYPASS and which do not.
        """
        # Greedily matches due to [\w\s\.-]+
        assert model_router.is_instant_command("open a discussion about AI") is True
        assert model_router.is_instant_command("launch an investigation into network anomalies") is True

        # Conversational framing before the command prevents bypass
        assert model_router.is_instant_command("can you open a discussion about AI") is False
        assert model_router.is_instant_command("please launch an investigation into network anomalies") is False
        assert model_router.is_instant_command("let us open a discussion") is False

    def test_orchestrator_instant_command_bypass_execution_and_persistence(self, tmp_path):
        """Verifies end-to-end execution of deterministic OS bypass in JarvisOrchestrator:
        - Executes only Stage 1 (Understand)
        - Skips Stages 2-6 (Plan, Select, Execute, Verify, Consolidate)
        - Accurately persists the interaction into ConversationService
        """
        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(bind=engine)
        session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        mem_service = ConversationService(engine=engine, session_factory=session_factory)

        orch = JarvisOrchestrator()
        orch.conversation_service = mem_service

        query = "open notepad"
        conv_id = "sess_bypass_exec"

        res = asyncio.run(orch.process_user_query(query, conversation_id=conv_id))

        assert res["status"] == "COMPLETED"
        assert res["tier"] == "BYPASS"
        assert res["provider"] == "deterministic"
        assert res["stages_executed"] == ["understand"]
        assert res["stage_outputs"]["understand"]["is_instant_shortcut"] is True
        assert res["verdict"] == "pass"

        # Verify conversation history was recorded
        history = mem_service.get_recent_context(conv_id)
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "open notepad"
        assert history[1]["role"] == "assistant"
        assert history[1]["model"] == "none-deterministic-command"


# =============================================================================
# 3. Multi-Turn Pipeline Dialogue Recall Across Turns
# =============================================================================

class TestPipelineMultiTurnDialogueFlow:
    """Verifies that consecutive queries across the 6-stage pipeline recall dialogue history."""

    def test_multi_turn_pipeline_context_accumulation(self):
        """Simulates 3 consecutive conversational turns through JarvisOrchestrator,
        confirming that each turn recalls dialogue history from all preceding turns.
        """
        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(bind=engine)
        session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        mem_service = ConversationService(engine=engine, session_factory=session_factory)

        orch = JarvisOrchestrator()
        orch.conversation_service = mem_service

        conv_id = "sess_3turn_dialogue"

        mock_replies = [
            {"status": "success", "tier": "TIER_1_LOCAL", "model": "ollama/llama3.1", "reply": "I have noted your goal is designing an Iron Man AI OS.", "tokens_used": 15},
            {"status": "success", "tier": "TIER_1_LOCAL", "model": "ollama/llama3.1", "reply": "For the OS, the 6-stage pipeline provides deterministic verification.", "tokens_used": 20},
            {"status": "success", "tier": "TIER_1_LOCAL", "model": "ollama/llama3.1", "reply": "SQLite WAL provides zero-leak local persistence for conversation memory.", "tokens_used": 25},
        ]

        # Turn 1
        with patch.object(orch.router, "execute_inference", return_value=mock_replies[0]):
            res1 = asyncio.run(orch.process_user_query("I am designing an Iron Man AI OS", conversation_id=conv_id))
            assert res1["status"] == "COMPLETED"
            assert res1["stage_outputs"]["understand"]["dialogue_history_recalled"] == 0

        # Turn 2
        with patch.object(orch.router, "execute_inference", return_value=mock_replies[1]):
            res2 = asyncio.run(orch.process_user_query("How does the pipeline ensure reliability?", conversation_id=conv_id))
            assert res2["status"] == "COMPLETED"
            # Turn 2 must recall Turn 1 (2 messages: user + assistant)
            assert res2["stage_outputs"]["understand"]["dialogue_history_recalled"] == 2

        # Turn 3
        with patch.object(orch.router, "execute_inference", return_value=mock_replies[2]):
            res3 = asyncio.run(orch.process_user_query("How does memory persistence work?", conversation_id=conv_id))
            assert res3["status"] == "COMPLETED"
            # Turn 3 must recall Turn 1 + Turn 2 (4 messages)
            assert res3["stage_outputs"]["understand"]["dialogue_history_recalled"] == 4

        # Verify final memory state has all 6 messages
        history = mem_service.get_recent_context(conv_id, limit=10)
        assert len(history) == 6
        assert history[0]["content"] == "I am designing an Iron Man AI OS"
        assert history[1]["content"] == "I have noted your goal is designing an Iron Man AI OS."
        assert history[2]["content"] == "How does the pipeline ensure reliability?"
        assert history[3]["content"] == "For the OS, the 6-stage pipeline provides deterministic verification."
        assert history[4]["content"] == "How does memory persistence work?"
        assert history[5]["content"] == "SQLite WAL provides zero-leak local persistence for conversation memory."
