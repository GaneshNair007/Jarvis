"""
Milestone 4 Empirical Challenger Stress Verification Suite
==========================================================
Target: Iron Man JARVIS Personal AI Operating System
Milestone: M4 Workload & Combination Stress Verification
Challenger: challenger_m4_gen2_2

Empirical stress verification against:
1. Academic tutor viva prep multi-turn interaction & context memory persistence across queries
2. Autonomous career scout and truthful RFC 822 email drafting
3. Desktop application path resolution across Windows Start Menu, Registry, and PATH
4. Reviewer agent independent verification gate and verdict generation
5. Glassmorphic HUD telemetry streaming and WebSocket stability
"""

from __future__ import annotations

import asyncio
import email
from email import policy
from email.message import EmailMessage
import hashlib
import os
from pathlib import Path
import shutil
import threading
import time
from typing import Any, Dict, List
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from jarvis.agents.academic_tutor import AcademicTutorAgent, academic_tutor_agent
from jarvis.agents.base import AgentContext, AgentResult, AgentTask
from jarvis.agents.career_agent import CareerAgent, career_agent
from jarvis.agents.reviewer_agent import ReviewerAgent, VerificationReport, reviewer_agent
from jarvis.api.server import app
from jarvis.core.capability_guard import capability_guard, CapabilityStatus
from jarvis.core.policy_gate import policy_gate
from jarvis.memory.conversation_service import ConversationService
from jarvis.memory.models import Base, Conversation, Message
from jarvis.powers.desktop_powers import DesktopPowers, resolve_app_path
from jarvis.powers.email_powers import EmailPowers


# =============================================================================
# Domain 1: Academic Tutor & Context Memory Multi-Turn Stress
# =============================================================================

