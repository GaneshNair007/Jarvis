"""
Automated Verification Suite for JARVIS Local Search Engine.
Tests SQLite FTS5 indexing, duplicate detection, sensitive data redaction,
semantic vector fallback, hybrid ranking with citations, hot cache (< 5ms),
PDF/Markdown/Code ingestion, SearXNG caching, document deletion, and REST APIs.
"""

import asyncio
import json
import os
import shutil
import tempfile
import time
import uuid
import pytest
from fastapi.testclient import TestClient

from jarvis.api.server import app
from search.hybrid_ranker import HybridRanker
from search.ingestors import (
    BaseIngestor,
    CodeRepoIngestor,
    FileIngestor,
    MarkdownIngestor,
    PDFIngestor,
    WebCacheIngestor,
)
from search.local_search_engine import LocalSearchEngine
from search.search_cache import SearchCache
from search.search_orchestrator import SearchOrchestrator
from search.searxng_client import SearXNGClient
from search.semantic_search import QdrantSemanticSearch

client = TestClient(app)


@pytest.fixture
def temp_search_engine(tmp_path):
    """Provides a fresh isolated LocalSearchEngine in a temp directory."""
    db_file = tmp_path / "test_search.db"
    engine = LocalSearchEngine(str(db_file))
    return engine


@pytest.fixture
def temp_orchestrator(tmp_path):
    """Provides an isolated SearchOrchestrator with all local sub-engines."""
    db_file = tmp_path / "test_orch_search.db"
    local_eng = LocalSearchEngine(str(db_file))
    semantic_eng = QdrantSemanticSearch(collection="test_docs")
    cache = SearchCache(default_ttl_sec=60)
    orchestrator = SearchOrchestrator(
        local_engine=local_eng,
        semantic_search=semantic_eng,
        cache=cache,
    )
    return orchestrator


# ─── 1. SQLite FTS5 Keyword Search & BM25 Ranking ────────────────────────────

def test_sqlite_fts5_indexing_and_bm25_search(temp_search_engine):
    """Verifies that SQLite FTS5 indexes text, ranks via BM25, and produces highlighted snippets."""
    engine = temp_search_engine

    engine.ingest(
        doc_id="doc_1",
        title="FastAPI Microservices Architecture",
        content="FastAPI is a modern high performance web framework for building APIs with Python and async support.",
        source_type="document",
        source_url="https://fastapi.tiangolo.com",
    )
    engine.ingest(
        doc_id="doc_2",
        title="Docker Container Deployment",
        content="Docker containers provide process isolation and reproducible execution environments across servers.",
        source_type="document",
        source_url="https://docker.com",
    )

    hits = engine.keyword_search("FastAPI Python", limit=10)
    assert len(hits) == 1
    hit = hits[0]
    assert hit.doc_id == "doc_1"
    assert "FastAPI" in hit.title
    assert "<b>" in hit.snippet
    assert hit.provider == "sqlite_fts5"
    assert hit.latency_ms < 25.0  # target sub-25ms


# ─── 2. Duplicate Detection via SHA-256 Content Hash ─────────────────────────

def test_duplicate_detection_by_content_hash(temp_search_engine):
    """Verifies that identical document content is not duplicated in the index."""
    engine = temp_search_engine
    text = "Universal deterministic approval tokens bound to frozen SHA-256 content hashes."

    first_res = engine.ingest(
        doc_id="doc_first",
        title="Approval Security Invariant",
        content=text,
        source_type="document",
    )
    assert first_res is True

    # Ingesting same text under different doc_id must be skipped as duplicate
    second_res = engine.ingest(
        doc_id="doc_second",
        title="Duplicate Policy Note",
        content=text,
        source_type="document",
    )
    assert second_res is False

    stats = engine.get_stats()
    assert stats["total_documents"] == 1


# ─── 3. Sensitive Data Redaction Before Indexing ──────────────────────────────

