"""
Empirical Adversarial Verification Suite: Milestone 1 Hardening & Fuzzing
========================================================================
Author: Milestone 1 Adversarial Challenger (teamwork_challenger)
Target: Iron Man JARVIS Personal AI Operating System

Stress & Adversarial Testing Vectors:
1. Multi-turn memory fuzzing:
   - High volume (100 messages)
   - Large payload (50KB text)
   - Unicode / Emoji / Multi-codepoint character preservation
   - SQL injection attack payload neutralization
   - Multi-threaded cross-session isolation (10 concurrent threads)
2. [BYPASS] boundary stress & conversational leak analysis:
   - Pure deterministic OS commands vs. compound conversational queries
   - Boundary vulnerability detection: "open notepad and tell me a joke"
3. Truthful email adversarial probe:
   - Missing, empty, and invalid .env configurations
   - Verification of zero canned/fabricated mock data in data/inbox
4. Smart-home freeze enforcement:
   - SmartHomePowers (8 methods) all return status="FROZEN"
   - HomeAssistantPowers (4 methods) all return status="FROZEN"
"""

from __future__ import annotations

import asyncio
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from jarvis.config import settings
from jarvis.memory.models import Base
from jarvis.memory.conversation_service import ConversationService
from jarvis.core.model_router import model_router, RoutingRequest
from jarvis.core.capability_guard import capability_guard
from jarvis.powers.email_powers import email_powers
from jarvis.powers.smart_home_powers import smart_home_powers
from jarvis.powers.homeassistant_powers import homeassistant_powers


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def isolated_memory_service(tmp_path):
    """Provides a thread-safe, isolated SQLite WAL file-backed ConversationService instance."""
    db_file = tmp_path / f"test_memory_{uuid.uuid4().hex[:6]}.db"
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
        echo=False,
    )
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA journal_mode=WAL;")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    return ConversationService(engine=engine, session_factory=session_factory)


# =============================================================================
# 1. Multi-Turn Memory Fuzzing & Concurrency Stress
# =============================================================================

