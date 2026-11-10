"""
Empirical Challenger Stress Test Suite for 6-Stage Execution Pipeline
Author: Milestone 1 Pipeline Challenger (teamwork_challenger)
Target: jarvis/core/orchestrator.py

Mission Areas Tested:
1. Stage 1 & Stage 5 Resilience:
   - Invalid and extreme queries ("", "   ", None, 50k chars, null bytes, unicode/emojis, SQL injection).
   - CriticAgent verdicts (PASS, PASS_WITH_WARNINGS, FAIL, RETRY) and their impact on task final_state.
   - Stage state transitions integrity across the state machine.
2. Concurrent Execution Stress:
   - 5 simultaneous queries to JarvisOrchestrator.process_user_query() with distinct conversation IDs.
   - 10 simultaneous queries under simulated load.
   - SQLite WAL concurrency, verifying zero thread corruption or race conditions.
3. Memory Persistence Failure Mode:
   - Read-only SQLite DB / database disconnection / storage write failure.
   - Assert whether pipeline handles storage failures gracefully or crashes the user response.
"""

import asyncio
import time
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from jarvis.core.orchestrator import JarvisOrchestrator
from jarvis.core.state_machine import TaskStateMachine
from jarvis.memory.conversation_service import ConversationService
from jarvis.memory.models import Base
from jarvis.memory.store import DatabaseStore
from jarvis.agents.critic import CriticReport, Verdict, CriticIssue


@pytest.fixture
def isolated_orchestrator(tmp_path):
    """Creates a fresh, isolated orchestrator with dedicated SQLite DB and memory store."""
    db_file = tmp_path / f"test_orch_{uuid.uuid4().hex[:8]}.db"
    store = DatabaseStore(db_path=db_file)

    engine = create_engine(f"sqlite:///{db_file}", echo=False)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    conv_service = ConversationService(engine=engine, session_factory=session_factory)

    orch = JarvisOrchestrator()
    orch.store = store
    orch.conversation_service = conv_service
    orch.state_machine = TaskStateMachine()
    return orch, db_file


# ==============================================================================
# SECTION 1: STAGE 1 & STAGE 5 RESILIENCE
# ==============================================================================

