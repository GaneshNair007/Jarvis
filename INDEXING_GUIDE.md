# JARVIS Local Search: Ingestion & Indexing Guide

This guide details how to ingest, index, and manage your local data corpus with JARVIS Local Search.

---

## 1. Supported Document Sources

JARVIS includes dedicated ingestors for every primary document format in your digital workspace:

| Ingestor File | Supported Formats / Sources | Key Behaviors |
| :--- | :--- | :--- |
| `file_ingestor.py` | `.txt`, `.csv`, `.json`, `.yaml`, `.xml` | UTF-8/Latin-1 auto-detect, line-aware chunking |
| `pdf_ingestor.py` | `.pdf` (Portable Document Format) | PyPDF text extraction, page-level metadata |
| `markdown_ingestor.py` | `.md`, `.markdown` | Header-aware `#`, `##` section slicing |
| `code_repo_ingestor.py` | `.py`, `.js`, `.ts`, `.html`, `.css`, `.go`, `.rs`, `.sh`, `.sql` | Respects `.gitignore`, excludes `node_modules`, `.git`, binary extensions |
| `browser_page_ingestor.py`| Saved HTML, web archives | HTML tag stripping, title & URL provenance |
| `email_ingestor.py` | `.eml`, `.msg`, email dumps | Header extraction (`From`, `Subject`, `Date`), body redaction |
| `chat_history_ingestor.py`| Slack, Discord, LLM chat transcripts | Turn-by-turn conversational chunking |
| `notes_ingestor.py` | Obsidian, Notion, Apple Notes exports | Tag preservation, wiki-link metadata extraction |
| `web_cache_ingestor.py` | SearXNG query results, web scrape caches | Query correlation, freshness timestamping |

---

## 2. Ingestion Rules & Data Pipeline

Every ingested document passes through the following automated pipeline:

```text
Raw File / Stream
       ↓
1. Text Extraction (UTF-8 normalizer, PDF extractor, or Markdown parser)
       ↓
2. Sensitive Data Redaction (Removes API keys, JWTs, passwords, private keys, payment cards)
       ↓
3. SHA-256 Content Hashing (Calculates deterministic digest of cleaned text)
       ↓
4. Deduplication Check (Queries documents table; aborts silently if digest exists)
       ↓
5. Semantic Chunking (Splits text into ~1200-char chunks with 200-char overlap)
       ↓
6. Multi-Engine Indexing:
   ├── Write to SQLite `documents` table (Provenance & soft-delete flags)
   ├── Index into SQLite FTS5 `search_index` (BM25 keyword search)
   ├── Index into Meilisearch `jarvis_docs` index (Typo tolerance)
   └── Embed via Ollama & upsert into Qdrant `jarvis_docs` (Cosine semantic search)
       ↓
7. Audit Event Recorded in JARVIS Security Ledger
```

---

## 3. Ingestion Methods

### Method A: REST API Endpoints

#### Ingest a Local File
```bash
curl -X POST http://localhost:8000/search/ingest/file \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "C:/Users/Ganesh Nair/Documents/Notes/SystemArchitecture.md",
    "source_type": "notes"
  }'
```

#### Ingest an Entire Directory or Repository
```bash
curl -X POST http://localhost:8000/search/ingest/repo \
  -H "Content-Type: application/json" \
  -d '{
    "repo_path": "C:/Users/Ganesh Nair/Projects/jarvis",
    "repo_name": "jarvis-core",
    "respect_gitignore": true
  }'
```

#### Ingest a PDF Document
```bash
curl -X POST http://localhost:8000/search/ingest/pdf \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "C:/Users/Ganesh Nair/Documents/Papers/AttentionIsAllYouNeed.pdf"
  }'
```

#### Ingest Web / Article Content
```bash
curl -X POST http://localhost:8000/search/ingest/url \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://fastapi.tiangolo.com/tutorial/bigger-applications/",
    "title": "FastAPI Bigger Applications Tutorial",
    "content": "When you create a FastAPI application, you can organize your routes across multiple APIRouter modules..."
  }'
```

---

### Method B: Python SDK / Direct Script Execution

```python
from search.local_search_engine import LocalSearchEngine
from search.meili_search import MeiliSearchClient
from search.semantic_search import QdrantSemanticSearch
from search.ingestors.code_repo_ingestor import CodeRepoIngestor

engine = LocalSearchEngine("data/jarvis_search.db")
semantic = QdrantSemanticSearch()
meili = MeiliSearchClient()

ingestor = CodeRepoIngestor(
    local_engine=engine,
    semantic_engine=semantic,
    meili_engine=meili,
)

# Ingest an entire local repository
summary = await ingestor.ingest_repo("C:/Users/Ganesh Nair/Projects/jarvis", repo_name="jarvis")
print(f"Indexed {summary['indexed_files']} files across {summary['total_chunks']} chunks.")
```

---

## 4. Incremental Reindexing & Deduplication

- **Idempotency Guarantee**: If a file has not changed, its SHA-256 digest matches the database, and ingestion skips it in microseconds without consuming CPU cycles or vector storage.
- **Incremental Rebuild**: Running `POST /search/reindex` reads all active (non-deleted) records from the SQLite `documents` table and syncs them into SQLite FTS5 and Meilisearch.

---

## 5. Document Deletion & Retention

To delete a document from the search brain:

```bash
curl -X DELETE http://localhost:8000/search/documents/doc_abc123
```

This immediately:
1. Marks `deleted_at = CURRENT_TIMESTAMP` in the SQLite `documents` table.
2. Removes the document row from the SQLite FTS5 `search_index`.
3. Calls Meilisearch `delete_documents([doc_id])`.
4. Deletes vector points from Qdrant by `doc_id` filter.
5. Invalidates the hot search cache.
