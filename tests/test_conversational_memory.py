"""
Tests for Conversational Multi-Turn Memory Service and Persistence.
Validates session tracking, message sequencing, recent context windowing,
and multi-turn dialogue continuity.
"""

import time
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from jarvis.memory.models import Base
from jarvis.memory.conversation_service import ConversationService


@pytest.fixture
def memory_service():
    """Provides an isolated in-memory ConversationService for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    return ConversationService(engine=engine, session_factory=session_factory)


def test_get_or_create_conversation(memory_service):
    """Verifies conversation session initialization and idempotency."""
    conv1 = memory_service.get_or_create_conversation("session_alpha", title="Research Session")
    assert conv1["id"] == "session_alpha"
    assert conv1["title"] == "Research Session"
    assert conv1["user_id"] == "ganesh"

    # Subsequent call returns the existing conversation
    conv2 = memory_service.get_or_create_conversation("session_alpha")
    assert conv2["id"] == "session_alpha"
    assert conv2["created_at"] == conv1["created_at"]


def test_append_message_and_retrieve_context(memory_service):
    """Verifies messages can be appended and retrieved in correct chronological order."""
    session_id = "sess_multi_turn_01"

    # Turn 1
    m1 = memory_service.append_message(
        session_id,
        role="user",
        content="I am designing a distributed neural architecture called Helios.",
    )
    assert m1["role"] == "user"
    assert "Helios" in m1["content"]

    m2 = memory_service.append_message(
        session_id,
        role="assistant",
        content="Understood, Helios sounds fascinating. How can I assist with the architecture?",
        model="ollama/llama3.1",
    )
    assert m2["role"] == "assistant"

    # Turn 2
    m3 = memory_service.append_message(
        session_id,
        role="user",
        content="What is the name of the architecture I am designing?",
    )

    # Retrieve context
    history = memory_service.get_recent_context(session_id, limit=10)
    assert len(history) == 3
    assert history[0]["content"] == "I am designing a distributed neural architecture called Helios."
    assert history[1]["content"] == "Understood, Helios sounds fascinating. How can I assist with the architecture?"
    assert history[2]["content"] == "What is the name of the architecture I am designing?"


def test_recent_context_limit(memory_service):
    """Verifies that context retrieval respects the limit parameter while keeping chronological order."""
    session_id = "sess_limit_test"

    for i in range(15):
        memory_service.append_message(session_id, role="user" if i % 2 == 0 else "assistant", content=f"Message {i}")

    # Fetch last 5 messages
    recent = memory_service.get_recent_context(session_id, limit=5)
    assert len(recent) == 5
    # The last message should be Message 14, and first of the slice should be Message 10
    assert recent[0]["content"] == "Message 10"
    assert recent[-1]["content"] == "Message 14"


def test_format_context_for_prompt(memory_service):
    """Verifies transcript formatting for LLM prompt injection."""
    session_id = "sess_prompt_format"
    memory_service.append_message(session_id, role="user", content="Calculate SHA-256 for root block")
    memory_service.append_message(session_id, role="assistant", content="Hash generated: e3b0c442...")

    prompt_ctx = memory_service.format_context_for_prompt(session_id)
    assert "Recent Dialogue History:" in prompt_ctx
    assert "User: Calculate SHA-256 for root block" in prompt_ctx
    assert "Assistant: Hash generated: e3b0c442..." in prompt_ctx


def test_multi_turn_continuity_across_queries(memory_service):
    """
    Simulates consecutive queries preserving context:
    Turn 1 sets context (company name).
    Turn 2 verifies context is retrieved in history.
    """
    session_id = "sess_continuity_01"

    # First Turn
    memory_service.append_message(session_id, role="user", content="My preferred programming language is Rust.")
    memory_service.append_message(session_id, role="assistant", content="I will prioritize Rust for systems code.")

    # Second Turn
    ctx_str = memory_service.format_context_for_prompt(session_id)
    assert "Rust" in ctx_str

    memory_service.append_message(session_id, role="user", content="Write a thread-safe channel queue for it.")
    memory_service.append_message(session_id, role="assistant", content="Here is a crossbeam-channel implementation in Rust...")

    # Verify complete 4-turn dialogue state
    history = memory_service.get_recent_context(session_id)
    assert len(history) == 4
    assert history[0]["role"] == "user"
    assert "Rust" in history[0]["content"]
    assert history[3]["role"] == "assistant"
    assert "crossbeam-channel" in history[3]["content"]


def test_clear_and_list_conversations(memory_service):
    """Verifies conversation listing and clearing."""
    s1 = "sess_list_01"
    s2 = "sess_list_02"

    memory_service.append_message(s1, role="user", content="Hello s1")
    memory_service.append_message(s2, role="user", content="Hello s2")

    convs = memory_service.list_conversations()
    assert len(convs) >= 2
    session_ids = [c["id"] for c in convs]
    assert s1 in session_ids
    assert s2 in session_ids

    # Clear s1
    cleared = memory_service.clear_conversation(s1)
    assert cleared is True
    assert len(memory_service.get_recent_context(s1)) == 0
    # s2 remains intact
    assert len(memory_service.get_recent_context(s2)) == 1