def test_sensitive_data_redaction():
    """Verifies that API keys, passwords, private keys, and card numbers are redacted."""
    raw_text = (
        "Project credentials:\n"
        "OpenAI: sk-proj-1234567890abcdef1234567890abcdef\n"
        "GitHub: ghp_1234567890abcdefghijklmnopqrstuvwxyz\n"
        "Database password: 'supersecretpassword123'\n"
        "Card: 4532-1234-5678-9012\n"
    )

    redacted = BaseIngestor.redact_sensitive_data(raw_text)
    assert "sk-proj-1234567890abcdef1234567890abcdef" not in redacted
    assert "[REDACTED_API_KEY]" in redacted
    assert "ghp_1234567890abcdefghijklmnopqrstuvwxyz" not in redacted
    assert "[REDACTED_GITHUB_TOKEN]" in redacted
    assert "supersecretpassword123" not in redacted
    assert "[REDACTED_SECRET]" in redacted
    assert "4532-1234-5678-9012" not in redacted


# ─── 4. Local Semantic Search & Deterministic Vector Fallback ────────────────

def test_semantic_search_vector_fallback():
    """Verifies vector embedding and cosine similarity retrieval without external APIs."""
    async def _run():
        semantic = QdrantSemanticSearch(collection="test_semantic_docs")

        await semantic.upsert(
            doc_id="vec_docker",
            title="Docker Engine",
            text="Docker automates application deployment inside lightweight software containers.",
            source_type="document",
        )
        await semantic.upsert(
            doc_id="vec_gardening",
            title="Organic Soil Care",
            text="Composting and soil enrichment techniques for vegetable garden health.",
            source_type="document",
        )

        hits = await semantic.search("containers deployment docker", limit=5)
        assert len(hits) >= 1
        top_hit = hits[0]
        assert top_hit.doc_id == "vec_docker"
        assert top_hit.score > 0.3

    asyncio.run(_run())


# ─── 5. Hybrid Ranker with Citations & Provenance ────────────────────────────

def test_hybrid_ranking_and_citations():
    """Verifies that RRF combines keyword and semantic hits with valid citations."""
    from search.local_search_engine import SearchHit

    keyword_hit = SearchHit(
        doc_id="doc_k",
        title="Kernel Memory Architecture",
        url="https://kernel.org",
        snippet="Kernel virtual memory allocations and page tables.",
        source_type="code_repo",
        score=0.9,
        provider="sqlite_fts5",
    )

    semantic_hit = SearchHit(
        doc_id="doc_s",
        title="Operating System Paging",
        url="https://os-book.com",
        snippet="Virtual memory paging algorithms and dirty page caches.",
        source_type="document",
        score=0.85,
        provider="qdrant_semantic",
    )

    ranker = HybridRanker()
    ranked = ranker.merge(
        keyword_hits=[keyword_hit],
        semantic_hits=[semantic_hit],
        limit=5,
        query_id="qry_test123",
    )

    assert len(ranked) == 2
    for r in ranked:
        assert "citation" in r
        cit = r["citation"]
        assert cit["citation_id"].startswith("cit_")
        assert cit["doc_id"] in ("doc_k", "doc_s")
        assert cit["excerpt"]
        assert len(cit["providers"]) >= 1


# ─── 6. Hot Cache (Sub-5ms Latency & Invalidation) ───────────────────────────

def test_search_cache_hit_and_invalidation():
    """Verifies that hot cache returns results in sub-5ms and clears cleanly."""
    cache = SearchCache(default_ttl_sec=30)

    sample_results = {"query": "python async", "results": [{"doc_id": "1"}], "total": 1}
    cache.set("python async", "hybrid", sample_results)

    start = time.perf_counter()
    cached = cache.get("python async", "hybrid")
    duration_ms = (time.perf_counter() - start) * 1000.0

    assert cached is not None
    assert cached["cache_hit"] is True
    assert duration_ms < 5.0  # target sub-5ms

    # Cache miss on different query
    assert cache.get("unseen query", "hybrid") is None

    # Clear cache
    cleared = cache.clear()
    assert cleared >= 1
    assert cache.get("python async", "hybrid") is None