class TestStage1AndStage5Resilience:

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "invalid_query,desc_id",
        [
            ("", "empty_str"),
            ("   \t\n  ", "whitespace_only"),
            ("A" * 50000, "50k_payload"),
            ("Normal query \x00 with null bytes", "null_bytes"),
            ("🤖🚀💻 こんにちは 세계 🌍", "unicode_emoji"),
            ("'; DROP TABLE conversations; --", "sql_injection"),
            ("cat /etc/passwd && rm -rf /", "cmd_injection"),
        ],
        ids=["empty_str", "whitespace", "50k_payload", "null_bytes", "unicode_emoji", "sql_injection", "cmd_injection"],
    )
    async def test_stage1_query_fuzzing(self, isolated_orchestrator, invalid_query, desc_id):
        """Tests that Stage 1 safely processes diverse edge-case and boundary queries without unhandled crash."""
        orch, _ = isolated_orchestrator
        conv_id = f"fuzz_sess_{uuid.uuid4().hex[:6]}"

        mock_reply = {
            "status": "success",
            "tier": "TIER_1_LOCAL",
            "model": "ollama/llama3.1",
            "reply": f"Handled query: {desc_id}",
            "tokens_used": 10,
        }

        with patch.object(orch.router, "execute_inference", return_value=mock_reply):
            res = await orch.process_user_query(invalid_query, conversation_id=conv_id)

            assert res is not None
            assert "status" in res
            assert "stages_executed" in res
            assert "understand" in res["stages_executed"]
            # Conversation must be recorded without SQLite crash
            ctx = orch.conversation_service.get_recent_context(conv_id)
            assert len(ctx) >= 2

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        strict=True,
        reason="DEFECT: orchestrator.py:119 raises TypeError: 'NoneType' object is not subscriptable when query=None",
    )
    async def test_defect_stage1_none_query_causes_unhandled_crash(self, isolated_orchestrator):
        """Contract requirement: Passing None as query should be safely handled rather than crashing with TypeError."""
        orch, _ = isolated_orchestrator
        res = await orch.process_user_query(None, conversation_id="none_sess")
        assert res is not None
        assert res["status"] in ["REJECTED", "FAILED"]

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        strict=True,
        reason="DEFECT: orchestrator.py:345-350 sets status=COMPLETED even when CriticAgent issues Verdict.FAIL",
    )
    async def test_defect_stage5_critic_fail_verdict_ignored_by_pipeline(self, isolated_orchestrator):
        """
        Contract requirement: When CriticAgent independently issues a FAIL verdict in Stage 5,
        the task status and state machine MUST reflect the failure (status == FAILED).
        Currently, orchestrator.py:345 checks only execution_result['status'], marking the task COMPLETED.
        """
        orch, _ = isolated_orchestrator
        query = "Generate critical code for medical device"

        mock_reply = {
            "status": "success",
            "tier": "TIER_1_LOCAL",
            "model": "ollama/llama3.1",
            "reply": "Device code snippet without error checking.",
            "tokens_used": 20,
        }

        fail_report = CriticReport(
            task_id="tsk_fail_contract",
            goal=query,
            verdict=Verdict.FAIL,
            score=0.2,
            issues=[
                CriticIssue(severity="critical", category="safety", description="Missing medical fail-safes.")
            ],
            retry_recommended=False,
        )

        with patch.object(orch.router, "execute_inference", return_value=mock_reply):
            with patch.object(orch.critic, "review", return_value=fail_report):
                res = await orch.process_user_query(query, task_id="tsk_fail_contract", conversation_id="fail_sess")

                # The task MUST be marked as FAILED if Critic rejects it
                task_state = orch.state_machine.get_task("tsk_fail_contract")
                assert res["status"] == "FAILED", f"Expected FAILED, but got {res['status']}"
                assert task_state.current_status == "FAILED"

    @pytest.mark.asyncio
    async def test_stage5_critic_verdict_captured_in_stage_outputs(self, isolated_orchestrator):
        """Verifies that Stage 5 verify dictionary accurately captures critic verdict, score, and issues."""
        orch, _ = isolated_orchestrator
        query = "Write a python sorting algorithm"

        mock_reply = {
            "status": "success",
            "tier": "TIER_1_LOCAL",
            "model": "ollama/llama3.1",
            "reply": "def quicksort(arr): return arr",
            "tokens_used": 15,
        }

        with patch.object(orch.router, "execute_inference", return_value=mock_reply):
            res = await orch.process_user_query(query, conversation_id="verify_test_sess")
            assert "verify" in res["stage_outputs"]
            v = res["stage_outputs"]["verify"]
            assert "verdict" in v
            assert "score" in v
            assert "issues" in v
            assert "retry_recommended" in v

    @pytest.mark.asyncio
    async def test_state_machine_strict_transitions_all_stages(self, isolated_orchestrator):
        """Verifies that all 6 stages execute strictly valid state transitions."""
        orch, _ = isolated_orchestrator
        task_id = "tsk_seq_verify"
        query = "Explain quantum cryptography algorithms"

        mock_reply = {
            "status": "success",
            "tier": "TIER_1_LOCAL",
            "model": "ollama/llama3.1",
            "reply": "Quantum key distribution utilizes photon polarization states.",
            "tokens_used": 30,
        }

        with patch.object(orch.router, "execute_inference", return_value=mock_reply):
            res = await orch.process_user_query(query, task_id=task_id, conversation_id="seq_sess")
            assert res["status"] == "COMPLETED"

            state = orch.state_machine.get_task(task_id)
            history = [h["status"] for h in state.history]

            # Assert complete, orderly state progression
            assert history == [
                "NEW",
                "TRIAGED",
                "PLANNED",
                "POLICY_CHECK",
                "RUNNING",
                "VERIFYING",
                "COMPLETED",
            ]


# ==============================================================================
# SECTION 2: CONCURRENT EXECUTION STRESS (SQLite & State Machine)
# ==============================================================================