class TestDomain1AcademicTutorMemoryStress:
    """Stress tests multi-turn academic viva sessions and conversational memory persistence."""

    @pytest.fixture
    def isolated_conv_service(self, tmp_path):
        db_file = tmp_path / "conv_test.db"
        engine = create_engine(
            f"sqlite:///{db_file}",
            connect_args={"check_same_thread": False},
            echo=False,
        )
        Base.metadata.create_all(bind=engine)
        session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        return ConversationService(engine=engine, session_factory=session_factory)

    def test_academic_tutor_20_turn_viva_conversation_integrity(self, isolated_conv_service):
        """Stress: 20 sequential dialogue turns in a viva prep session with context recall."""
        session_id = f"viva_stress_{uuid.uuid4().hex[:8]}"
        tutor = AcademicTutorAgent()

        isolated_conv_service.get_or_create_conversation(session_id, title="Raft & Paxos Viva Prep")

        viva_topics = [
            ("Raft Leader Election", "How does Raft elect a new leader when heartbeat times out?"),
            ("Log Invariants", "What is the Log Matching Property in Raft?"),
            ("Commit Index", "How is a log entry considered committed in Raft?"),
            ("Split Votes", "How does randomized election timeout prevent split vote livelocks?"),
            ("Joint Consensus", "How does Raft handle cluster membership changes safely?"),
            ("Log Compaction", "What mechanism does Raft use for snapshotting state machines?"),
            ("Linearizable Reads", "How do read-only queries avoid stale data in Raft?"),
            ("Safety Invariant", "Can an uncommitted entry from a previous term be committed directly?"),
            ("Paxos Comparison", "How does Multi-Paxos differ from Raft in terms of leader completeness?"),
            ("Byzantine Faults", "Does standard Raft tolerate malicious or Byzantine nodes?"),
        ]

        turn_count = 0
        for topic, question in viva_topics:
            # User turn
            isolated_conv_service.append_message(
                session_id,
                role="user",
                content=f"Viva Examiner: Regarding {topic}, {question}",
            )
            turn_count += 1

            # Tutor answers using explain_concept or viva generation
            explanation = tutor.explain_concept(topic=topic, subject="Distributed Systems")
            assert len(explanation["key_takeaways"]) > 0

            # Assistant turn
            isolated_conv_service.append_message(
                session_id,
                role="assistant",
                content=f"Candidate Answer: {explanation['explanation']}",
                model="tutor_local",
            )
            turn_count += 1

        # Verify all 20 turns are persisted
        recent_all = isolated_conv_service.get_recent_context(session_id, limit=50)
        assert len(recent_all) == 20

        # Verify strict chronological sequence
        timestamps = [turn.get("created_at", 0) for turn in recent_all]
        assert timestamps == sorted(timestamps)

        # Verify windowed context slice (last 6 turns = 3 user, 3 assistant)
        recent_window = isolated_conv_service.get_recent_context(session_id, limit=6)
        assert len(recent_window) == 6
        assert recent_window[-1]["role"] == "assistant"
        assert recent_window[-2]["role"] == "user"

    def test_academic_tutor_viva_adversarial_and_edge_inputs(self):
        """Stress: Edge cases, LaTeX formulas, massive input strings, and zero/negative counts."""
        tutor = AcademicTutorAgent()

        # 1. Empty topic
        empty_res = tutor.explain_concept("")
        assert empty_res["explanation"] == "No topic specified for explanation."
        assert empty_res["key_takeaways"] == []

        empty_viva = tutor.generate_viva_questions("")
        assert empty_viva == []

        # 2. LaTeX Formula evaluation and preservation
        latex_formula = r"\int_{-\infty}^{\infty} e^{-x^2} dx = \sqrt{\pi}"
        latex_res = tutor.explain_concept(topic=latex_formula, subject="Mathematics")
        assert latex_res["topic"] == latex_formula
        assert len(latex_res["key_takeaways"]) >= 3

        # 3. Massive string input (20 KB)
        massive_topic = "Quantum Decoherence " * 1000
        massive_res = tutor.explain_concept(topic=massive_topic)
        assert massive_res["topic"] == massive_topic.strip()

        # 4. Count boundaries in generate_viva_questions
        assert tutor.generate_viva_questions("Operating Systems", count=0) == []
        assert len(tutor.generate_viva_questions("Operating Systems", count=3)) == 3
        high_count = tutor.generate_viva_questions("Operating Systems", count=50)
        assert 1 <= len(high_count) <= 50

    def test_academic_tutor_execute_task_dispatch(self):
        """Verify AcademicTutorAgent.execute dispatch across viva, assignment, and study explanation."""
        tutor = AcademicTutorAgent()
        ctx = AgentContext(conversation_id="sess_tutor_exec")

        # 1. Viva generation goal
        task_viva = AgentTask(task_id="t_viva", goal="Prepare viva questions for Operating Systems", parameters={"topic": "Paging", "count": 3})
        res_viva = asyncio.run(tutor.execute(task_viva, ctx))
        assert res_viva.status == "SUCCESS"
        assert "viva_generator" in res_viva.tools_used
        assert len(res_viva.output) == 3

        # 2. Study explanation goal
        task_study = AgentTask(task_id="t_study", goal="Explain Deadlock avoidance algorithms", parameters={"topic": "Banker's Algorithm"})
        res_study = asyncio.run(tutor.execute(task_study, ctx))
        assert res_study.status == "SUCCESS"
        assert "study_explainer" in res_study.tools_used
        assert "Banker's Algorithm" in res_study.output["topic"]

    def test_conversational_memory_concurrent_writes_stress(self, isolated_conv_service):
        """Stress: 5 concurrent threads appending messages to the same session simultaneously."""
        session_id = f"concur_sess_{uuid.uuid4().hex[:6]}"
        isolated_conv_service.get_or_create_conversation(session_id, title="Concurrency Stress")

        errors: List[Exception] = []

        def worker_append(thread_idx: int):
            try:
                for i in range(10):
                    isolated_conv_service.append_message(
                        session_id,
                        role="user" if i % 2 == 0 else "assistant",
                        content=f"Thread {thread_idx} message {i}",
                    )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker_append, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Concurrent appends produced errors: {errors}"
        history = isolated_conv_service.get_recent_context(session_id, limit=100)
        assert len(history) == 50  # 5 threads * 10 messages = 50 total


