"""
JARVIS SQLite WAL Database Store
Initializes and manages the local-first persistent SQLite database
with Write-Ahead Logging (WAL) for high concurrency and zero external dependency.
"""

import sqlite3
import json
import time
from typing import Dict, Any, List, Optional
from pathlib import Path
from jarvis.config import settings

class DatabaseStore:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or settings.db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_database(self) -> None:
        """Runs initial schema migrations."""
        with self._get_connection() as conn:
            c = conn.cursor()

            # Tasks table
            c.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                priority TEXT NOT NULL DEFAULT 'P1',
                power_id TEXT,
                inputs TEXT,
                outputs TEXT,
                error TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            """)

            # Approvals table
            c.execute("""
            CREATE TABLE IF NOT EXISTS approvals (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                power_id TEXT NOT NULL,
                action_summary TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                token TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('PENDING', 'APPROVED', 'REJECTED', 'EXPIRED')),
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL
            );
            """)

            # Check and migrate memory_nodes schema if needed
            c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='memory_nodes'")
            row = c.fetchone()
            if row and "PROCEDURAL" not in row[0]:
                c.execute("ALTER TABLE memory_nodes RENAME TO memory_nodes_old")
                c.execute("""
                CREATE TABLE memory_nodes (
                    id TEXT PRIMARY KEY,
                    layer TEXT NOT NULL CHECK(layer IN ('CAPTURE', 'RAW', 'EPISODIC', 'SEMANTIC', 'PROCEDURAL', 'WORKING', 'DIRECTIVE')),
                    content TEXT NOT NULL,
                    metadata TEXT,
                    embedding BLOB,
                    is_hypothesis INTEGER DEFAULT 0,
                    confidence REAL DEFAULT 1.0,
                    evidence_count INTEGER DEFAULT 1,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                """)
                c.execute("""
                INSERT INTO memory_nodes (id, layer, content, metadata, embedding, is_hypothesis, confidence, evidence_count, created_at, updated_at)
                SELECT id, layer, content, metadata, embedding, 0, 1.0, 1, created_at, updated_at FROM memory_nodes_old
                """)
                c.execute("DROP TABLE memory_nodes_old")
            else:
                # Memory nodes (extended 7 layers)
                c.execute("""
                CREATE TABLE IF NOT EXISTS memory_nodes (
                    id TEXT PRIMARY KEY,
                    layer TEXT NOT NULL CHECK(layer IN ('CAPTURE', 'RAW', 'EPISODIC', 'SEMANTIC', 'PROCEDURAL', 'WORKING', 'DIRECTIVE')),
                    content TEXT NOT NULL,
                    metadata TEXT,
                    embedding BLOB,
                    is_hypothesis INTEGER DEFAULT 0,
                    confidence REAL DEFAULT 1.0,
                    evidence_count INTEGER DEFAULT 1,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                """)

            # Ensure columns exist if table was previously created
            c.execute("PRAGMA table_info(memory_nodes)")
            cols = [col[1] for col in c.fetchall()]
            if "is_hypothesis" not in cols:
                c.execute("ALTER TABLE memory_nodes ADD COLUMN is_hypothesis INTEGER DEFAULT 0")
            if "confidence" not in cols:
                c.execute("ALTER TABLE memory_nodes ADD COLUMN confidence REAL DEFAULT 1.0")
            if "evidence_count" not in cols:
                c.execute("ALTER TABLE memory_nodes ADD COLUMN evidence_count INTEGER DEFAULT 1")

            # Documents table (for RAG)
            c.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                file_path TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_type TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                total_pages INTEGER NOT NULL DEFAULT 1,
                total_chunks INTEGER NOT NULL DEFAULT 0,
                file_size INTEGER NOT NULL DEFAULT 0,
                metadata TEXT,
                created_at REAL NOT NULL
            );
            """)

            # Document Chunks table
            c.execute("""
            CREATE TABLE IF NOT EXISTS document_chunks (
                id TEXT PRIMARY KEY,
                doc_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                page_number INTEGER NOT NULL DEFAULT 1,
                chunk_index INTEGER NOT NULL DEFAULT 0,
                content TEXT NOT NULL,
                metadata TEXT,
                embedding BLOB,
                created_at REAL NOT NULL
            );
            """)

            # User Corrections table
            c.execute("""
            CREATE TABLE IF NOT EXISTS corrections (
                id TEXT PRIMARY KEY,
                failure_id TEXT,
                user_quote TEXT NOT NULL,
                old_behavior TEXT,
                new_instruction TEXT NOT NULL,
                scope TEXT NOT NULL CHECK(scope IN ('this_task', 'this_project', 'always')),
                status TEXT NOT NULL DEFAULT 'ACTIVE',
                created_at REAL NOT NULL
            );
            """)

            # Indexes
            c.execute("CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON document_chunks(doc_id)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_memory_layer ON memory_nodes(layer)")

            # System telemetry snapshots
            c.execute("""
            CREATE TABLE IF NOT EXISTS system_telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cpu_percent REAL,
                ram_percent REAL,
                disk_percent REAL,
                active_workers INTEGER,
                timestamp REAL NOT NULL
            );
            """)

            conn.commit()

    def save_task(self, task_id: str, title: str, status: str, power_id: str = "", inputs: Any = None, outputs: Any = None) -> None:
        now = time.time()
        with self._get_connection() as conn:
            conn.execute("""
            INSERT INTO tasks (id, title, status, power_id, inputs, outputs, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status = excluded.status,
                outputs = excluded.outputs,
                updated_at = excluded.updated_at
            """, (
                task_id, title, status, power_id,
                json.dumps(inputs) if inputs else None,
                json.dumps(outputs) if outputs else None,
                now, now
            ))
            conn.commit()

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row:
                return dict(row)
        return None

    def list_tasks(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM tasks ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]

    # Document operations
    def save_document(
        self,
        doc_id: str,
        file_path: str,
        file_name: str,
        file_type: str,
        sha256: str,
        total_pages: int,
        total_chunks: int,
        file_size: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        now = time.time()
        meta_str = json.dumps(metadata or {})
        with self._get_connection() as conn:
            conn.execute("""
            INSERT INTO documents (id, file_path, file_name, file_type, sha256, total_pages, total_chunks, file_size, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                total_chunks = excluded.total_chunks,
                metadata = excluded.metadata
            """, (doc_id, file_path, file_name, file_type, sha256, total_pages, total_chunks, file_size, meta_str, now))
            conn.commit()

    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
            if row:
                res = dict(row)
                if res.get("metadata"):
                    try:
                        res["metadata"] = json.loads(res["metadata"])
                    except Exception:
                        pass
                return res
        return None

    def get_document_by_hash(self, sha256: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM documents WHERE sha256 = ?", (sha256,)).fetchone()
            if row:
                res = dict(row)
                if res.get("metadata"):
                    try:
                        res["metadata"] = json.loads(res["metadata"])
                    except Exception:
                        pass
                return res
        return None

    def list_documents(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM documents ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
            results = []
            for r in rows:
                item = dict(r)
                if item.get("metadata"):
                    try:
                        item["metadata"] = json.loads(item["metadata"])
                    except Exception:
                        pass
                results.append(item)
            return results

    def delete_document(self, doc_id: str) -> bool:
        with self._get_connection() as conn:
            cur = conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
            conn.execute("DELETE FROM document_chunks WHERE doc_id = ?", (doc_id,))
            conn.commit()
            return cur.rowcount > 0

    # Document Chunks operations
    def save_chunks(self, chunks: List[Dict[str, Any]]) -> None:
        now = time.time()
        with self._get_connection() as conn:
            for ch in chunks:
                conn.execute("""
                INSERT OR REPLACE INTO document_chunks (id, doc_id, page_number, chunk_index, content, metadata, embedding, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    ch["id"],
                    ch["doc_id"],
                    ch.get("page_number", 1),
                    ch.get("chunk_index", 0),
                    ch["content"],
                    json.dumps(ch.get("metadata", {})),
                    ch.get("embedding"),
                    now
                ))
            conn.commit()

    def get_chunks_for_doc(self, doc_id: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM document_chunks WHERE doc_id = ? ORDER BY page_number, chunk_index", (doc_id,)).fetchall()
            return [dict(r) for r in rows]

    def get_all_chunks(self, limit: int = 2000) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            rows = conn.execute("""
            SELECT c.*, d.file_path, d.file_name, d.sha256 
            FROM document_chunks c
            JOIN documents d ON c.doc_id = d.id
            ORDER BY c.created_at DESC LIMIT ?
            """, (limit,)).fetchall()
            return [dict(r) for r in rows]

    # User Corrections
    def save_correction(
        self,
        correction_id: str,
        user_quote: str,
        new_instruction: str,
        scope: str = "always",
        failure_id: Optional[str] = None,
        old_behavior: Optional[str] = None
    ) -> None:
        now = time.time()
        with self._get_connection() as conn:
            conn.execute("""
            INSERT OR REPLACE INTO corrections (id, failure_id, user_quote, old_behavior, new_instruction, scope, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE', ?)
            """, (correction_id, failure_id, user_quote, old_behavior, new_instruction, scope, now))
            conn.commit()

    def list_corrections(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM corrections ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]

    # Storage Statistics
    def get_storage_stats(self) -> Dict[str, Any]:
        with self._get_connection() as conn:
            layer_counts = {}
            for row in conn.execute("SELECT layer, COUNT(*) as cnt FROM memory_nodes GROUP BY layer"):
                layer_counts[row["layer"]] = row["cnt"]

            total_nodes = sum(layer_counts.values())
            doc_count = conn.execute("SELECT COUNT(*) as cnt FROM documents").fetchone()["cnt"]
            chunk_count = conn.execute("SELECT COUNT(*) as cnt FROM document_chunks").fetchone()["cnt"]
            correction_count = conn.execute("SELECT COUNT(*) as cnt FROM corrections").fetchone()["cnt"]
            task_count = conn.execute("SELECT COUNT(*) as cnt FROM tasks").fetchone()["cnt"]

            db_size = self.db_path.stat().st_size if self.db_path.exists() else 0

            audit_log_size = 0
            if settings.audit_log_path.exists():
                audit_log_size = settings.audit_log_path.stat().st_size

            return {
                "db_path": str(self.db_path),
                "db_size_bytes": db_size,
                "db_size_kb": round(db_size / 1024, 2),
                "audit_log_size_bytes": audit_log_size,
                "total_memory_nodes": total_nodes,
                "layers": layer_counts,
                "total_documents": doc_count,
                "total_chunks": chunk_count,
                "total_corrections": correction_count,
                "total_tasks": task_count,
            }

# Singleton DB Store
db_store = DatabaseStore()
