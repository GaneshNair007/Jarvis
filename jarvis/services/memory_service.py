"""
JARVIS Memory Service
Semantic memory ingestion, episodic knowledge extraction, and contextual recall.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from jarvis.db.unit_of_work import UnitOfWork
from jarvis.db.models.memory import MemoryModel
from jarvis.core.logger import get_logger

logger = get_logger("services.memory")


class MemoryService:

    def __init__(self, uow_factory=UnitOfWork):
        self.uow_factory = uow_factory

    def record_memory(
        self,
        category: str,
        content: Dict[str, Any],
        importance_score: float = 1.0,
        source_task_id: Optional[uuid.UUID] = None,
        goal_id: Optional[uuid.UUID] = None,
    ) -> MemoryModel:
        with self.uow_factory() as uow:
            mem = uow.memories.store_memory(
                category=category,
                content=content,
                importance_score=importance_score,
                source_task_id=source_task_id,
                goal_id=goal_id,
            )
            uow.commit()
            return mem

    def recall(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 5,
    ) -> List[MemoryModel]:
        """Retrieves top semantic memories matching the query."""
        with self.uow_factory() as uow:
            return uow.memories.search_memory(term=query, category=category, limit=limit)