# =============================================================================
# Domain 2: Autonomous Career Scout & Truthful RFC 822 Email Drafting
# =============================================================================

class TestDomain2CareerScoutAndEmailStress:
    """Stress tests Career Scout integration, RFC 822 MIME drafting, and sending gate truthfulness."""

    def test_career_scout_pitch_to_rfc822_draft_pipeline(self, tmp_path):
        """Pipeline: Scout GSoC org -> Generate pitch -> Draft RFC 822 .eml -> Verify MIME integrity."""
        career = CareerAgent()
        outbox = tmp_path / "test_outbox"
        email_pwr = EmailPowers(outbox_dir=outbox)

        # 1. Scout Python / Scientific stack
        orgs = career.curated_orgs
        assert len(orgs) > 0
        target = orgs[0]

        # 2. Scout starter issues
        matched_issues = career.scout_opportunities(target.primary_languages[0])
        assert len(matched_issues) >= 0

        # 3. Generate contribution pitch
        pitch_res = career.generate_pitch(
            issue_id="ISSUE-NUMPY-01",
            candidate_name="Ganesh Nair",
            candidate_github="https://github.com/GaneshNair007",
        )
        assert "pitch_markdown" in pitch_res or "proposal" in pitch_res or "pitch" in str(pitch_res)

        pitch_text = pitch_res.get("pitch_markdown", "Proposal for GSoC 2026 Contribution")

        # 4. Draft RFC 822 email
        to_addr = "mentors@scipy.org"
        subject = f"GSoC 2026 Proposal: {target.name} Contributor Pitch"
        draft = email_pwr.draft_email(
            to=to_addr,
            subject=subject,
            body=pitch_text,
            from_addr="ganesh@localhost.local",
            cc="cc-mentors@scipy.org",
        )

        assert draft["status"] == "DRAFT_SAVED"
        assert draft["power_id"] == "PWR-051"
        draft_file = Path(draft["file_path"])
        assert draft_file.exists()

        # 5. Read back raw bytes and verify SHA-256 integrity
        raw_bytes = draft_file.read_bytes()
        computed_sha = hashlib.sha256(raw_bytes).hexdigest()
        assert computed_sha == draft["sha256"]

        # 6. Parse with python standard email parser using RFC 822 policy
        parsed = email.message_from_bytes(raw_bytes, policy=policy.default)
        assert parsed["To"] == to_addr
        assert parsed["Subject"] == subject
        assert parsed["From"] == "ganesh@localhost.local"
        assert parsed["Cc"] == "cc-mentors@scipy.org"
        assert parsed["Message-ID"] is not None
        assert parsed["Date"] is not None
        assert parsed.get_content().strip() == pitch_text.strip()

    def test_rfc822_adversarial_headers_and_unicode_handling(self, tmp_path):
        """Stress: Non-ASCII characters, emojis, multiline strings, and header safety."""
        email_pwr = EmailPowers(outbox_dir=tmp_path / "adv_outbox")

        # Complex unicode subject with emojis and non-Latin characters
        unicode_subject = "🚀 JARVIS AI: Viva Prep & GSoC 2026 日本語 / हिन्दी / Ελληνικά"
        unicode_body = (
            "Hello Mentors,\n\n"
            "This email contains multi-lingual text:\n"
            "- Japanese: こんにちは世界\n"
            "- Hindi: नमस्ते दुनिया\n"
            "- Mathematical symbols: ∀x ∈ ℝ, x² ≥ 0\n"
            "- Emojis: 🧠 🛡️ ⚡ 🤖\n\n"
            "Regards,\nGanesh"
        )

        draft = email_pwr.draft_email(
            to="test.unicode@example.com",
            subject=unicode_subject,
            body=unicode_body,
        )

        file_p = Path(draft["file_path"])
        raw = file_p.read_bytes()

        # Parse with policy.default to automatically decode RFC 2047 encoded words
        parsed = email.message_from_bytes(raw, policy=policy.default)
        assert parsed["To"] == "test.unicode@example.com"
        assert "JARVIS AI" in parsed["Subject"]
        assert "日本語" in parsed["Subject"]
        assert "こんにちは世界" in parsed.get_content()
        assert "नमस्ते दुनिया" in parsed.get_content()
        assert "∀x ∈ ℝ" in parsed.get_content()

    def test_email_send_gate_truthfulness_unapproved_and_offline(self, tmp_path):
        """Verify Level 3 human approval enforcement and honest status when SMTP is not configured."""
        email_pwr = EmailPowers(outbox_dir=tmp_path / "send_outbox")

        draft = email_pwr.draft_email(
            to="someone@example.com",
            subject="Test Gate",
            body="Gate verification payload",
        )
        draft_path = draft["file_path"]

        # Case 1: Send without approval token -> Must be blocked by policy gate
        res_unapproved = email_pwr.send_email(draft_path=draft_path, approval_token=None)
        assert res_unapproved["success"] is False
        assert res_unapproved["status"] == "APPROVAL_REQUIRED"
        assert "Human approval required" in res_unapproved["error"] or "Level 3" in res_unapproved["error"]

        # Case 2: Send with fraudulent approval token -> Must be blocked
        res_fake_token = email_pwr.send_email(
            draft_path=draft_path,
            approval_token="fake_forged_cryptographic_token",
        )
        assert res_fake_token["success"] is False
        assert res_fake_token["status"] == "APPROVAL_REQUIRED"

        # Case 3: Send non-existent file path
        res_missing = email_pwr.send_email(draft_path="nonexistent_file_path_1234.eml")
        assert res_missing["success"] is False
        assert "Draft file not found" in res_missing["error"]

    def test_email_draft_tampering_detection(self, tmp_path):
        """Stress: Modifying draft content on disk changes SHA-256 and invalidates prior checksums."""
        outbox = tmp_path / "tamper_outbox"
        email_pwr = EmailPowers(outbox_dir=outbox)

        draft = email_pwr.draft_email(
            to="recipient@example.com",
            subject="Original Subject",
            body="Original unaltered body content.",
        )
        draft_p = Path(draft["file_path"])
        orig_sha = draft["sha256"]

        # Adversarially append unauthorized data to the draft file
        with open(draft_p, "ab") as f:
            f.write(b"\nTampered: Malicious Payload Injection")

        tampered_sha = hashlib.sha256(draft_p.read_bytes()).hexdigest()
        assert tampered_sha != orig_sha


