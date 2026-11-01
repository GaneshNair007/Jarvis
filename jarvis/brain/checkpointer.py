"""
JARVIS SQLite State Checkpointer
Implements SqliteCheckpointSaver subclassing LangGraph's BaseCheckpointSaver.
Persists graph state snapshots and pending writes to the SQLite database
with WAL mode, 5000ms busy timeout, and thread-safe locking.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Union

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    get_checkpoint_id,
    get_checkpoint_metadata,
)
from langgraph.checkpoint.serde.base import SerializerProtocol
from jarvis.core.logger import get_logger

logger = get_logger("brain.checkpointer")


class SqliteCheckpointSaver(BaseCheckpointSaver[str]):
    """
    Durable SQLite checkpoint saver for LangGraph StateGraph execution.
    Complies with Alembic revision 0003_graph_voice database schema.
    """

    def __init__(
        self,
        conn: Optional[sqlite3.Connection] = None,
        db_path: Optional[Union[str, Path]] = None,
        *,
        serde: Optional[SerializerProtocol] = None,
    ) -> None:
        super().__init__(serde=serde)
        self._lock = threading.RLock()
        self._owns_conn = conn is None

        if conn is not None:
            self._conn = conn
        else:
            if db_path is None:
                from jarvis.config import settings

                db_path = settings.db_path

            db_path_obj = Path(db_path) if isinstance(db_path, str) else db_path
            if str(db_path_obj) != ":memory:":
                db_path_obj.parent.mkdir(parents=True, exist_ok=True)

            self._conn = sqlite3.connect(
                str(db_path_obj),
                check_same_thread=False,
                timeout=30.0,
            )

        # Enable WAL mode and 5000ms busy timeout for safe concurrent writes
        try:
            with self._lock:
                self._conn.execute("PRAGMA journal_mode=WAL;")
                self._conn.execute("PRAGMA busy_timeout=5000;")
        except Exception as exc:
            logger.warning(f"Could not set WAL pragma on sqlite connection: {exc}")

        self.setup()

    def setup(self) -> None:
        """Initializes checkpoint tables if missing."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS graph_checkpoints (
                    thread_id VARCHAR(128) NOT NULL,
                    checkpoint_ns VARCHAR(128) NOT NULL DEFAULT '',
                    checkpoint_id VARCHAR(64) NOT NULL,
                    parent_checkpoint_id VARCHAR(64),
                    type VARCHAR(32),
                    checkpoint_blob BLOB NOT NULL,
                    metadata_blob BLOB,
                    created_at FLOAT NOT NULL,
                    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
                );
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS ix_graph_checkpoints_thread
                ON graph_checkpoints (thread_id);
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS graph_checkpoint_writes (
                    thread_id VARCHAR(128) NOT NULL,
                    checkpoint_ns VARCHAR(128) NOT NULL DEFAULT '',
                    checkpoint_id VARCHAR(64) NOT NULL,
                    task_id VARCHAR(64) NOT NULL,
                    idx INTEGER NOT NULL,
                    channel VARCHAR(128) NOT NULL,
                    type VARCHAR(32),
                    value_blob BLOB NOT NULL,
                    task_path VARCHAR(256) DEFAULT '',
                    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
                );
                """
            )
            self._conn.commit()

    @classmethod
    def from_conn_string(cls, conn_string: str) -> SqliteCheckpointSaver:
        """Factory method to construct saver from connection string or file path."""
        # Clean prefix if sqlite:/// or sqlite://
        clean_path = conn_string
        for prefix in ("sqlite:///", "sqlite://"):
            if clean_path.startswith(prefix):
                clean_path = clean_path[len(prefix) :]
                break
        return cls(db_path=clean_path)

    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        """Retrieves a checkpoint tuple for a given config."""
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = get_checkpoint_id(config)

        with self._lock:
            cursor = self._conn.cursor()
            if checkpoint_id:
                cursor.execute(
                    """
                    SELECT checkpoint_id, parent_checkpoint_id, type, checkpoint_blob, metadata_blob, created_at
                    FROM graph_checkpoints
                    WHERE thread_id = ? AND checkpoint_ns = ? AND checkpoint_id = ?
                    """,
                    (thread_id, checkpoint_ns, checkpoint_id),
                )
            else:
                cursor.execute(
                    """
                    SELECT checkpoint_id, parent_checkpoint_id, type, checkpoint_blob, metadata_blob, created_at
                    FROM graph_checkpoints
                    WHERE thread_id = ? AND checkpoint_ns = ?
                    ORDER BY checkpoint_id DESC
                    LIMIT 1
                    """,
                    (thread_id, checkpoint_ns),
                )
            row = cursor.fetchone()
            if not row:
                return None

            cid, parent_cid, type_str, cp_blob, meta_blob, created_at = row

            cursor.execute(
                """
                SELECT task_id, channel, type, value_blob
                FROM graph_checkpoint_writes
                WHERE thread_id = ? AND checkpoint_ns = ? AND checkpoint_id = ?
                ORDER BY task_id, idx
                """,
                (thread_id, checkpoint_ns, cid),
            )
            write_rows = cursor.fetchall()

        checkpoint_data: Checkpoint = self.serde.loads_typed((type_str or "msgpack", cp_blob))
        metadata_data = self.serde.loads_typed((type_str or "msgpack", meta_blob)) if meta_blob else {}
        pending_writes = [
            (w_task_id, w_channel, self.serde.loads_typed((w_type or "msgpack", w_blob)))
            for w_task_id, w_channel, w_type, w_blob in write_rows
        ]

        final_config = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": cid,
            }
        }
        parent_config = (
            {
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": parent_cid,
                }
            }
            if parent_cid
            else None
        )

        return CheckpointTuple(
            config=final_config,
            checkpoint=checkpoint_data,
            metadata=metadata_data,
            pending_writes=pending_writes,
            parent_config=parent_config,
        )

    def list(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[Dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> Iterator[CheckpointTuple]:
        """Lists historical checkpoints matching thread and ns."""
        if not config:
            return

        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")

        query = """
            SELECT checkpoint_id, parent_checkpoint_id, type, checkpoint_blob, metadata_blob, created_at
            FROM graph_checkpoints
            WHERE thread_id = ? AND checkpoint_ns = ?
        """
        params: List[Any] = [thread_id, checkpoint_ns]

        if before and (before_id := get_checkpoint_id(before)):
            query += " AND checkpoint_id < ?"
            params.append(before_id)

        query += " ORDER BY checkpoint_id DESC"
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)

        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()

        for row in rows:
            cid, parent_cid, type_str, cp_blob, meta_blob, created_at = row
            with self._lock:
                cursor = self._conn.cursor()
                cursor.execute(
                    """
                    SELECT task_id, channel, type, value_blob
                    FROM graph_checkpoint_writes
                    WHERE thread_id = ? AND checkpoint_ns = ? AND checkpoint_id = ?
                    ORDER BY task_id, idx
                    """,
                    (thread_id, checkpoint_ns, cid),
                )
                write_rows = cursor.fetchall()

            checkpoint_data: Checkpoint = self.serde.loads_typed((type_str or "msgpack", cp_blob))
            metadata_data = self.serde.loads_typed((type_str or "msgpack", meta_blob)) if meta_blob else {}
            pending_writes = [
                (w_task_id, w_channel, self.serde.loads_typed((w_type or "msgpack", w_blob)))
                for w_task_id, w_channel, w_type, w_blob in write_rows
            ]

            yield CheckpointTuple(
                config={
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_ns": checkpoint_ns,
                        "checkpoint_id": cid,
                    }
                },
                checkpoint=checkpoint_data,
                metadata=metadata_data,
                pending_writes=pending_writes,
                parent_config=(
                    {
                        "configurable": {
                            "thread_id": thread_id,
                            "checkpoint_ns": checkpoint_ns,
                            "checkpoint_id": parent_cid,
                        }
                    }
                    if parent_cid
                    else None
                ),
            )

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """Persists a new checkpoint into graph_checkpoints."""
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = checkpoint["id"]
        parent_checkpoint_id = config["configurable"].get("checkpoint_id")

        c = checkpoint.copy()
        type_str, cp_blob = self.serde.dumps_typed(c)
        meta_dict = get_checkpoint_metadata(config, metadata)
        _, meta_blob = self.serde.dumps_typed(meta_dict)
        created_at = time.time()

        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO graph_checkpoints
                (thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id, type, checkpoint_blob, metadata_blob, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    thread_id,
                    checkpoint_ns,
                    checkpoint_id,
                    parent_checkpoint_id,
                    type_str,
                    cp_blob,
                    meta_blob,
                    created_at,
                ),
            )
            self._conn.commit()

        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            }
        }

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        """Stores pending intermediate node writes."""
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = config["configurable"]["checkpoint_id"]

        with self._lock:
            cursor = self._conn.cursor()
            for idx, (channel, val) in enumerate(writes):
                type_str, val_blob = self.serde.dumps_typed(val)
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO graph_checkpoint_writes
                    (thread_id, checkpoint_ns, checkpoint_id, task_id, idx, channel, type, value_blob, task_path)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        thread_id,
                        checkpoint_ns,
                        checkpoint_id,
                        task_id,
                        idx,
                        channel,
                        type_str,
                        val_blob,
                        task_path,
                    ),
                )
            self._conn.commit()

    def delete_thread(self, thread_id: str) -> None:
        """Deletes all checkpoints and pending writes for a thread."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("DELETE FROM graph_checkpoints WHERE thread_id = ?", (thread_id,))
            cursor.execute("DELETE FROM graph_checkpoint_writes WHERE thread_id = ?", (thread_id,))
            self._conn.commit()

    def __enter__(self) -> SqliteCheckpointSaver:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._owns_conn and hasattr(self, "_conn") and self._conn:
            try:
                self._conn.close()
            except Exception:
                pass


__all__ = ["SqliteCheckpointSaver"]
