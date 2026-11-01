"""Strongly typed cognitive schemas, enums, and data models for JARVIS Brain."""

from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MemoryCategory(str, Enum):
    """Explicit functional memory categories."""

    PREFERENCE = "preference"
    FACT = "fact"
    EPISODE = "episode"
    PROCEDURE = "procedure"
    DOCUMENT_REFERENCE = "document_reference"
    HYPOTHESIS = "hypothesis"


class MemorySourceType(str, Enum):
    """Authority classifications for memory provenance."""

    EXPLICIT_USER = "explicit_user"
    VERIFIED_TOOL = "verified_tool"
    IMPORTED_DOCUMENT = "imported_document"
    MODEL_INFERENCE = "model_inference"


class MemoryStatus(str, Enum):
    """Lifecycle status of memory records."""

    ACTIVE = "active"
    SUPERSEDED = "superseded"
    CONTRADICTED = "contradicted"
    EXPIRED = "expired"
    DELETED = "deleted"


class CanonicalMemoryRecord(BaseModel):
    """Authoritative memory representation conforming to Milestone M1 specifications."""

    id: str = Field(default_factory=lambda: f"mem_{uuid.uuid4().hex[:12]}")
    user_id: str = Field(..., description="Owner user identifier")
    project_id: Optional[str] = Field(None, description="Scoped project identifier")
    category: MemoryCategory = Field(default=MemoryCategory.FACT)
    content: str = Field(..., description="Clean memory text assertion")
    source_type: MemorySourceType = Field(default=MemorySourceType.EXPLICIT_USER)
    source_reference: Optional[str] = Field(None, description="Origin provenance link")
    evidence_references: List[str] = Field(default_factory=list, description="Audit hash or evidence IDs")
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    valid_from: float = Field(default_factory=time.time)
    valid_until: Optional[float] = Field(None, description="Expiration epoch; None if indefinite")
    status: MemoryStatus = Field(default=MemoryStatus.ACTIVE)
    sensitivity: str = Field(default="internal")
    retention_policy: str = Field(default="permanent")
    supersedes_id: Optional[str] = Field(None, description="Memory ID superseded by this record")
    extraction_model: Optional[str] = Field(None)
    embedding_model: Optional[str] = Field(None)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MemoryQueryFilter(BaseModel):
    """Scoped query parameters for memory retrieval."""

    user_id: str
    project_id: Optional[str] = None
    category: Optional[MemoryCategory] = None
    query: Optional[str] = None
    status: MemoryStatus = MemoryStatus.ACTIVE
    include_global_project: bool = True
    limit: int = 20
    offset: int = 0
