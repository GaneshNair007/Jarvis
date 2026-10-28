"""
JARVIS Local Search Engine — SQLite FTS5 Full-Text Search.
Provides millisecond-latency local keyword search, bm25 ranking,
highlighted snippets, provenance tracking, and incremental indexing.
"""

import hashlib
import json
import re
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class SearchHit:
    doc_id: str
    title: str
    url: Optional[str]
    snippet: str
    source_type: str
    score: float
    provider: str = "sqlite_fts5"
    latency_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "source_type": self.source_type,
            "score": round(self.score, 4),
            "provider": self.provider,
            "providers": [self.provider],
            "latency_ms": round(self.latency_ms, 2),
            "metadata": self.metadata,
            "provenance": self.provenance,
        }


class LocalSearchEngine:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            from jarvis.config import settings
            self.db_path = str(settings.search_db_path)
        else:
            self.db_path = str(db_path)

        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initialize SQLite tables and FTS5 virtual index."""
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    doc_id TEXT PRIMARY KEY,
                    source_type TEXT NOT NULL,
                    source_url TEXT,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    content_hash TEXT UNIQUE,
                    metadata_json TEXT,
                    provenance_json TEXT,
                    permissions_json TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    deleted_at TEXT
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(
                    doc_id UNINDEXED,
                    source_type UNINDEXED,
                    source_url UNINDEXED,
                    title,
                    content,
                    metadata_json UNINDEXED,
                    tokenize = 'porter unicode61'
                );

                CREATE TABLE IF NOT EXISTS search_queries (
                    query_id TEXT PRIMARY KEY,
                    user_id TEXT,
                    query TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    providers_used TEXT,
                    result_count INTEGER,
                    latency_ms REAL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS search_cache (
                    cache_key TEXT PRIMARY KEY,
                    query_hash TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    expires_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS citations (
                    citation_id TEXT PRIMARY KEY,
                    doc_id TEXT NOT NULL,
                    query_id TEXT,
                    title TEXT NOT NULL,
                    url TEXT,
                    excerpt TEXT,
                    score REAL,
                    provider TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

    @staticmethod
    def _hash(text: str) -> str:
        """Compute deterministic SHA-256 content hash."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def sanitize_fts5_query(query: str) -> str:
        """
        Sanitize search query for SQLite FTS5 syntax.
        Safely strips unescaped punctuation while preserving alphanumeric words.
        """
        clean = re.sub(r'[^\w\s\-_"]', ' ', query).strip()
        tokens = [t.strip() for t in clean.split() if t.strip()]
        if not tokens:
            return '""'
        # Group into matched tokens
        return " ".join(tokens)

    def ingest(
        self,
        doc_id: str,
        title: str,
        content: str,
        source_type: str,
        source_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        provenance: Optional[Dict[str, Any]] = None,
        permissions: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Ingest a document into local documents table and FTS5 search index.
        Returns False if duplicate content hash exists, True otherwise.
        """
        content_hash = self._hash(content)
        metadata_str = json.dumps(metadata or {})
        provenance_str = json.dumps(provenance or {})
        permissions_str = json.dumps(permissions or {"public": True})

        with self._connect() as conn:
            # Check for existing duplicate content hash
            existing = conn.execute(
                "SELECT doc_id FROM documents WHERE content_hash = ? AND deleted_at IS NULL",
                (content_hash,),
            ).fetchone()
            if existing:
                return False

            conn.execute(
                """
                INSERT INTO documents (
                    doc_id, source_type, source_url, title, content,
                    content_hash, metadata_json, provenance_json, permissions_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(doc_id) DO UPDATE SET
                    source_type=excluded.source_type,
                    source_url=excluded.source_url,
                    title=excluded.title,
                    content=excluded.content,
                    content_hash=excluded.content_hash,
                    metadata_json=excluded.metadata_json,
                    provenance_json=excluded.provenance_json,
                    permissions_json=excluded.permissions_json,
                    updated_at=CURRENT_TIMESTAMP,
                    deleted_at=NULL
                """,
                (
                    doc_id,
                    source_type,
                    source_url,
                    title,
                    content,
                    content_hash,
                    metadata_str,
                    provenance_str,
                    permissions_str,
                ),
            )

            # Keep FTS5 index in sync
            conn.execute("DELETE FROM search_index WHERE doc_id = ?", (doc_id,))
            conn.execute(
                """
                INSERT INTO search_index (
                    doc_id, source_type, source_url, title, content, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (doc_id, source_type, source_url, title, content, metadata_str),
            )
            return True

    def keyword_search(
        self, query: str, limit: int = 20, source_type: Optional[str] = None
    ) -> List[SearchHit]:
        """
        Run millisecond SQLite FTS5 full-text keyword search using bm25 ranking.
        """
        started = time.perf_counter()
        clean_query = self.sanitize_fts5_query(query)
        if not clean_query or clean_query == '""':
            return []

        with self._connect() as conn:
            try:
                if source_type:
                    cursor = conn.execute(
                        """
                        SELECT 
                            s.doc_id,
                            s.source_type,
                            s.source_url,
                            s.title,
                            snippet(search_index, 4, '<b>', '</b>', '...', 15) AS snippet,
                            bm25(search_index) AS rank,
                            d.metadata_json,
                            d.provenance_json
                        FROM search_index s
                        JOIN documents d ON s.doc_id = d.doc_id
                        WHERE search_index MATCH ? AND s.source_type = ? AND d.deleted_at IS NULL
                        ORDER BY rank
                        LIMIT ?
                        """,
                        (clean_query, source_type, limit),
                    )
                else:
                    cursor = conn.execute(
                        """
                        SELECT 
                            s.doc_id,
                            s.source_type,
                            s.source_url,
                            s.title,
                            snippet(search_index, 4, '<b>', '</b>', '...', 15) AS snippet,
                            bm25(search_index) AS rank,
                            d.metadata_json,
                            d.provenance_json
                        FROM search_index s
                        JOIN documents d ON s.doc_id = d.doc_id
                        WHERE search_index MATCH ? AND d.deleted_at IS NULL
                        ORDER BY rank
                        LIMIT ?
                        """,
                        (clean_query, limit),
                    )
                rows = cursor.fetchall()
            except sqlite3.OperationalError:
                # Fallback to wildcard token matching on syntax error
                tokens = [t for t in clean_query.split() if t]
                or_query = " OR ".join(f'"{t}"*' for t in tokens)
                cursor = conn.execute(
                    """
                    SELECT 
                        s.doc_id,
                        s.source_type,
                        s.source_url,
                        s.title,
                        snippet(search_index, 4, '<b>', '</b>', '...', 15) AS snippet,
                        bm25(search_index) AS rank,
                        d.metadata_json,
                        d.provenance_json
                    FROM search_index s
                    JOIN documents d ON s.doc_id = d.doc_id
                    WHERE search_index MATCH ? AND d.deleted_at IS NULL
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (or_query, limit),
                )
                rows = cursor.fetchall()

        latency_ms = (time.perf_counter() - started) * 1000.0

        hits = []
        for row in rows:
            meta = json.loads(row["metadata_json"] or "{}")
            prov = json.loads(row["provenance_json"] or "{}")
            # bm25 in SQLite is negative where more negative = more relevant
            score = abs(float(row["rank"])) if row["rank"] is not None else 1.0

            hits.append(
                SearchHit(
                    doc_id=row["doc_id"],
                    title=row["title"],
                    url=row["source_url"],
                    snippet=row["snippet"],
                    source_type=row["source_type"],
                    score=score,
                    provider="sqlite_fts5",
                    latency_ms=latency_ms,
                    metadata=meta,
                    provenance=prov,
                )
            )
        return hits

    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve full document record by ID."""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT doc_id, source_type, source_url, title, content,
                       content_hash, metadata_json, provenance_json, permissions_json,
                       created_at, updated_at, deleted_at
                FROM documents
                WHERE doc_id = ? AND deleted_at IS NULL
                """,
                (doc_id,),
            ).fetchone()
            if not row:
                return None
            return {
                "doc_id": row["doc_id"],
                "source_type": row["source_type"],
                "source_url": row["source_url"],
                "title": row["title"],
                "content": row["content"],
                "content_hash": row["content_hash"],
                "metadata": json.loads(row["metadata_json"] or "{}"),
                "provenance": json.loads(row["provenance_json"] or "{}"),
                "permissions": json.loads(row["permissions_json"] or "{}"),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }

    def list_documents(
        self, limit: int = 50, offset: int = 0, source_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List active indexed documents."""
        with self._connect() as conn:
            if source_type:
                rows = conn.execute(
                    """
                    SELECT doc_id, source_type, source_url, title, content_hash,
                           metadata_json, provenance_json, created_at, updated_at
                    FROM documents
                    WHERE deleted_at IS NULL AND source_type = ?
                    ORDER BY updated_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (source_type, limit, offset),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT doc_id, source_type, source_url, title, content_hash,
                           metadata_json, provenance_json, created_at, updated_at
                    FROM documents
                    WHERE deleted_at IS NULL
                    ORDER BY updated_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (limit, offset),
                ).fetchall()

            return [
                {
                    "doc_id": r["doc_id"],
                    "source_type": r["source_type"],
                    "source_url": r["source_url"],
                    "title": r["title"],
                    "content_hash": r["content_hash"],
                    "metadata": json.loads(r["metadata_json"] or "{}"),
                    "provenance": json.loads(r["provenance_json"] or "{}"),
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                }
                for r in rows
            ]

    def delete_document(self, doc_id: str) -> bool:
        """Soft-delete document from repository and remove from FTS5 index."""
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT doc_id FROM documents WHERE doc_id = ? AND deleted_at IS NULL",
                (doc_id,),
            ).fetchone()
            if not existing:
                return False

            conn.execute(
                "UPDATE documents SET deleted_at = CURRENT_TIMESTAMP WHERE doc_id = ?",
                (doc_id,),
            )
            conn.execute("DELETE FROM search_index WHERE doc_id = ?", (doc_id,))
            return True

    def reindex_all(self) -> int:
        """Clear and rebuild FTS5 search index incrementally from active documents."""
        with self._connect() as conn:
            conn.execute("DELETE FROM search_index")
            rows = conn.execute(
                """
                SELECT doc_id, source_type, source_url, title, content, metadata_json
                FROM documents
                WHERE deleted_at IS NULL
                """
            ).fetchall()

            count = 0
            for r in rows:
                conn.execute(
                    """
                    INSERT INTO search_index (
                        doc_id, source_type, source_url, title, content, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        r["doc_id"],
                        r["source_type"],
                        r["source_url"],
                        r["title"],
                        r["content"],
                        r["metadata_json"],
                    ),
                )
                count += 1
            return count

    def record_query(
        self,
        query_id: str,
        user_id: str,
        query: str,
        mode: str,
        providers_used: List[str],
        result_count: int,
        latency_ms: float,
    ) -> None:
        """Log search query performance and telemetry."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO search_queries (
                    query_id, user_id, query, mode, providers_used, result_count, latency_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    query_id,
                    user_id,
                    query,
                    mode,
                    json.dumps(providers_used),
                    result_count,
                    latency_ms,
                ),
            )

    def record_citation(
        self,
        citation_id: str,
        doc_id: str,
        query_id: Optional[str],
        title: str,
        url: Optional[str],
        excerpt: str,
        score: float,
        provider: str,
    ) -> None:
        """Persist verifiable citation."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO citations (
                    citation_id, doc_id, query_id, title, url, excerpt, score, provider
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    citation_id,
                    doc_id,
                    query_id,
                    title,
                    url,
                    excerpt,
                    score,
                    provider,
                ),
            )

    def get_stats(self) -> Dict[str, Any]:
        """Return corpus stats and telemetry."""
        with self._connect() as conn:
            doc_count = conn.execute(
                "SELECT COUNT(*) FROM documents WHERE deleted_at IS NULL"
            ).fetchone()[0]

            types = conn.execute(
                """
                SELECT source_type, COUNT(*) as cnt
                FROM documents
                WHERE deleted_at IS NULL
                GROUP BY source_type
                """
            ).fetchall()

            queries = conn.execute(
                "SELECT COUNT(*), AVG(latency_ms) FROM search_queries"
            ).fetchone()

            citations_count = conn.execute(
                "SELECT COUNT(*) FROM citations"
            ).fetchone()[0]

            db_size_bytes = Path(self.db_path).stat().st_size if Path(self.db_path).exists() else 0

            return {
                "total_documents": doc_count,
                "documents_by_type": {r["source_type"]: r["cnt"] for r in types},
                "total_queries": queries[0] if queries else 0,
                "avg_query_latency_ms": round(queries[1], 2) if queries and queries[1] else 0.0,
                "total_citations": citations_count,
                "database_size_kb": round(db_size_bytes / 1024, 2),
                "database_path": self.db_path,
            }
