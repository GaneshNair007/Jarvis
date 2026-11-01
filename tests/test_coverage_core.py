"""Comprehensive Coverage and Contract Tests for Core JARVIS Subsystems.

Verifies:
  - SQLAlchemy models, schema generation, and foreign key integrity
  - Personal Knowledge Ingestors (Notes, Email, Chat History, PDF)
  - Instant Powers security checks and error handling
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from jarvis.memory.models import (
    Base,
    User,
    Conversation,
    Message,
    Task,
    TaskStep,
    TaskEvent,
    Approval,
    AuditEvent,
    Power,
    Memory,
    Document,
    DocumentChunk,
    Embedding,
    get_db_engine,
)
from search.local_search_engine import LocalSearchEngine
from search.ingestors.notes_ingestor import NotesIngestor
from search.ingestors.email_ingestor import EmailIngestor
from search.ingestors.chat_history_ingestor import ChatHistoryIngestor
from search.ingestors.pdf_ingestor import PDFIngestor
from jarvis.powers.instant_powers import InstantPowers


def test_sqlalchemy_models_and_schema():
    """Validates complete SQLite schema generation and CRUD on all Base models."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # 1. User & Conversation & Message
    user = User(id="usr_001", username="ganesh", role="owner")
    conv = Conversation(id="cnv_001", user_id="usr_001", title="System Check")
    msg = Message(
        id="msg_001",
        conversation_id="cnv_001",
        role="user",
        content="Status report",
        model="local",
    )
    session.add_all([user, conv, msg])

    # 2. Task & TaskStep & TaskEvent
    task = Task(id="tsk_001", title="Automate CI", status="running")
    step = TaskStep(id="stp_001", task_id="tsk_001", step_number=1, action="Run pytest")
    event = TaskEvent(id="evt_001", task_id="tsk_001", event_type="started", payload="{}")
    session.add_all([task, step, event])

    # 3. Approval & AuditEvent & Power
    appr = Approval(
        id="app_001",
        task_id="tsk_001",
        power_id="PWR-001",
        action_summary="Deploy",
        payload_hash="abc",
        token="tok123",
        status="pending",
        expires_at=9999999999.0,
    )
    audit = AuditEvent(
        event_id="aud_001",
        task_id="tsk_001",
        user_id="usr_001",
        action="DEPLOY",
        tool="git",
        result="SUCCESS",
        entry_hash="hash1",
    )
    pwr = Power(
        power_id="PWR-025",
        name="Git Status",
        category="developer",
        description="Queries git status",
    )
    session.add_all([appr, audit, pwr])

    # 4. Memory & Document & Chunk & Embedding
    mem = Memory(
        id="mem_001",
        user_id="usr_001",
        layer="SEMANTIC",
        content="Prefers dark theme",
    )
    doc = Document(
        id="doc_001",
        file_path="/tmp/1.txt",
        file_name="1.txt",
        file_type="txt",
        sha256="abc12345",
    )
    chunk = DocumentChunk(
        id="chk_001",
        doc_id="doc_001",
        chunk_index=0,
        content="First chunk",
    )
    emb = Embedding(id="emb_001", source_id="chk_001", vector_dims=384)
    session.add_all([mem, doc, chunk, emb])

    session.commit()

    # Query back & verify
    queried_user = session.query(User).filter_by(id="usr_001").first()
    assert queried_user is not None
    assert queried_user.username == "ganesh"

    queried_task = session.query(Task).filter_by(id="tsk_001").first()
    assert queried_task is not None
    assert queried_task.title == "Automate CI"

    queried_audit = session.query(AuditEvent).filter_by(event_id="aud_001").first()
    assert queried_audit is not None
    assert queried_audit.action == "DEPLOY"

    session.close()

    # Also test get_db_engine fallback
    eng = get_db_engine()
    assert eng is not None


@pytest.mark.asyncio
async def test_notes_ingestor(tmp_path):
    """Validates NotesIngestor indexing into local search engine."""
    db_path = str(tmp_path / "notes_search.db")
    engine = LocalSearchEngine(db_path=db_path)
    ingestor = NotesIngestor(local_engine=engine)

    success = await ingestor.ingest_note(
        note_id="arch_001",
        title="Microservices Architecture Plan",
        body="Detailed discussion on gRPC vs REST with event bus topology.",
        tags=["architecture", "distributed"],
        notebook="Engineering",
    )
    assert success is True

    hits = engine.keyword_search("Microservices")
    assert len(hits) >= 1
    assert "Microservices Architecture Plan" in hits[0].title


@pytest.mark.asyncio
async def test_email_ingestor(tmp_path):
    """Validates EmailIngestor indexing and metadata binding."""
    db_path = str(tmp_path / "email_search.db")
    engine = LocalSearchEngine(db_path=db_path)
    ingestor = EmailIngestor(local_engine=engine)

    success = await ingestor.ingest_email(
        email_id="eml_77",
        subject="Sprint Planning Follow-up",
        body="Action items: Finalize CI test coverage and Docker compose readiness.",
        sender="lead@scaleai.io",
        recipients=["team@scaleai.io"],
        date_str="2026-10-31",
    )
    assert success is True

    hits = engine.keyword_search("Planning")
    assert len(hits) >= 1
    assert "Sprint Planning" in hits[0].title