class TestConcurrentExecutionStress:

    @pytest.mark.asyncio
    async def test_5_simultaneous_queries_distinct_conversations(self, isolated_orchestrator):
        """
        Sends 5 simultaneous queries to JarvisOrchestrator.process_user_query()
        with distinct conversation IDs; asserts zero race conditions or corruption in SQLite.
        """
        orch, db_file = isolated_orchestrator

        queries = [
            ("Research photon entanglement in quantum optics", f"sess_conc_1_{uuid.uuid4().hex[:4]}"),
            ("Write python code for a binary search tree", f"sess_conc_2_{uuid.uuid4().hex[:4]}"),
            ("Prepare viva questions on virtual memory paging", f"sess_conc_3_{uuid.uuid4().hex[:4]}"),
            ("Find machine learning research internships", f"sess_conc_4_{uuid.uuid4().hex[:4]}"),
            ("Schedule project sync meeting for tomorrow at 10 AM", f"sess_conc_5_{uuid.uuid4().hex[:4]}"),
        ]

        def mock_inference(decision, prompt):
            time.sleep(0.05)  # Simulate small async/thread I/O delay to induce contention
            return {
                "status": "success",
                "tier": "TIER_1_LOCAL",
                "model": "ollama/llama3.1",
                "reply": f"Verified response for {decision.task_id}",
                "tokens_used": 35,
            }

        with patch.object(orch.router, "execute_inference", side_effect=mock_inference):
            tasks = [
                orch.process_user_query(
                    query=q,
                    task_id=f"tsk_c5_{idx}_{uuid.uuid4().hex[:4]}",
                    conversation_id=c_id,
                )
                for idx, (q, c_id) in enumerate(queries)
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Check that zero exceptions occurred
            for idx, r in enumerate(results):
                assert not isinstance(r, Exception), f"Query {idx} failed with exception: {r}"
                assert r["status"] == "COMPLETED"
                assert r["verdict"] in ["pass", "pass_with_warnings"]

            # Verify SQLite integrity for all 5 conversations
            for q, c_id in queries:
                turns = orch.conversation_service.get_recent_context(c_id)
                assert len(turns) == 2, f"Conversation {c_id} had {len(turns)} turns instead of 2"
                assert turns[0]["role"] == "user"
                assert turns[0]["content"] == q
                assert turns[1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_10_simultaneous_queries_high_load(self, isolated_orchestrator):
        """Stress-tests 10 simultaneous queries under simulated contention."""
        orch, _ = isolated_orchestrator
        count = 10

        def fast_mock(decision, prompt):
            time.sleep(0.02)
            return {
                "status": "success",
                "tier": "TIER_1_LOCAL",
                "model": "ollama/llama3.1",
                "reply": f"Answer for {decision.task_id}",
                "tokens_used": 20,
            }

        with patch.object(orch.router, "execute_inference", side_effect=fast_mock):
            tasks = [
                orch.process_user_query(
                    query=f"Query number {i} asking for help",
                    task_id=f"tsk_c10_{i}_{uuid.uuid4().hex[:4]}",
                    conversation_id=f"sess_c10_{i}_{uuid.uuid4().hex[:4]}",
                )
                for i in range(count)
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            failures = [r for r in results if isinstance(r, Exception)]
            assert len(failures) == 0, f"{len(failures)} concurrent queries threw exceptions: {failures}"
            assert len(results) == count
            for r in results:
                assert r["status"] == "COMPLETED"


# ==============================================================================
# SECTION 3: MEMORY PERSISTENCE FAILURE MODES
# ==============================================================================

class TestMemoryPersistenceFailureModes:

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        strict=True,
        reason="DEFECT: orchestrator.py:336 crashes with unhandled exception when ConversationService raises OperationalError, dropping user response and leaving task stranded in VERIFYING",
    )
    async def test_defect_conversation_service_storage_failure_crashes_pipeline(self, isolated_orchestrator):
        """
        Contract requirement: Storage failure in ConversationService must be handled gracefully.
        The user response computed in Stage 4 should still be returned, rather than crashing
        with an unhandled 500 error.
        """
        orch, _ = isolated_orchestrator
        query = "Explain distributed consensus algorithms like Raft"

        mock_reply = {
            "status": "success",
            "tier": "TIER_1_LOCAL",
            "model": "ollama/llama3.1",
            "reply": "Raft achieves consensus via leader election and log replication.",
            "tokens_used": 30,
        }

        with patch.object(orch.router, "execute_inference", return_value=mock_reply):
            with patch.object(
                orch.conversation_service,
                "append_message",
                side_effect=Exception("sqlite3.OperationalError: disk I/O error or readonly database"),
            ):
                # Must return response gracefully without unhandled crash
                res = await orch.process_user_query(query, conversation_id="disc_sess")
                assert res is not None
                assert "final_reply" in res
                assert "Raft" in res["final_reply"]

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        strict=True,
        reason="DEFECT: orchestrator.py:119 crashes with unhandled exception when store.save_task fails, dropping request",
    )
    async def test_defect_store_save_task_failure_crashes_pipeline(self, isolated_orchestrator):
        """
        Contract requirement: Storage failure in store.save_task() must be handled gracefully.
        """
        orch, _ = isolated_orchestrator
        query = "Analyze system architecture"

        with patch.object(
            orch.store,
            "save_task",
            side_effect=Exception("sqlite3.OperationalError: attempt to write a readonly database"),
        ):
            res = await orch.process_user_query(query, conversation_id="readonly_sess")
            assert res is not None
