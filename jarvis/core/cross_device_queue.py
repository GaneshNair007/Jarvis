"""
JARVIS Cross-Device Task Queue
==============================
Persistent SQLite WAL queue supporting bidirectional remote execution
between mobile devices (phone) and host compute (laptop).

State Machine:
  QUEUED -> TRANSFERRED -> EXECUTING -> COMPLETED / FAILED
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from jarvis.config import settings
from jarvis.core.logger import get_logger

logger = get_logger("core.cross_device_queue")


class TaskStatus(str, Enum):
    QUEUED = "QUEUED"
    TRANSFERRED = "TRANSFERRED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    CANCELLED = "CANCELLED"


class TaskPriority(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


PRIORITY_WEIGHTS = {
    TaskPriority.CRITICAL: 0,
    TaskPriority.HIGH: 1,
    TaskPriority.MEDIUM: 2,
    TaskPriority.LOW: 3,
}

# Strict valid state transitions
VALID_TRANSITIONS = {
    TaskStatus.QUEUED: {TaskStatus.TRANSFERRED, TaskStatus.CANCELLED},
    TaskStatus.TRANSFERRED: {TaskStatus.EXECUTING, TaskStatus.FAILED, TaskStatus.QUEUED},
    TaskStatus.EXECUTING: {TaskStatus.COMPLETED, TaskStatus.FAILED},
    TaskStatus.FAILED: {TaskStatus.QUEUED},  # Retry path
    TaskStatus.COMPLETED: {TaskStatus.ACKNOWLEDGED},
    TaskStatus.ACKNOWLEDGED: set(),
    TaskStatus.CANCELLED: set(),
}


@dataclass
class CrossDeviceTask:
    task_id: str
    source_device: str
    source_channel: str
    target_device: str
    sender_id: str
    command_text: str
    status: str = TaskStatus.QUEUED.value
    priority: str = TaskPriority.HIGH.value
    retry_count: int = 0
    max_retries: int = 3
    payload: Dict[str, Any] = field(default_factory=dict)
    result: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    claimed_at: Optional[float] = None
    completed_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CrossDeviceTaskQueue:
    """
    SQLite WAL-backed persistent queue managing remote tasks sent from
    Ganesh's phone (+91 9324094474) or Switch for execution on laptop.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or (settings.data_dir / "jarvis.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_table()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        return conn

    def _init_table(self) -> None:
        """Initializes the cross_device_tasks table and supporting indexes."""
        with self._get_connection() as conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS cross_device_tasks (
                task_id TEXT PRIMARY KEY,
                source_device TEXT NOT NULL,
                source_channel TEXT NOT NULL,
                target_device TEXT NOT NULL,
                sender_id TEXT NOT NULL,
                command_text TEXT NOT NULL,
                status TEXT NOT NULL,
                priority TEXT NOT NULL DEFAULT 'HIGH',
                retry_count INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3,
                payload_json TEXT DEFAULT '{}',
                result_json TEXT DEFAULT '{}',
                error_message TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                claimed_at REAL,
                completed_at REAL
            );
            """)
            conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_cdt_status_priority 
            ON cross_device_tasks(status, priority, created_at);
            """)
            conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_cdt_target_device 
            ON cross_device_tasks(target_device, status);
            """)
            conn.commit()

    def _row_to_task(self, row: sqlite3.Row) -> CrossDeviceTask:
        payload = {}
        result = {}
        try:
            if row["payload_json"]:
                payload = json.loads(row["payload_json"])
        except Exception:
            payload = {}
        try:
            if row["result_json"]:
                result = json.loads(row["result_json"])
        except Exception:
            result = {}

        return CrossDeviceTask(
            task_id=row["task_id"],
            source_device=row["source_device"],
            source_channel=row["source_channel"],
            target_device=row["target_device"],
            sender_id=row["sender_id"],
            command_text=row["command_text"],
            status=row["status"],
            priority=row["priority"],
            retry_count=row["retry_count"],
            max_retries=row["max_retries"],
            payload=payload,
            result=result,
            error_message=row["error_message"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            claimed_at=row["claimed_at"],
            completed_at=row["completed_at"],
        )

    def enqueue_task(
        self,
        command: str,
        source_device: str = "phone",
        transport: str = "whatsapp",
        sender_id: str = "+919324094474",
        priority: str = TaskPriority.HIGH.value,
        payload: Optional[Dict[str, Any]] = None,
        target_device: str = "laptop",
        task_id: Optional[str] = None,
        max_retries: int = 3,
    ) -> CrossDeviceTask:
        """
        Enqueues a task issued from a remote device into the persistent SQLite WAL queue.
        Initial state: QUEUED.
        """
        now = time.time()
        generated_id = task_id or f"cdt_{int(now * 1000)}_{uuid.uuid4().hex[:8]}"
        payload_dict = payload or {}
        norm_priority = priority.upper() if priority.upper() in TaskPriority._value2member_map_ else TaskPriority.HIGH.value

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO cross_device_tasks (
                    task_id, source_device, source_channel, target_device,
                    sender_id, command_text, status, priority, retry_count,
                    max_retries, payload_json, result_json, error_message,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    generated_id,
                    source_device,
                    transport,
                    target_device,
                    sender_id,
                    command,
                    TaskStatus.QUEUED.value,
                    norm_priority,
                    0,
                    max_retries,
                    json.dumps(payload_dict),
                    json.dumps({}),
                    None,
                    now,
                    now,
                ),
            )
            conn.commit()

        logger.info(f"Cross-device task enqueued: {generated_id} ('{command[:40]}') from {source_device}/{transport}")
        return self.get_task(generated_id)  # type: ignore

    def enqueue_remote_task(
        self,
        command_text: str,
        source_device: str = "phone",
        source_channel: str = "whatsapp",
        sender_id: str = "+919324094474",
        priority: str = TaskPriority.HIGH.value,
        payload: Optional[Dict[str, Any]] = None,
        target_device: str = "laptop",
    ) -> CrossDeviceTask:
        """Alias for enqueue_task conforming to survey blueprint."""
        return self.enqueue_task(
            command=command_text,
            source_device=source_device,
            transport=source_channel,
            sender_id=sender_id,
            priority=priority,
            payload=payload,
            target_device=target_device,
        )

    def get_task(self, task_id: str) -> Optional[CrossDeviceTask]:
        """Retrieves task by unique task ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM cross_device_tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            if row:
                return self._row_to_task(row)
        return None

    def transition_status(
        self,
        task_id: str,
        new_status: TaskStatus | str,
        error_message: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
    ) -> CrossDeviceTask:
        """
        Strictly validates and applies a state transition in the task lifecycle.
        Valid paths: QUEUED -> TRANSFERRED -> EXECUTING -> COMPLETED / FAILED.
        """
        target_status = TaskStatus(new_status) if isinstance(new_status, str) else new_status
        task = self.get_task(task_id)
        if not task:
            raise KeyError(f"Task '{task_id}' not found in cross-device queue")

        curr_status = TaskStatus(task.status)
        allowed_next = VALID_TRANSITIONS.get(curr_status, set())
        if target_status not in allowed_next:
            raise ValueError(
                f"Illegal state transition for task '{task_id}': cannot move from '{curr_status.value}' to '{target_status.value}'. "
                f"Valid next states: {[s.value for s in allowed_next]}"
            )

        now = time.time()
        claimed_at = now if target_status in (TaskStatus.TRANSFERRED, TaskStatus.EXECUTING) and not task.claimed_at else task.claimed_at
        completed_at = now if target_status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED) else task.completed_at

        merged_result = task.result
        if result is not None:
            merged_result = result

        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE cross_device_tasks
                SET status = ?, error_message = COALESCE(?, error_message),
                    result_json = ?, updated_at = ?, claimed_at = ?, completed_at = ?
                WHERE task_id = ?
                """,
                (
                    target_status.value,
                    error_message,
                    json.dumps(merged_result),
                    now,
                    claimed_at,
                    completed_at,
                    task_id,
                ),
            )
            conn.commit()

        logger.info(f"Task '{task_id}' transitioned: {curr_status.value} -> {target_status.value}")
        return self.get_task(task_id)  # type: ignore

    def claim_next_task(
        self,
        worker_id: str = "laptop_worker",
        target_device: str = "laptop",
    ) -> Optional[CrossDeviceTask]:
        """
        Atomically claims the highest priority oldest QUEUED task for the target device.
        Transitions state: QUEUED -> TRANSFERRED.
        """
        with self._get_connection() as conn:
            # Query candidate tasks
            rows = conn.execute(
                """
                SELECT * FROM cross_device_tasks
                WHERE status = 'QUEUED' AND target_device = ?
                ORDER BY created_at ASC
                """,
                (target_device,),
            ).fetchall()

            if not rows:
                return None

            # Sort in memory by priority weight then created_at
            tasks = [self._row_to_task(r) for r in rows]
            tasks.sort(
                key=lambda t: (
                    PRIORITY_WEIGHTS.get(TaskPriority(t.priority), 99),
                    t.created_at,
                )
            )
            candidate = tasks[0]

            now = time.time()
            cursor = conn.execute(
                """
                UPDATE cross_device_tasks
                SET status = 'TRANSFERRED', claimed_at = ?, updated_at = ?
                WHERE task_id = ? AND status = 'QUEUED'
                """,
                (now, now, candidate.task_id),
            )
            conn.commit()

            if cursor.rowcount > 0:
                logger.info(f"Worker '{worker_id}' claimed task '{candidate.task_id}' (status -> TRANSFERRED)")
                return self.get_task(candidate.task_id)
        return None

    def start_execution(self, task_id: str) -> CrossDeviceTask:
        """Transitions state: TRANSFERRED -> EXECUTING."""
        return self.transition_status(task_id, TaskStatus.EXECUTING)

    def complete_task(
        self,
        task_id: str,
        result: Optional[Dict[str, Any]] = None,
    ) -> CrossDeviceTask:
        """Transitions state: EXECUTING -> COMPLETED."""
        return self.transition_status(task_id, TaskStatus.COMPLETED, result=result or {})

    def fail_task(
        self,
        task_id: str,
        error: str,
        retryable: bool = False,
    ) -> CrossDeviceTask:
        """
        Handles task failure. If retryable and attempts remain,
        increments retry count and sets back to QUEUED. Otherwise sets FAILED.
        """
        task = self.get_task(task_id)
        if not task:
            raise KeyError(f"Task '{task_id}' not found")

        now = time.time()
        if retryable and (task.retry_count + 1 < task.max_retries):
            new_retries = task.retry_count + 1
            with self._get_connection() as conn:
                conn.execute(
                    """
                    UPDATE cross_device_tasks
                    SET status = 'QUEUED', retry_count = ?, error_message = ?, updated_at = ?
                    WHERE task_id = ?
                    """,
                    (new_retries, f"Attempt {new_retries} failed: {error}", now, task_id),
                )
                conn.commit()
            logger.warning(f"Task '{task_id}' failed (retryable). Queued for retry {new_retries}/{task.max_retries}")
            return self.get_task(task_id)  # type: ignore
        else:
            # If not in EXECUTING, transition to EXECUTING first if needed before FAILED
            if task.status == TaskStatus.TRANSFERRED.value:
                self.transition_status(task_id, TaskStatus.EXECUTING)
            return self.transition_status(task_id, TaskStatus.FAILED, error_message=error)

    def list_tasks(
        self,
        status: Optional[str] = None,
        target_device: Optional[str] = None,
        limit: int = 50,
    ) -> List[CrossDeviceTask]:
        """Lists tasks matching optional status and target_device filters."""
        query = "SELECT * FROM cross_device_tasks WHERE 1=1"
        params: List[Any] = []
        if status:
            query += " AND status = ?"
            params.append(status.upper())
        if target_device:
            query += " AND target_device = ?"
            params.append(target_device)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_task(r) for r in rows]

    async def execute_task_flow(
        self,
        task_id: str,
        executor_fn: Optional[Callable[[str], Any]] = None,
    ) -> CrossDeviceTask:
        """
        Executes a claimed task through the complete state machine:
        TRANSFERRED -> EXECUTING -> COMPLETED (or FAILED).
        """
        task = self.get_task(task_id)
        if not task:
            raise KeyError(f"Task '{task_id}' not found")

        if task.status == TaskStatus.QUEUED.value:
            task = self.transition_status(task_id, TaskStatus.TRANSFERRED)

        if task.status == TaskStatus.TRANSFERRED.value:
            task = self.start_execution(task_id)

        try:
            if executor_fn:
                import inspect
                if inspect.iscoroutinefunction(executor_fn):
                    out = await executor_fn(task.command_text)
                else:
                    out = executor_fn(task.command_text)
            else:
                from jarvis.core.orchestrator import orchestrator
                out = await orchestrator.process_user_query(task.command_text)

            res_dict = out if isinstance(out, dict) else {"result": str(out)}
            if res_dict.get("status") in ("error", "failed", "unavailable"):
                return self.fail_task(task_id, error=str(res_dict.get("error", "Execution failed")))
            return self.complete_task(task_id, result=res_dict)
        except Exception as exc:
            logger.error(f"Execution error for task '{task_id}': {exc}", exc_info=True)
            return self.fail_task(task_id, error=str(exc))


# Global Singleton Instance
cross_device_queue = CrossDeviceTaskQueue()