class TestMemoryFuzzingAndStress:
    """Empirically stress-tests ConversationService under adversarial workloads."""

    def test_adv_memory_01_high_volume_100_turns(self, isolated_memory_service):
        """Stress: Appends 100 sequential messages to a single conversation thread.
        Verifies exact count, chronological ordering, and rolling window limits.
        """
        session_id = f"sess_vol_{uuid.uuid4().hex[:8]}"
        total_messages = 100

        for i in range(total_messages):
            role = "user" if i % 2 == 0 else "assistant"
            content = f"Turn {i:03d}: Verification of state persistence token {uuid.uuid4().hex[:6]}"
            isolated_memory_service.append_message(
                session_id,
                role=role,
                content=content,
                model="test-runner",
                tokens=15,
            )

        # 1. Verify default window (limit=10)
        recent_10 = isolated_memory_service.get_recent_context(session_id, limit=10)
        assert len(recent_10) == 10
        assert "Turn 090:" in recent_10[0]["content"]
        assert "Turn 099:" in recent_10[-1]["content"]

        # 2. Verify complete transcript retrieval without dropouts
        all_100 = isolated_memory_service.get_recent_context(session_id, limit=150)
        assert len(all_100) == total_messages
        assert "Turn 000:" in all_100[0]["content"]
        assert "Turn 099:" in all_100[-1]["content"]

        # Verify strict ascending order of turns
        for idx, msg in enumerate(all_100):
            assert f"Turn {idx:03d}:" in msg["content"]

    def test_adv_memory_02_large_payload_50kb(self, isolated_memory_service):
        """Stress: Persists and retrieves a 50KB dense payload.
        Verifies 100% data integrity without database buffer truncation.
        """
        session_id = f"sess_payload_{uuid.uuid4().hex[:8]}"
        # Generate 50,000 characters of structured text
        dense_chunk = "JARVIS_COGNITIVE_TELEMETRY_BLOCK_HASH_9928174829104829104719284719203847291048\n"
        repetitions = 50000 // len(dense_chunk) + 1
        large_payload = (dense_chunk * repetitions)[:50000]
        assert len(large_payload) == 50000

        msg = isolated_memory_service.append_message(
            session_id,
            role="user",
            content=large_payload,
            metadata={"payload_size": len(large_payload)},
        )
        assert msg["content"] == large_payload

        # Retrieve and verify exact match
        context = isolated_memory_service.get_recent_context(session_id, limit=1)
        assert len(context) == 1
        assert len(context[0]["content"]) == 50000
        assert context[0]["content"] == large_payload

    def test_adv_memory_03_unicode_and_emoji_fuzzing(self, isolated_memory_service):
        """Stress: Injects complex multi-byte UTF-8, bidirectional text, and emojis.
        Verifies safe storage and retrieval without UTF-8 decode/encode corruption.
        """
        session_id = f"sess_unicode_{uuid.uuid4().hex[:8]}"

        adversarial_strings = [
            "🚀🔥🧠🤖🛡️✨ Universal Multi-byte Emoji Set",
            "Complex family emoji: 👨‍👩‍👧‍👦 (ZWJ sequence)",
            "Japanese Kanji/Kana: 人工知能のジャービスオペレーティングシステム",
            "Arabic BiDi text: نظام تشغيل الذكاء الاصطناعي جارفيس 12345",
            "Hindi Devanagari: जार्विस व्यक्तिगत कृत्रिम बुद्धिमत्ता",
            "Russian Cyrillic: Персональная операционная система ИИ Джарвис",
            "Math Symbols: ∀x ∈ ℝ, ∃y : ∇²f(x, y) = 0 ∧ ∮ E·dl = -dΦ_B/dt",
            "Control & Zero-width: \u200bZeroWidth\u200cJoiner\u200dTest\ufeffBOM",
            "Special characters: <script>alert('xss')</script> & \" ' ` \\ /",
        ]

        for s in adversarial_strings:
            isolated_memory_service.append_message(session_id, role="user", content=s)

        history = isolated_memory_service.get_recent_context(session_id, limit=len(adversarial_strings))
        assert len(history) == len(adversarial_strings)

        for i, original in enumerate(adversarial_strings):
            retrieved = history[i]["content"]
            assert retrieved == original, f"Mismatch at index {i}: expected {original!r}, got {retrieved!r}"

    def test_adv_memory_04_sql_injection_defense(self, isolated_memory_service):
        """Stress: Injects malicious SQL syntax into all fields (session ID, role, content).
        Asserts SQLAlchemy parameterized statements prevent SQL injection and data corruption.
        """
        sql_injections = [
            "' OR 1=1 --",
            "admin' --",
            "'; DROP TABLE messages; --",
            "'; DROP TABLE conversations; --",
            "UNION SELECT 1, 'admin', 'hacked', 0, 0, 0 --",
            "1' AND (SELECT COUNT(*) FROM users) > 0 --",
            "\\'; EXEC xp_cmdshell('dir'); --",
            "\" OR \"\"=\"",
        ]

        # 1. SQL injection in conversation_id
        for sqli in sql_injections:
            conv = isolated_memory_service.get_or_create_conversation(sqli)
            assert conv["id"] == sqli

            msg = isolated_memory_service.append_message(
                sqli,
                role="user",
                content=f"Safe content for {sqli}",
            )
            assert msg["conversation_id"] == sqli

            # Verify tables still exist and query succeeds
            ctx = isolated_memory_service.get_recent_context(sqli, limit=5)
            assert len(ctx) >= 1

        # 2. SQL injection in message content
        session_id = f"sess_sqli_{uuid.uuid4().hex[:8]}"
        for sqli in sql_injections:
            isolated_memory_service.append_message(session_id, role="user", content=sqli)

        history = isolated_memory_service.get_recent_context(session_id, limit=len(sql_injections))
        assert len(history) == len(sql_injections)
        for i, sqli in enumerate(sql_injections):
            assert history[i]["content"] == sqli

    def test_adv_memory_05_concurrent_cross_session_isolation(self, isolated_memory_service):
        """Stress: 10 concurrent worker threads concurrently write 20 messages each
        to 10 distinct session IDs.
        Verifies 100% cross-session data isolation with zero message leakage or crosstalk.
        """
        thread_count = 10
        messages_per_thread = 20
        session_ids = [f"sess_worker_{i}_{uuid.uuid4().hex[:6]}" for i in range(thread_count)]
        barrier = threading.Barrier(thread_count)
        errors = []

        def worker(idx: int, s_id: str):
            try:
                barrier.wait()  # Synchronize start across all 10 threads
                for m_idx in range(messages_per_thread):
                    isolated_memory_service.append_message(
                        s_id,
                        role="user" if m_idx % 2 == 0 else "assistant",
                        content=f"Thread-{idx} Turn-{m_idx:02d} Token-{uuid.uuid4().hex[:4]}",
                    )
            except Exception as exc:
                errors.append(f"Thread-{idx} failed: {exc}")

        threads = [
            threading.Thread(target=worker, args=(i, session_ids[i]))
            for i in range(thread_count)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Concurrent workers encountered errors: {errors}"

        # Assert strict cross-session isolation
        for idx, s_id in enumerate(session_ids):
            history = isolated_memory_service.get_recent_context(s_id, limit=messages_per_thread + 5)
            assert len(history) == messages_per_thread, f"Session {s_id} expected {messages_per_thread} messages, got {len(history)}"
            # Verify every single message belongs to this thread only
            for m in history:
                assert f"Thread-{idx}" in m["content"], f"Cross-talk detected in {s_id}: message was {m['content']}"


# =============================================================================
# 2. [BYPASS] Boundary Stress & Intent Evasion Analysis
# =============================================================================

class TestBypassBoundaryStress:
    """Stress-tests the boundary between instant OS bypass and conversational understanding."""

    def test_adv_bypass_01_pure_deterministic_os_shortcuts_match(self):
        """Verifies that purely deterministic OS shortcuts cleanly trigger instant bypass."""
        valid_shortcuts = [
            "open notepad",
            "launch calc",
            "close chrome",
            "switch to explorer",
            "volume up",
            "volume down",
            "volume mute",
            "brightness 75",
            "lock screen",
            "lock workstation",
            "sleep",
            "take screenshot",
            "screenshot",
            "system health report",
            "disk usage",
            "docker ps",
            "hud telemetry",
        ]
        for cmd in valid_shortcuts:
            assert model_router.is_instant_command(cmd) is True, f"Expected '{cmd}' to be recognized as instant shortcut"

    def test_adv_bypass_02_conversational_prefix_does_not_bypass(self):
        """Verifies that conversational queries with greetings or polite framing
        do NOT bypass to instant OS command.
        """
        conversational_queries = [
            "hi jarvis open notepad and tell me a joke",
            "hello jarvis please launch calc",
            "hey can you close the window",
            "good morning jarvis what is on my schedule",
            "who are you and what can you do",
            "tell me about quantum computing",
        ]
        for q in conversational_queries:
            assert model_router.is_instant_command(q) is False, f"Conversational query '{q}' leaked into instant bypass!"

    def test_adv_bypass_03_compound_conversational_queries_boundary_vulnerability(self):
        """Adversarial Finding Verification:
        Documents the boundary where commands starting with 'open', 'launch', 'close', 'switch to'
        greedily match `[\\w\\s\\.-]+$` in INSTANT_COMMAND_PATTERNS even when conversational
        or compound clauses like 'and tell me a joke' are attached.
        """
        compound_queries = [
            "open notepad and tell me a joke",
            "launch calc and explain calculus",
            "close window and summarize todays news",
            "switch to chrome and search for quantum papers",
        ]

        # Empirical test: Observe current regex matching behavior
        # In current M1 implementation, these match because r"^open\s+[\w\s\.-]+$"
        # permits any words and spaces.
        matches = {q: model_router.is_instant_command(q) for q in compound_queries}
        # Document that compound queries starting with 'open' match the greedy regex
        assert matches["open notepad and tell me a joke"] is True, "Compound query matched greedy regex pattern"


# =============================================================================
# 3. Truthful Email Adversarial Probe
# =============================================================================

class TestEmailTruthfulnessAdversarialProbe:
    """Verifies truthful reporting of email connectivity and absence of fabricated mocks."""

    def test_adv_email_01_missing_env_returns_disconnected(self):
        """Probe: When all Gmail credentials are unset, returns DISCONNECTED with 0 opportunities."""
        capability_guard.clear_cache()
        with patch.dict(
            os.environ,
            {
                "GMAIL_USER": "",
                "GMAIL_ADDRESS": "",
                "GMAIL_APP_PASSWORD": "",
                "GMAIL_PASSWORD": "",
                "GMAIL_OAUTH_TOKEN": "",
            },
            clear=False,
        ):
            res = email_powers.scan_inbox_for_opportunities()
            assert res["status"] == "DISCONNECTED"
            assert res["connected"] is False
            assert res["opportunities_found"] == 0
            assert res["opportunities"] == []
            assert res["fabricated"] is False
            assert "not configured" in res["message"]

    def test_adv_email_02_empty_env_returns_disconnected(self):
        """Probe: When Gmail credentials are empty strings, returns DISCONNECTED."""
        capability_guard.clear_cache()
        with patch.dict(os.environ, {"GMAIL_USER": "", "GMAIL_APP_PASSWORD": ""}, clear=False):
            res = email_powers.scan_inbox_for_opportunities(query="urgent interview offer")
            assert res["status"] == "DISCONNECTED"
            assert res["opportunities"] == []
            assert res["fabricated"] is False

    def test_adv_email_03_invalid_env_truthful_rejection(self):
        """Probe: When Gmail credentials are invalid, ensures honest failure and
        ZERO synthetic or canned emails are returned. Status is strictly DISCONNECTED or NETWORK_ERROR.
        """
        capability_guard.clear_cache()
        with patch.dict(
            os.environ,
            {
                "GMAIL_USER": "invalid_user@invalid_domain.xyz",
                "GMAIL_APP_PASSWORD": "invalid_app_password_12345",
            },
            clear=False,
        ):
            with patch("imaplib.IMAP4_SSL", side_effect=Exception("Simulated connection refusal")):
                res = email_powers.scan_inbox_for_opportunities()
                assert res["status"] in ("DISCONNECTED", "NETWORK_ERROR")
                assert res["connected"] is False
                assert res["opportunities_found"] == 0
                assert res["opportunities"] == []
                assert res["fabricated"] is False

    def test_adv_email_04_data_inbox_mock_eml_files_purged(self):
        """Probe: Verifies that data/inbox contains NO fabricated mock .eml files."""
        inbox_dir = Path(settings.base_dir if hasattr(settings, "base_dir") else ".") / "data" / "inbox"
        if inbox_dir.exists():
            eml_files = list(inbox_dir.glob("*.eml"))
            forbidden_files = {
                "mail_01_deeptech_interview.eml",
                "mail_02_google_hackathon.eml",
                "mail_03_college_assignment.eml",
            }
            found = {f.name for f in eml_files}
            inter = found.intersection(forbidden_files)
            assert len(inter) == 0, f"Found purged mock files in data/inbox: {inter}"


# =============================================================================
# 4. Smart-Home Freeze Enforcement
# =============================================================================

class TestSmartHomeFreezeEnforcement:
    """Verifies that all smart-home and Home Assistant actions strictly return status='FROZEN'."""

    def test_adv_smarthome_01_all_methods_return_frozen(self):
        """Asserts all 8 device control methods of SmartHomePowers return status='FROZEN'."""
        assert getattr(settings, "enable_smart_home", False) is False

        # 1. get_all_devices
        res = smart_home_powers.get_all_devices()
        assert res["status"] == "FROZEN"
        assert res["fabricated"] is False

        # 2. get_device_status
        res = smart_home_powers.get_device_status("climate.ac")
        assert res["status"] == "FROZEN"

        # 3. control_climate
        res = smart_home_powers.control_climate(action="on", temperature=18)
        assert res["status"] == "FROZEN"

        # 4. control_media
        res = smart_home_powers.control_media(action="on", volume=50)
        assert res["status"] == "FROZEN"

        # 5. control_plug
        res = smart_home_powers.control_plug("switch.geyser", state="on")
        assert res["status"] == "FROZEN"

        # 6. control_lights
        res = smart_home_powers.control_lights("light.living_room", state="on", brightness=100)
        assert res["status"] == "FROZEN"

        # 7. activate_scene
        res = smart_home_powers.activate_scene("movie_night")
        assert res["status"] == "FROZEN"

        # 8. process_voice_command
        res = smart_home_powers.process_voice_command("turn on the living room ac")
        assert res["status"] == "FROZEN"

    def test_adv_homeassistant_02_all_methods_return_frozen(self):
        """Asserts all 4 methods of HomeAssistantPowers return status='FROZEN'."""
        assert getattr(settings, "enable_smart_home", False) is False

        # 1. check_connection
        res = homeassistant_powers.check_connection()
        assert res["status"] == "FROZEN"
        assert res["connected"] is False

        # 2. get_entity_state
        res = homeassistant_powers.get_entity_state("light.desk_lamp")
        assert res["status"] == "FROZEN"

        # 3. list_entities
        res = homeassistant_powers.list_entities()
        assert res["status"] == "FROZEN"

        # 4. call_service
        res = homeassistant_powers.call_service("light", "turn_on", {"entity_id": "light.desk_lamp"})
        assert res["status"] == "FROZEN"
        assert res["success"] is False
