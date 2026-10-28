"""
Unit & Integration Tests for Milestone 3 — Private Memory Vault & Document RAG
Verifies:
  1. 7-Layer memory nodes (facts vs hypotheses, confidence scoring)
  2. Append-only raw memory & standing directives
  3. User correction pipeline and automatic directive promotion
  4. PDF & text document ingestion with semantic chunking and SHA-256 checksums
  5. RAG query with exact page-level citations and provenance
  6. Memory Vault REST APIs (add, search, delete, correction, ingest, query, storage)
"""

import pytest
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient

from jarvis.memory.layers import memory_manager
from jarvis.memory.document_rag import document_rag
from jarvis.memory.correction_engine import correction_engine
from jarvis.memory.store import db_store
from jarvis.api.server import app

client = TestClient(app)

def test_store_and_recall_facts():
    """Verifies storing explicit user facts with 100% confidence across layers."""
    fact_id = memory_manager.add_fact(
        layer="SEMANTIC",
        content="User's primary operating system is Windows 11 Enterprise",
        metadata={"category": "system_env"}
    )
    assert fact_id.startswith("mem_")

    results = memory_manager.recall(layer="SEMANTIC", query="Windows 11")
    assert len(results) >= 1
    target = next(r for r in results if r["id"] == fact_id)
    assert target["is_hypothesis"] is False
    assert target["confidence"] == 1.0
    assert target["evidence_count"] == 1
    assert "Windows 11" in target["content"]

def test_store_and_filter_hypotheses():
    """Verifies storing inferred patterns as hypotheses with confidence thresholds."""
    hypo_id = memory_manager.add_hypothesis(
        layer="SEMANTIC",
        content="User frequently prefers dark mode interfaces after 8 PM",
        confidence=0.85,
        evidence_count=4,
        metadata={"source": "telemetry_pattern"}
    )
    assert hypo_id.startswith("mem_")

    # Recall with high confidence threshold
    high_conf = memory_manager.recall(layer="SEMANTIC", query="dark mode", min_confidence=0.8)
    assert any(r["id"] == hypo_id for r in high_conf)

    # Filter with overly high confidence threshold
    too_high = memory_manager.recall(layer="SEMANTIC", query="dark mode", min_confidence=0.95)
    assert not any(r["id"] == hypo_id for r in too_high)

def test_user_correction_promotes_to_directive():
    """Verifies that user corrections with scope='always' are promoted to DIRECTIVE memory."""
    res = correction_engine.record_correction(
        user_quote="Never run rm -rf without confirmation",
        new_instruction="Always require explicit confirmation token for recursive directory deletion",
        scope="always",
        failure_id="task_fail_99",
        old_behavior="Attempted unconfirmed directory prune"
    )

    assert res["status"] == "ACTIVE"
    assert res["promoted_layer"] == "DIRECTIVE"
    assert res["memory_node_id"] is not None

    directives = memory_manager.get_directives()
    assert any("recursive directory deletion" in d["content"] for d in directives)

def test_document_ingestion_and_chunking():
    """Verifies text ingestion, SHA-256 calculation, and idempotency."""
    sample_text = (
        "JARVIS Architecture Document.\n\n"
        "Chapter 1: The Core Foundation comprises Policy Gate and Cost Governor.\n"
        "Chapter 2: The Safe Browser uses ephemeral contexts to block SSRF attacks.\n"
        "Chapter 3: The Private Memory Vault stores 7 cognitive layers and document RAG."
    )

    doc_info = document_rag.ingest_text(sample_text, title="architecture_spec.txt")
    assert doc_info["id"].startswith("doc_")
    assert doc_info["total_chunks"] >= 1
    assert len(doc_info["sha256"]) == 64

    # Idempotent re-ingest returns the existing record
    reingest = document_rag.ingest_text(sample_text, title="architecture_spec.txt")
    assert reingest["id"] == doc_info["id"]

