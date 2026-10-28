"""
JARVIS Local Search API Routes.
Provides REST endpoints for keyword, semantic, hybrid, and research search,
document ingestion, reindexing, cache management, and index health.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from jarvis.config import settings
from search import search_orchestrator
from search.ingestors import (
    BrowserPageIngestor,
    CodeRepoIngestor,
    FileIngestor,
    MarkdownIngestor,
    PDFIngestor,
)

router = APIRouter(prefix="", tags=["Local Search"])


# ─── Request / Response Schemas ──────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str = Field(..., description="Search query string")
    limit: int = Field(default=10, ge=1, le=100)
    source_type: Optional[str] = Field(default=None, description="Optional filter by source type")
    refresh_web: bool = Field(default=False, description="Whether to query SearXNG if local results are insufficient")
    user_id: str = Field(default_factory=lambda: settings.jarvis_user_id)


class IngestFileRequest(BaseModel):
    file_path: str = Field(..., description="Absolute or relative path to file")
    title: Optional[str] = None
    source_type: str = Field(default="document")


class IngestFolderRequest(BaseModel):
    folder_path: str = Field(..., description="Path to folder to index")
    recursive: bool = Field(default=True)
    max_files: int = Field(default=100)


class IngestPDFRequest(BaseModel):
    file_path: str = Field(..., description="Path to PDF file")
    title: Optional[str] = None


class IngestURLRequest(BaseModel):
    url: str = Field(..., description="Web URL to index")
    title: Optional[str] = None
    content: str = Field(..., description="Page text content or HTML")


class IngestRepoRequest(BaseModel):
    repo_path: str = Field(..., description="Path to code repository root")
    repo_name: Optional[str] = None
    max_files: int = Field(default=150)


# ─── Search Query Endpoints ──────────────────────────────────────────────────

@router.post("/search/local")
async def search_local(req: SearchRequest) -> Dict[str, Any]:
    """Execute millisecond SQLite FTS5 keyword search."""
    return await search_orchestrator.search(
        query=req.query,
        mode="keyword",
        limit=req.limit,
        source_type=req.source_type,
        refresh_web=False,
        user_id=req.user_id,
    )


@router.post("/search/hybrid")
async def search_hybrid(req: SearchRequest) -> Dict[str, Any]:
    """Execute hybrid search combining SQLite FTS5, Meilisearch, and Qdrant."""
    return await search_orchestrator.search(
        query=req.query,
        mode="hybrid",
        limit=req.limit,
        source_type=req.source_type,
        refresh_web=req.refresh_web,
        user_id=req.user_id,
    )


@router.post("/search/research")
async def search_research(req: SearchRequest) -> Dict[str, Any]:
    """
    Execute deep research search: local-first, with automatic SearXNG web
    refresh when local corpus does not satisfy the query.
    """
    return await search_orchestrator.search(
        query=req.query,
        mode="research",
        limit=req.limit,
        source_type=req.source_type,
        refresh_web=True,
        user_id=req.user_id,
    )


# ─── Document Ingestion Endpoints ────────────────────────────────────────────

@router.post("/search/ingest/file")
async def ingest_file(req: IngestFileRequest) -> Dict[str, Any]:
    """Ingest a single text file into the search engine."""
    ingestor = FileIngestor(
        local_engine=search_orchestrator.local,
        semantic_engine=search_orchestrator.semantic,
        meili_engine=search_orchestrator.meili,
    )
    try:
        doc_ids = await ingestor.ingest_file(
            file_path=req.file_path,
            title=req.title,
            source_type=req.source_type,
        )
        return {"success": True, "indexed_chunks": len(doc_ids), "doc_ids": doc_ids}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/search/ingest/pdf")
async def ingest_pdf(req: IngestPDFRequest) -> Dict[str, Any]:
    """Ingest a PDF with page-specific provenance."""
    ingestor = PDFIngestor(
        local_engine=search_orchestrator.local,
        semantic_engine=search_orchestrator.semantic,
        meili_engine=search_orchestrator.meili,
    )
    try:
        doc_ids = await ingestor.ingest_pdf(
            file_path=req.file_path,
            title=req.title,
        )
        return {"success": True, "indexed_pages": len(doc_ids), "doc_ids": doc_ids}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/search/ingest/url")
async def ingest_url(req: IngestURLRequest) -> Dict[str, Any]:
    """Ingest browser page or web content."""
    ingestor = BrowserPageIngestor(
        local_engine=search_orchestrator.local,
        semantic_engine=search_orchestrator.semantic,
        meili_engine=search_orchestrator.meili,
    )
    try:
        doc_ids = await ingestor.ingest_page(
            url=req.url,
            title=req.title or req.url,
            html_or_text=req.content,
        )
        return {"success": True, "indexed_chunks": len(doc_ids), "doc_ids": doc_ids}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/search/ingest/repo")
async def ingest_repo(req: IngestRepoRequest) -> Dict[str, Any]:
    """Ingest code repository source files."""
    ingestor = CodeRepoIngestor(
        local_engine=search_orchestrator.local,
        semantic_engine=search_orchestrator.semantic,
        meili_engine=search_orchestrator.meili,
    )
    try:
        doc_ids = await ingestor.ingest_repository(
            repo_dir=req.repo_path,
            repo_name=req.repo_name,
            max_files=req.max_files,
        )
        return {"success": True, "indexed_files": len(doc_ids), "doc_ids": doc_ids}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/search/ingest/folder")
async def ingest_folder(req: IngestFolderRequest) -> Dict[str, Any]:
    """Ingest documents from a directory."""
    from pathlib import Path
    root = Path(req.folder_path)
    if not root.exists() or not root.is_dir():
        raise HTTPException(status_code=400, detail=f"Folder not found: {req.folder_path}")

    file_ingestor = FileIngestor(
        local_engine=search_orchestrator.local,
        semantic_engine=search_orchestrator.semantic,
        meili_engine=search_orchestrator.meili,
    )
    pdf_ingestor = PDFIngestor(
        local_engine=search_orchestrator.local,
        semantic_engine=search_orchestrator.semantic,
        meili_engine=search_orchestrator.meili,
    )
    md_ingestor = MarkdownIngestor(
        local_engine=search_orchestrator.local,
        semantic_engine=search_orchestrator.semantic,
        meili_engine=search_orchestrator.meili,
    )

    all_indexed = []
    pattern = "**/*" if req.recursive else "*"
    count = 0

    for path in root.glob(pattern):
        if count >= req.max_files:
            break
        if not path.is_file():
            continue

        try:
            if path.suffix.lower() == ".pdf":
                doc_ids = await pdf_ingestor.ingest_pdf(str(path))
            elif path.suffix.lower() in (".md", ".markdown"):
                doc_ids = await md_ingestor.ingest_markdown(str(path))
            elif path.suffix.lower() in (".txt", ".csv", ".json", ".log"):
                doc_ids = await file_ingestor.ingest_file(str(path))
            else:
                continue

            all_indexed.extend(doc_ids)
            count += 1
        except Exception:
            continue

    return {"success": True, "files_processed": count, "total_chunks": len(all_indexed)}


# ─── Corpus Management & Inspection Endpoints ────────────────────────────────

@router.post("/search/reindex")
async def reindex_corpus() -> Dict[str, Any]:
    """Rebuild SQLite FTS5 search index incrementally from active documents."""
    count = search_orchestrator.local.reindex_all()
    search_orchestrator.cache.clear()
    return {"success": True, "reindexed_count": count}


@router.get("/search/status")
async def get_search_status() -> Dict[str, Any]:
    """Get status of all connected search sub-engines."""
    meili_ok = await search_orchestrator.meili.is_healthy()
    qdrant_ok = await search_orchestrator.semantic.is_healthy()
    searx_ok = await search_orchestrator.web.is_healthy()

    return {
        "status": "ready",
        "engines": {
            "sqlite_fts5": {"active": True, "mode": "primary_local", "latency": "1-20ms"},
            "meilisearch": {"active": meili_ok, "mode": "instant_search", "latency": "5-50ms"},
            "qdrant_semantic": {"active": qdrant_ok, "mode": "vector_semantic", "latency": "20-150ms"},
            "searxng": {"active": searx_ok, "mode": "fresh_web_fallback", "latency": "1-5s"},
            "hot_cache": {"active": True, "redis": bool(search_orchestrator.cache.redis_client), "latency": "<5ms"},
        },
    }


@router.get("/search/stats")
async def get_search_stats() -> Dict[str, Any]:
    """Return database statistics, document counts, and telemetry."""
    stats = search_orchestrator.local.get_stats()
    stats["cache"] = search_orchestrator.cache.stats()
    return stats


@router.get("/search/documents")
async def list_documents(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    source_type: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    """List indexed documents with pagination."""
    docs = search_orchestrator.local.list_documents(limit=limit, offset=offset, source_type=source_type)
    return {"documents": docs, "limit": limit, "offset": offset, "count": len(docs)}


@router.get("/search/documents/{doc_id}")
async def get_document(doc_id: str) -> Dict[str, Any]:
    """Inspect full document content, provenance, and metadata."""
    doc = search_orchestrator.local.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")
    return doc


@router.delete("/search/documents/{doc_id}")
async def delete_document(doc_id: str) -> Dict[str, Any]:
    """Delete a document from search indices."""
    success = search_orchestrator.local.delete_document(doc_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Document not found or already deleted: {doc_id}")

    # Remove from Meilisearch and Qdrant
    await search_orchestrator.meili.delete_document(doc_id)
    search_orchestrator.semantic.delete_document(doc_id)
    search_orchestrator.cache.clear()

    return {"success": True, "deleted_doc_id": doc_id}


@router.post("/search/cache/clear")
async def clear_cache() -> Dict[str, Any]:
    """Clear hot search query cache."""
    cleared = search_orchestrator.cache.clear()
    return {"success": True, "cleared_entries": cleared}


@router.get("/search/health")
async def get_search_health() -> Dict[str, Any]:
    """Search health probe."""
    stats = search_orchestrator.local.get_stats()
    return {
        "status": "healthy",
        "total_documents": stats["total_documents"],
        "fts5_ready": True,
        "database_path": stats["database_path"],
    }
