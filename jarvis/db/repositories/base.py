"""
JARVIS Base Repository
Enforces Domain-Driven Design: Repositories ONLY Read, Write, Update, Delete, and Query.
Repositories NEVER invoke LLMs, think, plan, or decompose goals.
"""

from __future__ import annotations

import uuid
from typing import Any, Generic, List, Optional, Type, TypeVar
import sqlalchemy as sa
from sqlalchemy.orm import Session

from jarvis.core.logger import get_logger

logger = get_logger("db.repository")

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """Universal repository interface encapsulating transactional operations."""

    def __init__(self, session: Session, model_class: Optional[Type[T]] = None):
        self.session = session
        self.model_class = model_class

    def save(self, entity: T) -> T:
        """Adds entity to current session."""
        self.session.add(entity)
        return entity

    def delete(self, entity: T) -> None:
        """Marks entity for deletion."""
        self.session.delete(entity)

    def flush(self) -> None:
        """Flushes pending changes to the database without committing."""
        self.session.flush()

    def commit(self) -> None:
        """Commits transaction directly (preferred through UnitOfWork)."""
        self.session.commit()

    def get_by_id(self, entity_id: uuid.UUID) -> Optional[T]:
        """Generic primary key lookup."""
        if not self.model_class:
            raise NotImplementedError("model_class must be defined for generic get_by_id.")
        return self.session.get(self.model_class, entity_id)

    def list_all(self, limit: int = 100) -> List[T]:
        """Lists entities up to limit."""
        if not self.model_class:
            raise NotImplementedError("model_class must be defined for generic list_all.")
        return self.session.query(self.model_class).limit(limit).all()