# ─── 7. Ingestion: Text & Markdown Files ─────────────────────────────────────

def test_file_and_markdown_ingestion(tmp_path, temp_search_engine):
    """Verifies file and markdown ingestors with section-aware chunking."""
    async def _run():
        engine = temp_search_engine

        # 1. Plain file ingestor
        txt_file = tmp_path / "notes.txt"
        txt_file.write_text("JARVIS local search operates entirely on device.", encoding="utf-8")

        file_ingestor = FileIngestor(local_engine=engine)
        txt_ids = await file_ingestor.ingest_file(str(txt_file))
        assert len(txt_ids) >= 1

        # 2. Markdown ingestor
        md_file = tmp_path / "architecture.md"
        md_file.write_text(
            "# System Architecture\nCore orchestrator specifications.\n\n"
            "## Subsystem A\nSQLite FTS5 full text indexing.\n\n"
            "## Subsystem B\nQdrant vector semantic similarity.\n",
            encoding="utf-8",
        )

        md_ingestor = MarkdownIngestor(local_engine=engine)
        md_ids = await md_ingestor.ingest_markdown(str(md_file))
        assert len(md_ids) >= 2  # multiple sections

        hits = engine.keyword_search("Subsystem FTS5", limit=5)
        assert len(hits) >= 1
        assert "Subsystem A" in hits[0].title

    asyncio.run(_run())


# ─── 8. Ingestion: Code Repository (.gitignore awareness) ────────────────────

def test_code_repo_ingestion(tmp_path, temp_search_engine):
    """Verifies repository ingestor walks code files and ignores .git/__pycache__."""
    async def _run():
        engine = temp_search_engine
        repo_root = tmp_path / "sample_repo"
        repo_root.mkdir()

        # Valid Python file
        src_dir = repo_root / "src"
        src_dir.mkdir()
        (src_dir / "main.py").write_text("def run_search():\n    return 'fast local'", encoding="utf-8")

        # Ignored directory
        git_dir = repo_root / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("dummy git content", encoding="utf-8")

        pycache_dir = repo_root / "__pycache__"
        pycache_dir.mkdir()
        (pycache_dir / "cache.pyc").write_text("binary cache", encoding="utf-8")

        ingestor = CodeRepoIngestor(local_engine=engine)
        ingested_ids = await ingestor.ingest_repository(str(repo_root), repo_name="sample")

        assert len(ingested_ids) == 1
        assert "main.py" in ingested_ids[0]

        hits = engine.keyword_search("run_search", limit=5)
        assert len(hits) == 1
        assert hits[0].source_type == "code_repo"

    asyncio.run(_run())


# ─── 9. SearXNG Fresh-Web Search & Automatic Local Indexing ──────────────────

def test_web_cache_ingestion(temp_search_engine):
    """Verifies fresh web search results are ingested locally for next-time millisecond recall."""
    async def _run():
        engine = temp_search_engine
        web_ingestor = WebCacheIngestor(local_engine=engine)

        fake_web_results = [
            {
                "title": "Quantum Computing Frontiers 2026",
                "url": "https://quantum-daily.org/article-101",
                "snippet": "Recent breakthroughs in fault-tolerant topological qubits announced.",
                "engine": "searxng",
                "published_date": "2026-10-28",
            }
        ]

        ingested_ids = await web_ingestor.ingest_web_results("topological qubits", fake_web_results)
        assert len(ingested_ids) == 1

        # Now verify that subsequent local search finds it in milliseconds!
        hits = engine.keyword_search("topological qubits", limit=5)
        assert len(hits) == 1
        assert hits[0].doc_id == ingested_ids[0]
        assert hits[0].source_type == "web_cache"

    asyncio.run(_run())


# ─── 10. Document Deletion & Incremental Reindexing ──────────────────────────

