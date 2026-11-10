"""SQLAlchemy SQLite Implementation of Canonical Memory Repository."""

from __future__ import annotations

import json
import time
from typing import List, Optional
from sqlalchemy import or_
from sqlalchemy.orm import Session, sessionmaker

from jarvis.memory.models import get_db_engine
from jarvis.brain.schemas import (
    CanonicalMemoryRecord,
    MemoryQueryFilter,
    MemoryStatus,
)
from jarvis.brain.memory.interfaces import MemoryRepositoryInterface
from jarvis.brain.memory.models import Base, CanonicalMemoryModel


def get_default_session():
    engine = get_db_engine()
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


class SQLAlchemyMemoryRepository(MemoryRepositoryInterface):
    """Production SQLite/SQLAlchemy implementation of the memory repository."""

    def __init__(self, session_factory=None):
        self.session_factory = session_factory or get_default_session
        self._ensure_tables()

    def _ensure_tables(self):
        engine = get_db_engine()
        Base.metadata.create_all(engine)

    def add(self, record: CanonicalMemoryRecord) -> CanonicalMemoryRecord:
        """Persists a new canonical memory record."""
        session: Session = self.session_factory()
        try:
            model = CanonicalMemoryModel(
                id=record.id,
                user_id=record.user_id,
                project_id=record.project_id,
                category=record.category.value if hasattr(record.category, "value") else str(record.category),
                content=record.content,
                source_type=record.source_type.value
                if hasattr(record.source_type, "value")
                else str(record.source_type),
                source_reference=record.source_reference,
                evidence_references_json=json.dumps(record.evidence_references),
                created_at=record.created_at,
                updated_at=record.updated_at,
                valid_from=record.valid_from,
                valid_until=record.valid_until,
                status=record.status.value if hasattr(record.status, "value") else str(record.status),
                sensitivity=record.sensitivity,
                retention_policy=record.retention_policy,
                supersedes_id=record.supersedes_id,
                extraction_model=record.extraction_model,
                embedding_model=record.embedding_model,
                metadata_json=json.dumps(record.metadata),
            )
            session.add(model)
            session.commit()
            return CanonicalMemoryRecord(**model.to_record_dict())
        finally:
            session.close()

    def get_by_id(self, memory_id: str, user_id: str) -> Optional[CanonicalMemoryRecord]:
        """Retrieves a memory record strictly scoped to user_id."""
        session: Session = self.session_factory()
        try:
            model = (
                session.query(CanonicalMemoryModel)
                .filter(
                    CanonicalMemoryModel.id == memory_id,
                    CanonicalMemoryModel.user_id == user_id,
                )
                .first()
            )
            if not model:
                return None
            return CanonicalMemoryRecord(**model.to_record_dict())
        finally:
            session.close()

    def search(self, filters: MemoryQueryFilter) -> List[CanonicalMemoryRecord]:
        """Executes scoped query filtering by user, project, category, status, and keywords."""
        session: Session = self.session_factory()
        try:
            query = session.query(CanonicalMemoryModel).filter(
                CanonicalMemoryModel.user_id == filters.user_id,
            )

            # Scoping: Project match or Global project
            if filters.project_id:
                if filters.include_global_project:
                    query = query.filter(
                        or_(
                            CanonicalMemoryModel.project_id == filters.project_id,
                            CanonicalMemoryModel.project_id.is_(None),
                        )
                    )
                else:
                    query = query.filter(CanonicalMemoryModel.project_id == filters.project_id)

            if filters.category:
                cat_val = filters.category.value if hasattr(filters.category, "value") else str(filters.category)
                query = query.filter(CanonicalMemoryModel.category == cat_val)

            if filters.status:
                stat_val = filters.status.value if hasattr(filters.status, "value") else str(filters.status)
                query = query.filter(CanonicalMemoryModel.status == stat_val)

            # Keyword containment
            if filters.query:
                tokens = [t.strip().lower() for t in filters.query.split() if len(t.strip()) > 1]
                for tok in tokens:
                    query = query.filter(CanonicalMemoryModel.content.ilike(f"%{tok}%"))

            # Order by updated_at desc
            query = query.order_by(CanonicalMemoryModel.updated_at.desc())
            results = query.offset(filters.offset).limit(filters.limit).all()

            return [CanonicalMemoryRecord(**m.to_record_dict()) for m in results]
        finally:
            session.close()

    def correct(
        self,
        memory_id: str,
        user_id: str,
        new_content: str,
        supersedes_id: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> Optional[CanonicalMemoryRecord]:
        """Marks old record as superseded and creates a new corrected record."""
        session: Session = self.session_factory()
        try:
            target_id = supersedes_id or memory_id
            old_model = (
                session.query(CanonicalMemoryModel)
                .filter(
                    CanonicalMemoryModel.id == target_id,
                    CanonicalMemoryModel.user_id == user_id,
                )
                .first()
            )
            if not old_model:
                return None

            now = time.time()
            old_model.status = MemoryStatus.SUPERSEDED.value
            old_model.updated_at = now

            # Create replacement record
            new_record = CanonicalMemoryRecord(
                user_id=old_model.user_id,
                project_id=old_model.project_id,
                category=old_model.category,
                content=new_content,
                source_type=old_model.source_type,
                source_reference=old_model.source_reference,
                evidence_references=json.loads(old_model.evidence_references_json or "[]"),
                created_at=now,
                updated_at=now,
                valid_from=now,
                status=MemoryStatus.ACTIVE,
                supersedes_id=target_id,
                metadata={"correction_reason": reason or "User correction"},
            )

            new_model = CanonicalMemoryModel(
                id=new_record.id,
                user_id=new_record.user_id,
                project_id=new_record.project_id,
                category=str(
                    new_record.category.value if hasattr(new_record.category, "value") else new_record.category
                ),
                content=new_record.content,
                source_type=str(
                    new_record.source_type.value if hasattr(new_record.source_type, "value") else new_record.source_type
                ),
                source_reference=new_record.source_reference,
                evidence_references_json=json.dumps(new_record.evidence_references),
                created_at=new_record.created_at,
                updated_at=new_record.updated_at,
                valid_from=new_record.valid_from,
                status=new_record.status.value,
                supersedes_id=target_id,
                metadata_json=json.dumps(new_record.metadata),
            )
            session.add(new_model)
            session.commit()
            return CanonicalMemoryRecord(**new_model.to_record_dict())
        finally:
            session.close()

    def delete(self, memory_id: str, user_id: str, hard_delete: bool = False) -> bool:
        """Deletes or tombstones a record."""
        session: Session = self.session_factory()
        try:
            model = (
                session.query(CanonicalMemoryModel)
                .filter(
                    CanonicalMemoryModel.id == memory_id,
                    CanonicalMemoryModel.user_id == user_id,
                )
                .first()
            )
            if not model:
                return False

            if hard_delete:
                session.delete(model)
            else:
                model.status = MemoryStatus.DELETED.value
                model.updated_at = time.time()
            session.commit()
            return True
        finally:
            session.close()

    def delete_by_project(self, user_id: str, project_id: str) -> int:
        """Deletes all memories for a project."""
        session: Session = self.session_factory()
        try:
            count = (
                session.query(CanonicalMemoryModel)
                .filter(
                    CanonicalMemoryModel.user_id == user_id,
                    CanonicalMemoryModel.project_id == project_id,
                )
                .update(
                    {"status": MemoryStatus.DELETED.value, "updated_at": time.time()},
                    synchronize_session="fetch",
                )
            )
            session.commit()
            return count
        finally:
            session.close()
