---
name: jarvis-local-search
description: Guides the implementation, maintenance, and benchmarking of JARVIS's local, non-API, sub-5ms hybrid search engine. Use when modifying search indices, ingestors, caching, ranking, or vector integration.
---

# JARVIS Local Search Architecture & Ingestion

## Overview
JARVIS local search delivers sub-millisecond to low-millisecond keyword retrieval without cloud search APIs:
`Exact Cache (Redis / in-memory)` -> `SQLite FTS5 (BM25 keyword)` -> `Meilisearch (typo-tolerant)` -> `Qdrant (vector semantic)` -> `SearXNG (optional fresh web refresh)`.

## Ingestion Pipeline
1. **Base Ingestor (`search/ingestors/base_ingestor.py`)**:
   - Strips sensitive credentials via `redact_sensitive_data()`.
   - Splits text into overlapping semantic chunks (`chunk_text()`).
   - Builds provenance tracking records (`build_provenance()`).
2. **Specific Ingestors**:
   - `CodeRepoIngestor`: AST / file symbols and code repos.
   - `NotesIngestor`: Markdown notes, tags, notebooks.
   - `EmailIngestor`: Email threads, senders, recipients, dates.
   - `ChatHistoryIngestor`: Conversational turns and model attribution.
   - `PDFIngestor`: Page-specific extraction via PyMuPDF (`fitz`).
3. **Keyword Search Engine (`search/local_search_engine.py`)**:
   - SQLite FTS5 table `search_index` using `porter unicode61` tokenizer.
   - Fast BM25 scoring and snippet generation.
4. **Cache & Invalidation (`search/search_cache.py`)**:
   - Invalidate cached queries on document mutations or deletions.

## Benchmarking & Verification
```powershell
python -m pytest tests/test_local_search.py tests/test_coverage_core.py -v
```
Ensure keyword retrieval achieves sub-10ms response on local database files.

