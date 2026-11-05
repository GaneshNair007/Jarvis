"""SQLAlchemy Declarative Models for Canonical Brain Memory Records."""

import json
import time
from sqlalchemy import Column, String, Float, Text, Index
from jarvis.memory.models import Base


class CanonicalMemoryModel(Base):
    """SQLAlchemy persistent entity for canonical memory records."""

    __tablename__ = "canonical_memories"

    id = Column(String(64), primary_key=True)
    user_id = Column(String(64), nullable=False, index=True)
    project_id = Column(String(64), nullable=True, index=True)
    category = Column(String(32), nullable=False, default="fact", index=True)
    content = Column(Text, nullable=False)
    source_type = Column(String(32), nullable=False, default="explicit_user")
    source_reference = Column(String(256), nullable=True)
    evidence_references_json = Column(Text, default="[]")
    created_at = Column(Float, default=time.time)
    updated_at = Column(Float, default=time.time)
    valid_from = Column(Float, default=time.time)
    valid_until = Column(Float, nullable=True)
    status = Column(String(32), default="active", index=True)
    sensitivity = Column(String(32), default="internal")
    retention_policy = Column(String(32), default="permanent")
    supersedes_id = Column(String(64), nullable=True)
    extraction_model = Column(String(64), nullable=True)
    embedding_model = Column(String(64), nullable=True)
    metadata_json = Column(Text, default="{}")

    __table_args__ = (
        Index("ix_canonical_user_proj", "user_id", "project_id"),
        Index("ix_canonical_user_cat", "user_id", "category"),
    )

    def to_record_dict(self):
        """Converts model entity to dictionary representation."""
        try:
            evidence = json.loads(self.evidence_references_json or "[]")
        except Exception:
            evidence = []
        try:
            meta = json.loads(self.metadata_json or "{}")
        except Exception:
            meta = {}

        return {
            "id": self.id,
            "user_id": self.user_id,
            "project_id": self.project_id,
            "category": self.category,
            "content": self.content,
            "source_type": self.source_type,
            "source_reference": self.source_reference,
            "evidence_references": evidence,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "valid_from": self.valid_from,
            "valid_until": self.valid_until,
            "status": self.status,
            "sensitivity": self.sensitivity,
            "retention_policy": self.retention_policy,
            "supersedes_id": self.supersedes_id,
            "extraction_model": self.extraction_model,
            "embedding_model": self.embedding_model,
            "metadata": meta,
        }
