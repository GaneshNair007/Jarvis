# JARVIS Local Search: Citation & Provenance Policy

## 1. Core Principle: Zero Unverified Information

In JARVIS, **every search result must be accompanied by verifiable provenance and a structured citation**. 

The system enforces three invariant rules:
1. **Never return an answer or result without provenance**: An answer without a source cannot be audited, verified, or trusted.
2. **Never hallucinate citations**: Citations must map directly to an existing local document row in the SQLite `documents` table.
3. **Exact Excerpt Attribution**: Every citation must contain a verbatim excerpt from the underlying indexed text chunk.

---

## 2. Citation Data Model

The database schema and API enforce the following structured citation contract:

```json
{
  "citation_id": "cit_doc_8f192b_d41d8cd9",
  "doc_id": "doc_8f192b02",
  "query_id": "qry_88301b",
  "title": "FastAPI Dependency Injection Guide",
  "url": "https://fastapi.tiangolo.com/tutorial/dependencies/",
  "source_type": "web",
  "indexed_at": "2026-10-29T02:15:30.128Z",
  "excerpt": "FastAPI has a very powerful but intuitive Dependency Injection system that allows developers to declare dependencies cleanly...",
  "score": 0.884,
  "providers": ["sqlite_fts5", "meilisearch", "qdrant_semantic"],
  "provenance": {
    "source_type": "web",
    "source_url": "https://fastapi.tiangolo.com/tutorial/dependencies/",
    "content_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "retrieved_at": "2026-10-29T02:15:30.128Z"
  }
}
```

---

## 3. Cryptographic Determinism of Citation IDs

Citations are generated with deterministic IDs:

$$\text{citation\_id} = \text{"cit\_"} + \text{doc\_id} + \text{"\_"} + \text{SHA256}(\text{excerpt})[:8]$$

This ensures that:
- Identical quotes across multiple query passes retain stable citation references.
- Citations can be cross-referenced across LangGraph agent workflows and persistent memory checkpoints.
- Citations can be looked up in the SQLite `citations` table for audit trails.

---

## 4. Citation UI Presentation in Dashboard

In the JARVIS Dashboard Search HUD:
- Every search hit renders a **Verified Citation Badge** displaying:
  - Source Type pill (e.g., `[CODE]`, `[PDF]`, `[NOTES]`, `[WEB]`)
  - Provider list (e.g., `FTS5`, `Meilisearch`, `Qdrant`)
  - Direct clickable file link or URL (`file:///...` or `https://...`)
  - Expandable excerpt with matching keyword highlights
  - Single-click **Inspect Document** modal to inspect raw provenance metadata, SHA-256 hash, and full document text.