def test_pdf_ingestion_and_page_citations():
    """Creates a multi-page PDF, ingests it, and queries with exact page citations."""
    try:
        import fitz
    except ImportError:
        pytest.skip("PyMuPDF not installed")

    # Generate a temporary 2-page PDF
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    doc = fitz.open()
    # Page 1
    page1 = doc.new_page()
    page1.insert_text((50, 50), "Overview: Iron Man Mark 85 armor capabilities and flight dynamics.", fontsize=12)
    # Page 2
    page2 = doc.new_page()
    page2.insert_text((50, 50), "Arc Reactor Telemetry: Nanotech energy transfer efficiency reaches 98.4 percent.", fontsize=12)
    doc.save(str(tmp_path))
    doc.close()

    try:
        pdf_info = document_rag.ingest_file(tmp_path)
        assert pdf_info["total_pages"] == 2
        assert pdf_info["total_chunks"] >= 2

        # Query for Page 2 content
        query_res = document_rag.query_documents("Nanotech energy transfer efficiency")
        assert len(query_res["citations"]) >= 1

        top_citation = query_res["citations"][0]
        assert top_citation["page_number"] == 2
        assert "Nanotech energy transfer" in top_citation["excerpt"]
        assert top_citation["score"] > 0.0
        assert "Page: 2" in query_res["answer"]
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

def test_memory_vault_rest_apis():
    """Tests all Memory Vault REST endpoints via FastAPI TestClient."""
    # 1. POST /api/v1/memory/add
    add_resp = client.post("/api/v1/memory/add", json={
        "layer": "PROCEDURAL",
        "content": "To deploy docker compose: run docker compose up -d",
        "is_hypothesis": False,
        "confidence": 1.0
    })
    assert add_resp.status_code == 200
    node_id = add_resp.json()["node_id"]

    # 2. POST /api/v1/memory/search
    search_resp = client.post("/api/v1/memory/search", json={
        "query": "docker compose",
        "layer": "PROCEDURAL"
    })
    assert search_resp.status_code == 200
    assert search_resp.json()["count"] >= 1

    # 3. GET /api/v1/memory
    list_resp = client.get("/api/v1/memory?layer=PROCEDURAL")
    assert list_resp.status_code == 200
    assert any(m["id"] == node_id for m in list_resp.json()["results"])

    # 4. POST /api/v1/memory/correction
    corr_resp = client.post("/api/v1/memory/correction", json={
        "user_quote": "Prefer pytest -v over bare pytest",
        "new_instruction": "Always append -v when executing pytest command suites",
        "scope": "always"
    })
    assert corr_resp.status_code == 200
    assert corr_resp.json()["status"] == "ACTIVE"

    # 5. POST /api/v1/documents/ingest
    ingest_resp = client.post("/api/v1/documents/ingest", json={
        "content": "Secret Project PEGASUS: Autonomous drone fleet coordination protocols.",
        "title": "pegasus_protocol.txt"
    })
    assert ingest_resp.status_code == 200
    doc_id = ingest_resp.json()["id"]

    # 6. POST /api/v1/documents/query
    query_resp = client.post("/api/v1/documents/query", json={
        "query": "drone fleet coordination",
        "top_k": 3
    })
    assert query_resp.status_code == 200
    assert len(query_resp.json()["citations"]) >= 1
    assert "drone fleet" in query_resp.json()["citations"][0]["excerpt"]

    # 7. GET /api/v1/memory/storage
    storage_resp = client.get("/api/v1/memory/storage")
    assert storage_resp.status_code == 200
    storage_data = storage_resp.json()
    assert storage_data["db_size_bytes"] > 0
    assert storage_data["total_memory_nodes"] > 0
    assert storage_data["total_documents"] >= 1

    # 8. POST /api/v1/memory/delete
    del_resp = client.post("/api/v1/memory/delete", json={"node_id": node_id})
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "DELETED"
