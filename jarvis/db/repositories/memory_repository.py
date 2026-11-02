"""
JARVIS Memory Repository
Long-term intelligence repository managing semantic and episodic memory records.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional
import sqlalchemy as sa
from sqlalchemy.orm import Session

from jarvis.db.models.memory import MemoryModel
from jarvis.db.repositories.base import BaseRepository


class MemoryRepository(BaseRepository[MemoryModel]):

    def __init__(self, session: Session):
        super().__init__(session, MemoryModel)

    def store_memory(
        self,
        category: str,
        content: Dict[str, Any],
        importance_score: float = 1.0,
        source_task_id: Optional[uuid.UUID] = None,
        goal_id: Optional[uuid.UUID] = None,
        embedding_id: Optional[str] = None,
        memory_id: Optional[uuid.UUID] = None,
    ) -> MemoryModel:
        """Stores a structured memory event into permanent persistence."""
        mem = MemoryModel(
            id=memory_id or uuid.uuid4(),
            category=category.lower(),
            content=content,
            importance_score=importance_score,
            source_task_id=source_task_id,
            goal_id=goal_id,
            embedding_id=embedding_id,
            access_count=0,
        )
        self.session.add(mem)
        return mem

    def get_memory(self, memory_id: uuid.UUID) -> Optional[MemoryModel]:
        mem = self.session.query(MemoryModel).filter(MemoryModel.id == memory_id).first()
        if mem:
            mem.access_count += 1
            self.session.add(mem)
        return mem

    def search_memory(
        self,
        term: str,
        category: Optional[str] = None,
        limit: int = 10,
    ) -> List[MemoryModel]:
        """Simple text search across category and memory content."""
        query = self.session.query(MemoryModel)
        if category:
            query = query.filter(MemoryModel.category == category.lower())

        # For cross-platform support (PostgreSQL and SQLite JSON text)
        query = query.filter(sa.cast(MemoryModel.content, sa.String).ilike(f"%{term}%"))
        return query.order_by(MemoryModel.importance_score.desc()).limit(limit).all()

    def update_memory(self, memory_id: uuid.UUID, content: Dict[str, Any]) -> Optional[MemoryModel]:
        mem = self.get_memory(memory_id)
        if mem:
            updated = dict(mem.content)
            updated.update(content)
            mem.content = updated
            self.session.add(mem)
        return mem

    def get_recent_memories(self, category: Optional[str] = None, limit: int = 10) -> List[MemoryModel]:
        query = self.session.query(MemoryModel)
        if category:
            query = query.filter(MemoryModel.category == category.lower())
        return query.order_by(MemoryModel.created_at.desc()).limit(limit).all()
