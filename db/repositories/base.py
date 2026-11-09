"""
Base Repository Pattern for SQLAlchemy 2.x
Generic CRUD operations, transaction-safe, UnitOfWork-compatible.
"""

from __future__ import annotations

import uuid
from typing import Any, Generic, List, Optional, Type, TypeVar
import sqlalchemy as sa
from sqlalchemy.orm import Session

from db.models.base import Base

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    """Generic CRUD repository bound to an active SQLAlchemy Session."""

    def __init__(self, session: Session, model_cls: Type[T]):
        self.session = session
        self.model_cls = model_cls

    def get_by_id(self, entity_id: uuid.UUID | str) -> Optional[T]:
        """Fetch entity by UUID or stringified UUID."""
        if isinstance(entity_id, str):
            try:
                entity_id = uuid.UUID(entity_id)
            except ValueError:
                return None
        return self.session.get(self.model_cls, entity_id)

    def list(self, limit: int = 100, offset: int = 0, **filters: Any) -> List[T]:
        """Fetch list of entities with optional equality filters."""
        stmt = sa.select(self.model_cls)
        for key, value in filters.items():
            if hasattr(self.model_cls, key) and value is not None:
                stmt = stmt.where(getattr(self.model_cls, key) == value)
        stmt = stmt.limit(limit).offset(offset)
        return list(self.session.scalars(stmt).all())

    def create(self, entity: T) -> T:
        """Add and flush entity to session."""
        self.session.add(entity)
        self.session.flush()
        return entity

    def update(self, entity: T) -> T:
        """Merge/update entity in session."""
        entity = self.session.merge(entity)
        self.session.flush()
        return entity

    def delete(self, entity_id: uuid.UUID | str) -> bool:
        """Delete entity by ID."""
        entity = self.get_by_id(entity_id)
        if entity:
            self.session.delete(entity)
            self.session.flush()
            return True
        return False

    def count(self, **filters: Any) -> int:
        """Count total matching rows."""
        stmt = sa.select(sa.func.count()).select_from(self.model_cls)
        for key, value in filters.items():
            if hasattr(self.model_cls, key) and value is not None:
                stmt = stmt.where(getattr(self.model_cls, key) == value)
        return self.session.scalar(stmt) or 0
