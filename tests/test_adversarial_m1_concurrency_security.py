"""
Empirical Adversarial Test Harness: Milestone M1 Concurrency & Security Gate
Validates:
1. Multi-threaded SQLite checkpointing stress (10 concurrent threads reading/writing to graph_checkpoints,
   WAL mode validation, busy timeout, zero database locked errors, zero corruption).
2. Tier 3 dangerous operations bypass attempts (format_disk, reboot_host, deploy_production) through
   the 8-node cognitive state machine.
3. HMAC-SHA256 token forgery, payload tampering, and approval binding verification.
"""

from __future__ import annotations

import hmac
import hashlib
import threading
import time
import uuid
from pathlib import Path
import pytest

from jarvis.brain.checkpointer import SqliteCheckpointSaver
from jarvis.core.policy_gate import policy_gate
from jarvis.core.policy_engine import policy_engine
from graph.jarvis_graph import build_jarvis_graph, _after_policy
from graph.nodes import policy, act


# ── 1. SQLite Checkpointer Concurrency Stress Tests ─────────────────────────


class TestCheckpointerConcurrencyStress:
    def test_sqlite_checkpointer_10_threads_simultaneous_writes_and_reads(self, tmp_path):
        """
        Stress test: 10 concurrent threads concurrently writing and reading checkpoints
        from the same SqliteCheckpointSaver instance backed by an SQLite WAL database.
        """
        db_file = tmp_path / "stress_shared.db"
        saver = SqliteCheckpointSaver(db_path=db_file)

        # Confirm WAL pragma is active
        with saver._lock:
            cur = saver._conn.cursor()
            cur.execute("PRAGMA journal_mode;")
            journal_mode = cur.fetchone()[0].lower()
            assert journal_mode == "wal", f"Expected WAL journal mode, got {journal_mode}"

        errors = []
        thread_count = 10
        iterations_per_thread = 20

        def worker(worker_idx: int):
            try:
                for i in range(iterations_per_thread):
                    thread_id = f"th_stress_{worker_idx}"
                    cfg = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
                    checkpoint_id = f"chk_{worker_idx}_{i:03d}"
                    cp = {
                        "v": 1,
                        "id": checkpoint_id,
                        "ts": f"2026-11-01T12:{worker_idx:02d}:{i:02d}Z",
                        "channel_values": {
                            "worker_id": worker_idx,
                            "iteration": i,
                            "payload": "adversarial_stress_bytes" * 50,
                        },
                        "channel_versions": {"worker_id": 1, "iteration": i},
                        "versions_seen": {},
                    }
                    meta = {"step": i, "worker": worker_idx}
                    saver.put(cfg, cp, meta, {})

                    # Immediate concurrent read-back
                    retrieved = saver.get_tuple(cfg)
                    assert retrieved is not None, f"Failed to retrieve checkpoint for worker {worker_idx} iteration {i}"
                    assert retrieved.checkpoint["id"] == checkpoint_id
                    assert retrieved.checkpoint["channel_values"]["worker_id"] == worker_idx
                    assert retrieved.checkpoint["channel_values"]["iteration"] == i
            except Exception as exc:
                errors.append((worker_idx, exc))

        threads = [threading.Thread(target=worker, args=(w,)) for w in range(thread_count)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        saver._conn.close()
        assert len(errors) == 0, f"Encountered {len(errors)} concurrency errors: {errors}"

    def test_sqlite_checkpointer_multi_instance_concurrency(self, tmp_path):
        """
        Stress test: 10 separate SqliteCheckpointSaver instances (simulating concurrent connections)
        all reading and writing to the same SQLite WAL database file.
        """
        db_file = tmp_path / "stress_multi_conn.db"
        # Seed database tables first
        init_saver = SqliteCheckpointSaver(db_path=db_file)
        init_saver._conn.close()

        errors = []
        thread_count = 10
        iterations_per_thread = 15

        def worker(worker_idx: int):
            try:
                # Each thread opens its own separate connection
                saver = SqliteCheckpointSaver(db_path=db_file)
                for i in range(iterations_per_thread):
                    thread_id = f"th_multi_{worker_idx}"
                    cfg = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
                    checkpoint_id = f"chk_conn_{worker_idx}_{i:03d}"
                    cp = {
                        "v": 1,
                        "id": checkpoint_id,
                        "ts": "2026-11-01T12:00:00Z",
                        "channel_values": {"worker": worker_idx, "step": i},
                        "channel_versions": {"step": i},
                        "versions_seen": {},
                    }
                    meta = {"step": i, "worker": worker_idx}
                    saver.put(cfg, cp, meta, {})

                    t = saver.get_tuple(cfg)
                    assert t is not None
                    assert t.checkpoint["channel_values"]["step"] == i
                saver._conn.close()
            except Exception as exc:
                errors.append((worker_idx, exc))

        threads = [threading.Thread(target=worker, args=(w,)) for w in range(thread_count)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Encountered multi-instance concurrency errors: {errors}"


# ── 2. Policy Gate & Tier 3 Dangerous Operations Empirical Tests ────────────


class TestPolicyGateTier3Adversarial:
    def test_tier3_natural_language_halts_deterministically(self):
        """
        When user input contains space-delimited dangerous keywords ('format disk', 'drop database', 'wipe system'),
        the graph deterministically routes to END_POLICY_HALT and never executes act.
        """
        saver = SqliteCheckpointSaver(db_path=":memory:")
        graph = build_jarvis_graph(checkpointer=saver)

        dangerous_inputs = ["format disk", "drop database", "wipe system"]
        for query in dangerous_inputs:
            thread_id = f"th_danger_{uuid.uuid4().hex[:6]}"
            result = graph.invoke(
                {"user_input": query, "user_id": "ganesh"},
                config={"configurable": {"thread_id": thread_id}},
            )
            # Must halt at policy node: policy_tier == 3, approval_required == True, final_response == None
            assert result.get("policy_tier") == 3, f"Query '{query}' failed to assign Tier 3"
            assert result.get("approval_required") is True, f"Query '{query}' did not require approval"
            assert result.get("final_response") is None, f"Query '{query}' leaked to act and executed: {result.get('final_response')}"
            assert result.get("model_route") is None, f"Query '{query}' invoked model routing"

    def test_tier3_dangerous_power_names_deterministic_halt(self):
        """
        VERIFICATION OF FIX (VULN-M1-01):
        Literal dangerous power names ('format_disk', 'reboot_host', 'deploy_production')
        are normalized, classified as Tier 3 (critical), and deterministically halted at END_POLICY_HALT.
        """
        saver = SqliteCheckpointSaver(db_path=":memory:")
        graph = build_jarvis_graph(checkpointer=saver)

        # 1. Test format_disk
        res_format = graph.invoke(
            {"user_input": "format_disk", "user_id": "ganesh"},
            config={"configurable": {"thread_id": f"th_fd_{uuid.uuid4().hex[:6]}"}},
        )
        assert res_format.get("policy_tier") == 3
        assert res_format.get("approval_required") is True
        assert res_format.get("final_response") is None
        assert res_format.get("model_route") is None

        # 2. Test reboot_host
        res_reboot = graph.invoke(
            {"user_input": "reboot_host", "user_id": "ganesh"},
            config={"configurable": {"thread_id": f"th_rb_{uuid.uuid4().hex[:6]}"}},
        )
        assert res_reboot.get("policy_tier") == 3
        assert res_reboot.get("approval_required") is True
        assert res_reboot.get("final_response") is None
        assert res_reboot.get("model_route") is None

        # 3. Test deploy_production
        res_deploy = graph.invoke(
            {"user_input": "deploy_production", "user_id": "ganesh"},
            config={"configurable": {"thread_id": f"th_dp_{uuid.uuid4().hex[:6]}"}},
        )
        assert res_deploy.get("policy_tier") == 3
        assert res_deploy.get("approval_required") is True
        assert res_deploy.get("final_response") is None
        assert res_deploy.get("model_route") is None

    def test_emergency_kill_switch_deterministic_halt(self):
        """
        When emergency kill switch is activated, ANY invocation unconditionally halts
        at policy node with status DENIED and code POLICY_DENIED.
        """
        saver = SqliteCheckpointSaver(db_path=":memory:")
        graph = build_jarvis_graph(checkpointer=saver)

        policy_gate.trigger_kill_switch("Adversarial Emergency Test")
        try:
            thread_id = f"th_ks_{uuid.uuid4().hex[:6]}"
            result = graph.invoke(
                {"user_input": "Hello JARVIS, status report please.", "user_id": "ganesh"},
                config={"configurable": {"thread_id": thread_id}},
            )
            # Graph halts at policy node
            assert result.get("policy_tier") == 3
            assert result.get("approval_required") is True
            assert result.get("final_response") is None
            assert result.get("approvals", {}).get("status") == "DENIED"
            assert any(e.get("code") == "POLICY_DENIED" for e in result.get("errors", []))
        finally:
            policy_gate.reset_kill_switch()


# ── 3. Token Forgery & Payload Tampering Tests ──────────


class TestTokenForgeryAndTampering:
    def test_policy_gate_cryptographic_verification_rejects_forgery(self):
        """
        PolicyGate.verify_approval_token strictly enforces HMAC-SHA256 integrity:
        - Rejects forged signatures
        - Rejects tampered payloads
        - Rejects expired tokens
        - Rejects altered task_id or power_id
        """
        task_id = "tsk_sec_001"
        power_id = "format_disk"
        payload = {"drive": "C:", "force": True}
        payload_hash = policy_gate.hash_payload(payload)

        # 1. Genuine token verifies
        token, expiry = policy_gate.generate_approval_token(task_id, power_id, payload_hash)
        valid, reason = policy_gate.verify_approval_token(task_id, power_id, payload_hash, token)
        assert valid is True
        assert "valid and verified" in reason

        # 2. Forged signature rejected
        forged_token = f"{'a' * 64}.{int(expiry)}"
        valid, reason = policy_gate.verify_approval_token(task_id, power_id, payload_hash, forged_token)
        assert valid is False
        assert "Invalid cryptographic signature" in reason

        # 3. Tampered payload hash rejected
        tampered_hash = policy_gate.hash_payload({"drive": "D:", "force": True})
        valid, reason = policy_gate.verify_approval_token(task_id, power_id, tampered_hash, token)
        assert valid is False
        assert "Invalid cryptographic signature" in reason

        # 4. Altered power_id rejected
        valid, reason = policy_gate.verify_approval_token(task_id, "reboot_host", payload_hash, token)
        assert valid is False

        # 5. Expired token rejected
        expired_token = f"{token.split('.')[0]}.{int(time.time() - 100)}"
        valid, reason = policy_gate.verify_approval_token(task_id, power_id, payload_hash, expired_token)
        assert valid is False
        assert "expired" in reason.lower()

    def test_graph_approval_token_validation_enforces_cryptographic_verification(self):
        """
        Verifies that passing a forged approval_id into the 8-node graph deterministically
        halts at policy gate with status DENIED, while a genuine HMAC token allows execution.
        Remediates VULN-M1-02.
        """
        saver = SqliteCheckpointSaver(db_path=":memory:")
        graph = build_jarvis_graph(checkpointer=saver)

        # 1. Forged token MUST halt at END_POLICY_HALT with DENIED status
        thread_id_forged = f"th_forge_{uuid.uuid4().hex[:6]}"
        result_forged = graph.invoke(
            {
                "user_input": "format disk",  # Triggers Tier 3
                "approval_id": "completely_bogus_unverified_token_string",  # Forged non-HMAC string
                "user_id": "ganesh",
            },
            config={"configurable": {"thread_id": thread_id_forged}},
        )
        assert result_forged.get("policy_tier") == 3
        assert result_forged.get("model_route") is None, "Forged token must NOT execute act!"
        assert result_forged.get("approvals", {}).get("status") == "DENIED"
        assert any(e.get("code") == "POLICY_DENIED" for e in result_forged.get("errors", []))

        # 2. Genuine HMAC token MUST verify and execute act
        task_id = f"tsk_valid_{uuid.uuid4().hex[:6]}"
        thread_id_valid = f"th_valid_{uuid.uuid4().hex[:6]}"
        payload_hash = policy_gate.hash_payload("format disk")
        token, _ = policy_gate.generate_approval_token(task_id, "format_disk", payload_hash)

        result_valid = graph.invoke(
            {
                "task_id": task_id,
                "user_input": "format disk",
                "approval_id": token,
                "user_id": "ganesh",
            },
            config={"configurable": {"thread_id": thread_id_valid}},
        )
        assert result_valid.get("approvals", {}).get("status") == "APPROVED"
        assert result_valid.get("model_route") is not None, "Genuine token must proceed to act!"

    def test_cross_action_approval_hijacking_prevented(self):
        """
        Verifies that an approval token or approval_id generated for one power/task
        (e.g., harmless Tier 2 'send_email') CANNOT be hijacked to authorize a
        destructive Tier 3 operation ('format_disk').
        Remediates VULN-AUDIT-M1-01.
        """
        saver = SqliteCheckpointSaver(db_path=":memory:")
        graph = build_jarvis_graph(checkpointer=saver)

        # 1. Create legitimate pending approval for harmless Tier 2 power
        safe_task_id = f"tsk_safe_{uuid.uuid4().hex[:6]}"
        safe_appr = policy_gate.request_approval(
            power_id="send_email",
            task_id=safe_task_id,
            action_summary="Send harmless email",
            payload="safe content",
        )
        safe_approval_id = safe_appr["approval_id"]

        # 2. Attacker invokes graph with Tier 3 format_disk using safe_approval_id
        evil_task_id = f"tsk_evil_{uuid.uuid4().hex[:6]}"
        thread_id = f"th_hijack_{uuid.uuid4().hex[:6]}"
        res = graph.invoke(
            {
                "task_id": evil_task_id,
                "user_input": "format disk",
                "approval_id": safe_approval_id,
                "user_id": "ganesh",
            },
            config={"configurable": {"thread_id": thread_id}},
        )

        assert res.get("policy_tier") == 3
        assert res.get("approvals", {}).get("status") == "DENIED"
        assert res.get("model_route") is None
        assert any(e.get("code") == "POLICY_DENIED" for e in res.get("errors", []))

    def test_edge_and_router_truthiness_bypass_prevented(self):
        """
        Verifies that passing unverified approval_id strings without approvals dict
        deterministically halts both in edge routing and in model_router.
        Remediates VULN-AUDIT-M1-02.
        """
        from graph.jarvis_graph import _after_policy
        from graph.nodes import model_router

        # 1. Edge routing halt
        res_edge = _after_policy(
            {
                "policy_tier": 3,
                "approval_required": True,
                "approval_id": "completely_fake_unverified_token",
            }
        )
        assert res_edge == "END_POLICY_HALT"

        # 2. Node execution halt
        res_node = model_router(
            {
                "user_input": "format disk",
                "approval_required": True,
                "policy_tier": 3,
                "approval_id": "completely_fake_unverified_token",
            }
        )
        assert res_node.get("model_route") == "policy_halt"
        assert "⛔" in res_node.get("final_response", "")
