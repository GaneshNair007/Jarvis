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

            # Memory nodes (5 layers)
            c.execute("""
            CREATE TABLE IF NOT EXISTS memory_nodes (
                id TEXT PRIMARY KEY,
                layer TEXT NOT NULL CHECK(layer IN ('RAW', 'SEMANTIC', 'EPISODIC', 'WORKING', 'DIRECTIVE')),
                content TEXT NOT NULL,
                metadata TEXT,
                embedding BLOB,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            """)

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

# Singleton DB Store
db_store = DatabaseStore()
