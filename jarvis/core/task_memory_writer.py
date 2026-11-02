"""
JARVIS Task Memory Integration Layer
Every completed task automatically formats and records structured MemoryEvents into
the persistent long-term SQLite memory graph, ensuring zero state amnesia across restarts.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from jarvis.core.task_graph import TaskNode
from jarvis.memory.store import db_store
from jarvis.core.logger import get_logger

logger = get_logger("core.task_memory")


class MemoryEvent(BaseModel):
    source_task: str
    category: str
    content: Dict[str, Any]
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    event_id: Optional[str] = None


class TaskMemoryWriter:
    """
    Subscribes to task completions, extracts distilled semantic knowledge,
    and writes indexed MemoryEvents into the SQLite long-term memory graph.
    """

    def __init__(self, backup_storage: str = "data/task_memory_events.json"):
        self.backup_path = Path(backup_storage)
        self.events: List[MemoryEvent] = []
        self._load_backup()

    def _load_backup(self) -> None:
        if self.backup_path.exists():
            try:
                data = json.loads(self.backup_path.read_text(encoding="utf-8"))
                self.events = [MemoryEvent(**item) for item in data]
            except Exception as e:
                logger.warning(f"Failed to load memory backup from {self.backup_path}: {e}")

    def _save_backup(self) -> None:
        try:
            self.backup_path.parent.mkdir(parents=True, exist_ok=True)
            serializable = [e.model_dump() for e in self.events]
            self.backup_path.write_text(json.dumps(serializable, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to save memory backup: {e}")

    def record_task_memory(self, task: TaskNode) -> MemoryEvent:
        """Extracts task results and records a permanent MemoryEvent."""
        category = self._infer_category(task)
        content = {
            "task_name": task.name,
            "description": task.description,
            "department": task.department,
            "assigned_agent": task.assigned_agent,
            "parent_goal": task.parent_goal,
            "outputs": task.outputs,
            "tools_used": task.tool_requirements,
        }

        event = MemoryEvent(
            source_task=task.task_id,
            category=category,
            content=content,
        )
        self.events.append(event)
        self._save_backup()

        # Write to SQLite DB Store (Permanent graph storage)
        try:
            db_store.save_memory(
                user_id="ganesh",
                text=f"[{category.upper()}] Task '{task.name}' completed by [{task.assigned_agent}]: {json.dumps(task.outputs)[:250]}",
                category=category,
                source=f"task:{task.task_id}",
            )
        except Exception as dbe:
            logger.warning(f"SQLite memory write skipped or simulated: {dbe}")

        logger.info(f"TaskMemoryWriter: Recorded memory event for task '{task.task_id}' under category '{category}'")
        return event

    def query_memories(self, category: Optional[str] = None, keyword: Optional[str] = None, limit: int = 50) -> List[MemoryEvent]:
        """Queries recorded memory events with category and keyword filtering."""
        results = self.events
        if category:
            results = [e for e in results if e.category.lower() == category.lower()]
        if keyword:
            kw = keyword.lower()
            results = [e for e in results if kw in json.dumps(e.content).lower()]
        return results[-limit:]

    @staticmethod
    def _infer_category(task: TaskNode) -> str:
        dept = task.department.lower()
        if "hackathon" in dept:
            return "hackathon"
        if "eng" in dept or "code" in dept:
            return "engineering"
        if "research" in dept:
            return "research"
        if "career" in dept or "job" in dept:
            return "career"
        if "security" in dept:
            return "security"
        if "ops" in dept:
            return "operations"
        return "general"


# Global Singleton Instance
task_memory_writer = TaskMemoryWriter()