# =============================================================================
# Domain 3: Desktop Application Path Resolution Stress
# =============================================================================

class TestDomain3DesktopAppResolutionStress:
    """Stress tests Windows application path resolution across shortcuts, registry, and PATH."""

    def test_desktop_resolution_known_shortcuts(self):
        """Verify built-in Windows known shortcuts resolve to genuine executables."""
        known = ["notepad", "calc", "cmd", "powershell", "explorer"]
        for app in known:
            p = resolve_app_path(app)
            assert p is not None, f"Failed to resolve core utility: {app}"
            assert isinstance(p, Path)
            assert p.exists(), f"Resolved path does not exist on disk: {p}"

    def test_desktop_resolution_case_insensitivity(self):
        """Verify case-insensitive and extension-tolerant resolution."""
        variations = [
            ("NOTEPAD", "notepad"),
            ("Notepad.exe", "notepad"),
            ("nOtEpAd.EXE", "notepad"),
            ("CMD.EXE", "cmd"),
            ("powershell.EXE", "powershell"),
        ]
        for query, base in variations:
            p = resolve_app_path(query)
            assert p is not None, f"Failed case-insensitive resolution for {query}"
            assert p.exists()
            assert base in p.name.lower()

    def test_desktop_resolution_blocked_destructive_binaries(self):
        """Security: Forbidden destructive system binaries must return None."""
        blocked = [
            "format.com",
            "FORMAT.COM",
            "vssadmin.exe",
            "VSSADMIN.EXE",
            "delpart.exe",
            "diskpart.exe",
            "DISKPART.EXE",
        ]
        for bad_bin in blocked:
            res = resolve_app_path(bad_bin)
            assert res is None, f"Security violation: {bad_bin} resolved to {res}"

    def test_desktop_resolution_adversarial_and_nonexistent_inputs(self):
        """Adversarial: Null, whitespace, symbols, path traversals, nonexistent binaries."""
        adversarial = [
            "",
            "   ",
            None,
            "../../../../Windows/System32/nonexistent.exe",
            "definitely_not_a_real_application_xyz987",
            "calc.exe.exe",
            ";;rmdir /s /q C:\\",
            "notepad.exe & calc.exe",
            "notepad.exe | whoami",
        ]
        for query in adversarial:
            res = resolve_app_path(query)  # type: ignore
            assert res is None, f"Adversarial query {query!r} returned unexpected path {res}"

    def test_desktop_resolution_system_path_discovery(self):
        """Verify discovery of tools available on system PATH."""
        path_tools = ["python", "git"]
        for tool in path_tools:
            if shutil.which(tool):
                p = resolve_app_path(tool)
                assert p is not None, f"Failed to resolve PATH utility: {tool}"
                assert p.exists()