@pytest.mark.asyncio
async def test_chat_history_ingestor(tmp_path):
    """Validates ChatHistoryIngestor turn-level conversational ingestion."""
    db_path = str(tmp_path / "chat_search.db")
    engine = LocalSearchEngine(db_path=db_path)
    ingestor = ChatHistoryIngestor(local_engine=engine)

    success = await ingestor.ingest_chat_turn(
        session_id="sess_alpha",
        turn_id="turn_04",
        user_query="What is the recommended retry policy for Redis?",
        jarvis_reply="Use exponential backoff with jitter up to 5 attempts.",
        model_used="mistral-7b",
    )
    assert success is True

    hits = engine.keyword_search("recommended retry policy")
    assert len(hits) >= 1
    assert "Chat:" in hits[0].title


@pytest.mark.asyncio
async def test_pdf_ingestor(tmp_path):
    """Validates PDFIngestor with synthetic PDF extraction and provenance."""
    import fitz

    pdf_path = tmp_path / "sample_policy.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (50, 72),
        "Autonomous Agent Safety Guidelines and Zero Trust Boundaries.",
    )
    doc.save(str(pdf_path))
    doc.close()

    db_path = str(tmp_path / "pdf_search.db")
    engine = LocalSearchEngine(db_path=db_path)
    ingestor = PDFIngestor(local_engine=engine)

    doc_ids = await ingestor.ingest_pdf(str(pdf_path))
    assert len(doc_ids) >= 1

    hits = engine.keyword_search("Autonomous Agent Safety")
    assert len(hits) >= 1


def test_instant_powers_guardrails():
    """Validates InstantPowers approval gates and launch controls."""
    # Prohibited/unregistered application
    denied = InstantPowers.launch_app("malware_installer.exe")
    assert denied["status"] == "error"
    assert "not in the allowed application list" in denied["message"]

    # Approved application simulation
    with patch("subprocess.Popen") as mock_popen:
        mock_popen.return_value = MagicMock(pid=12345)
        allowed = InstantPowers.launch_app("notepad")
        assert allowed["status"] == "success"
        assert allowed["launched"] == "notepad"

    # Clipboard error handling
    with patch("tkinter.Tk", side_effect=Exception("Display unavailable")):
        clip = InstantPowers.get_clipboard()
        assert clip["status"] == "error"
        assert "inaccessible" in clip["message"]

    # Lock workstation
    with patch("os.name", "posix"), patch("subprocess.run") as mock_sub:
        res = InstantPowers.lock_workstation()
        assert res["status"] == "success"
        mock_sub.assert_called_once()


def test_oauth_manager_lifecycle():
    """Validates OAuthManager authorization URL generation, verification, and revocation."""
    from integrations.base.oauth_manager import OAuthManager

    mgr = OAuthManager()
    with pytest.raises(ValueError):
        mgr.generate_authorization_url("unsupported", "cid", "https://redirect", ["read"])

    auth = mgr.generate_authorization_url(
        "google", "client_123", "https://app.jarvis.internal/callback", ["email", "profile"]
    )
    assert auth["provider"] == "google"
    assert "https://accounts.google.com" in auth["authorization_url"]
    state = auth["state"]

    # Verify valid state
    verified = mgr.verify_state(state)
    assert verified is not None
    assert verified["provider"] == "google"

    # Register token
    mgr.register_token("google", "tok_acc_123", refresh_token="tok_ref_123", expires_in_sec=3600)
    assert mgr.is_connected("google") is True
    assert mgr.get_token("google") == "tok_acc_123"

    # Revoke token
    assert mgr.revoke_token("google") is True
    assert mgr.is_connected("google") is False
    assert mgr.get_token("google") is None


def test_system_diagnostics_integration():
    """Validates SystemDiagnosticsIntegration lifecycle, health check, and metrics collection."""
    from integrations.system.system_diagnostics import SystemDiagnosticsIntegration
    from integrations.base.integration_health import IntegrationStatus

    diag = SystemDiagnosticsIntegration()
    assert diag.connect() is True
    health = diag.health_check()
    assert health.status in [IntegrationStatus.HEALTHY, IntegrationStatus.DEGRADED]
    assert "cpu_percent" in health.details

    powers = diag.list_powers()
    assert len(powers) >= 3

    probe = diag._execute_power_impl("system.health_probe", {})
    assert "cpu_percent" in probe
    assert "ram_percent" in probe

    disk = diag._execute_power_impl("system.disk_diagnostics", {})
    assert "partitions" in disk

    temp_clean = diag._execute_power_impl("system.clear_temp_cache", {})
    assert "bytes_reclaimed" in temp_clean

    assert diag.disconnect() is True


@pytest.mark.asyncio
async def test_searxng_client_methods():
    """Validates SearXNGClient request formatting, error fallback, and health check."""
    from search.searxng_client import SearXNGClient
    import httpx

    client = SearXNGClient(base_url="http://localhost:8888")

    # Offline health check
    healthy = await client.is_healthy()
    assert healthy is False

    # Mock response search
    mock_resp = httpx.Response(
        200,
        json={
            "results": [
                {
                    "title": "Local LLM Architectures",
                    "url": "https://example.com/llm",
                    "content": "Comprehensive guide to quantization and local deployment.",
                    "engine": "google",
                    "score": 0.95,
                }
            ]
        },
        request=httpx.Request("GET", "http://localhost:8888/search"),
    )

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        res = await client.search("Local LLM Architectures", limit=5)
        assert len(res) == 1
        assert res[0]["title"] == "Local LLM Architectures"
        assert res[0]["engine"] == "google"

    # Search with network failure fallback
    with patch("httpx.AsyncClient.get", side_effect=Exception("Connection refused")):
        res_fail = await client.search("Offline query")
        assert res_fail == []