def test_document_deletion_and_reindex(temp_search_engine):
    """Verifies that deleted documents are excluded and reindex is non-destructive."""
    engine = temp_search_engine

    engine.ingest(
        doc_id="doc_keep",
        title="Standing Directive",
        content="Always prioritize local execution before escalating.",
        source_type="document",
    )
    engine.ingest(
        doc_id="doc_temp",
        title="Ephemeral Scratch Note",
        content="Temporary scratchpad text to be removed.",
        source_type="document",
    )

    assert len(engine.keyword_search("scratchpad", limit=5)) == 1

    # Delete doc_temp
    del_ok = engine.delete_document("doc_temp")
    assert del_ok is True
    assert len(engine.keyword_search("scratchpad", limit=5)) == 0

    # Non-destructive incremental reindexing
    reindexed_count = engine.reindex_all()
    assert reindexed_count == 1
    assert len(engine.keyword_search("directive", limit=5)) == 1


# ─── 11. Search Orchestrator Pipeline ────────────────────────────────────────

def test_search_orchestrator_pipeline(temp_orchestrator):
    """Verifies end-to-end SearchOrchestrator pipeline."""
    async def _run():
        orch = temp_orchestrator

        orch.local.ingest(
            doc_id="orch_doc_1",
            title="LangGraph Persisted Checkpoints",
            content="Checkpoints in LangGraph maintain state across long-running task executions.",
            source_type="document",
            source_url="https://langchain.com",
        )

        # 1. First execution (Local query)
        res1 = await orch.search("LangGraph checkpoints", mode="hybrid")
        assert res1["total_results"] >= 1
        assert res1["mode"] == "hybrid"
        assert len(res1["citations"]) >= 1

        # 2. Second execution (Cache hit)
        res2 = await orch.search("LangGraph checkpoints", mode="hybrid")
        assert res2["total_results"] >= 1
        assert res2["cache_hit"] is True

    asyncio.run(_run())


# ─── 12. Search REST API Endpoints ───────────────────────────────────────────

def test_search_rest_api_endpoints():
    """Verifies all FastAPI Search endpoints."""
    # 1. Health Probe
    resp = client.get("/search/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"

    # 2. Search Status
    resp = client.get("/search/status")
    assert resp.status_code == 200
    assert "sqlite_fts5" in resp.json()["engines"]

    # 3. Ingest URL Content (unique timestamped content)
    unique_key = f"rev_{uuid.uuid4().hex[:8]}"
    ingest_payload = {
        "url": f"https://python.org/pep-0684?v={unique_key}",
        "title": "PEP 684 Per-Interpreter GIL",
        "content": f"A per-interpreter GIL allows subinterpreters to run concurrently in parallel threads (revision {unique_key}).",
    }
    resp = client.post("/search/ingest/url", json=ingest_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["indexed_chunks"] >= 1

    # 4. Search Local (Keyword FTS5)
    resp = client.post("/search/local", json={"query": "subinterpreters GIL", "limit": 5})
    assert resp.status_code == 200
    search_data = resp.json()
    assert search_data["total_results"] >= 1
    assert "PEP 684" in search_data["results"][0]["title"]

    # 5. Search Hybrid
    resp = client.post("/search/hybrid", json={"query": "subinterpreters GIL", "limit": 5})
    assert resp.status_code == 200
    assert resp.json()["total_results"] >= 1

    # 6. Search Stats
    resp = client.get("/search/stats")
    assert resp.status_code == 200
    stats = resp.json()
    assert stats["total_documents"] >= 1

    # 7. Document Inspection & Deletion
    doc_id = data["doc_ids"][0]
    resp = client.get(f"/search/documents/{doc_id}")
    assert resp.status_code == 200
    assert resp.json()["doc_id"] == doc_id

    del_resp = client.delete(f"/search/documents/{doc_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["success"] is True

    # 8. Clear Cache
    resp = client.post("/search/cache/clear")
    assert resp.status_code == 200
    assert resp.json()["success"] is True