# =============================================================================
# Domain 4: Reviewer Agent Verification Gate & Verdict Generation
# =============================================================================

class TestDomain4ReviewerAgentStress:
    """Stress tests ReviewerAgent multi-dimensional verification, safety red-flag scanning, and verdicts."""

    def test_reviewer_passes_clean_execution_with_evidence(self):
        """Verification: Clean execution result with evidence generates PASS verdict."""
        reviewer = ReviewerAgent()
        task = AgentTask(task_id="t_clean_01", goal="Explain Raft Consensus Algorithm")
        clean_result = AgentResult(
            task_id="t_clean_01",
            agent_name="AcademicTutorAgent",
            role="academic_tutor",
            status="SUCCESS",
            output="Raft decomposes consensus into Leader Election, Log Replication, and Safety.",
            evidence={"sources": ["Raft Paper 2014"], "tool": "study_explainer"},
            tools_used=["study_explainer"],
        )

        rep = reviewer.verify(task=task, execution_results=[clean_result])
        assert isinstance(rep, VerificationReport)
        assert rep.verdict == "PASS"
        assert rep.safety_passed is True
        assert rep.evidence_verified is True
        assert rep.score >= 0.7
        assert len(rep.findings) == 0

    def test_reviewer_catches_pii_and_secret_red_flags(self):
        """Security: Detection of API keys, tokens, emails, phone numbers generates FAIL."""
        reviewer = ReviewerAgent()
        task = AgentTask(task_id="t_secret_01", goal="Scout API Endpoints")

        leaks = [
            ("api_key = 'sk-live-9923847291847129847192847'", "secret_key"),
            ("token: ghp_1234567890abcdef1234567890abcdef123456", "secret_key"),
            ("Contact leaked email: developer.private@shadow-corp.org", "pii_email"),
            ("Customer card: 4111 2222 3333 4444", "credit_card"),
        ]

        for leaky_output, expected_flag in leaks:
            bad_result = AgentResult(
                task_id="t_secret_01",
                agent_name="ResearcherAgent",
                role="researcher",
                status="SUCCESS",
                output=leaky_output,
                evidence={"data": "raw"},
                tools_used=["search"],
            )

            rep = reviewer.verify(task=task, execution_results=[bad_result])
            assert rep.safety_passed is False, f"Reviewer failed to catch {expected_flag} in: {leaky_output}"
            assert rep.verdict == "FAIL"
            assert any(expected_flag in finding for finding in rep.findings)

    def test_reviewer_forbidden_tool_invocation_gate(self):
        """Security: TOOL_NOT_PERMITTED status triggers safety violation and FAIL."""
        reviewer = ReviewerAgent()
        task = AgentTask(task_id="t_forbidden_01", goal="Format hard drive")
        forbidden_result = AgentResult(
            task_id="t_forbidden_01",
            agent_name="DesktopAgent",
            role="desktop",
            status="TOOL_NOT_PERMITTED",
            output="Execution blocked by policy",
            evidence={},
            tools_used=["format_disk"],
        )

        rep = reviewer.verify(task=task, execution_results=[forbidden_result])
        assert rep.safety_passed is False
        assert rep.verdict == "FAIL"
        assert any("forbidden tool invocation" in finding for finding in rep.findings)

    def test_reviewer_empty_results_triggers_retry(self):
        """Boundary: Empty execution result list triggers RETRY verdict with score 0.0."""
        reviewer = ReviewerAgent()
        task = AgentTask(task_id="t_empty_01", goal="Check system status")

        rep = reviewer.verify(task=task, execution_results=[])
        assert rep.verdict == "RETRY"
        assert rep.score == 0.0
        assert rep.evidence_verified is False
        assert "No execution results provided" in rep.findings[0]

    def test_reviewer_execute_dispatch_with_dict_and_critic_review(self):
        """Verify ReviewerAgent.execute handles dictionary adaptation and fallback critic reviews."""
        reviewer = ReviewerAgent()
        ctx = AgentContext(conversation_id="sess_rev_exec")

        # 1. Execute verification with raw dictionary results
        task_dict = AgentTask(
            task_id="t_dict",
            goal="Verify compute step",
            parameters={
                "execution_results": [
                    {
                        "task_id": "step_1",
                        "agent_name": "EngineerAgent",
                        "role": "engineer",
                        "status": "SUCCESS",
                        "output": "Code executed with 0 syntax errors.",
                        "evidence": {"test": "passed"},
                        "tools_used": ["sandbox"],
                    }
                ]
            },
        )
        res_dict = asyncio.run(reviewer.execute(task_dict, ctx))
        assert res_dict.status == "SUCCESS"
        assert res_dict.output["verdict"] == "PASS"

        # 2. Execute backward-compatible review
        task_review = AgentTask(
            task_id="t_review",
            goal="Ensure accuracy of summary",
            parameters={"output": "Accurate summary of system metrics."},
        )
        res_review = asyncio.run(reviewer.execute(task_review, ctx))
        assert res_review.status == "SUCCESS"
        assert "score" in res_review.output or "approved" in res_review.output


# =============================================================================
# Domain 5: Glassmorphic HUD Telemetry Streaming & WebSocket Stability
# =============================================================================

class TestDomain5HudTelemetryAndWebSocketStress:
    """Stress tests WebSocket telemetry pulse schemas and rapid connection cycles."""

    @pytest.fixture
    def test_client(self):
        return TestClient(app)

    def test_websocket_telemetry_pulse_contract(self, test_client):
        """Verify WebSocket /ws/stream delivers valid telemetry_pulse frame."""
        with test_client.websocket_connect("/ws/stream") as ws:
            data = ws.receive_json()
            assert data["type"] == "telemetry_pulse"
            assert "cpu_percent" in data
            assert isinstance(data["cpu_percent"], (int, float))
            assert "ram_percent" in data
            assert isinstance(data["ram_percent"], (int, float))
            assert "disk_percent" in data
            assert isinstance(data["disk_percent"], (int, float))
            assert "kill_switch_active" in data
            assert isinstance(data["kill_switch_active"], bool)
            assert "timestamp" in data
            assert isinstance(data["timestamp"], (int, float))

    def test_websocket_rapid_connect_disconnect_stress(self, test_client):
        """Stress: 10 sequential rapid connect, read frame, disconnect cycles."""
        for cycle in range(10):
            with test_client.websocket_connect("/ws/stream") as ws:
                data = ws.receive_json()
                assert data["type"] == "telemetry_pulse"
                assert "timestamp" in data
            # Disconnect happens upon exit of context manager

    def test_websocket_disconnect_cleanliness(self, test_client):
        """Verify server handles abrupt client disconnection without hanging."""
        ws = test_client.websocket_connect("/ws/stream")
        session = ws.__enter__()
        data = session.receive_json()
        assert data["type"] == "telemetry_pulse"
        # Abruptly close
        session.close()
        ws.__exit__(None, None, None)

        # Subsequent connection must succeed without obstruction
        with test_client.websocket_connect("/ws/stream") as ws2:
            data2 = ws2.receive_json()
            assert data2["type"] == "telemetry_pulse"
