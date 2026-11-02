"""
SQLAlchemy 2.x Knowledge Graph Models for JARVIS
Underlying graph nodes and directed relationships modeling long-term semantic connections.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from jarvis.db.models.base import Base, GUID, UniversalJSON


class KnowledgeNodeModel(Base):
    __tablename__ = "knowledge_nodes"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    node_type: Mapped[str] = mapped_column(sa.String(50), index=True, nullable=False)
    name: Mapped[str] = mapped_column(sa.String(255), index=True, nullable=False)
    metadata_json: Mapped[Dict[str, Any]] = mapped_column("metadata", UniversalJSON, default=dict, nullable=False)

    # Outgoing and incoming edges
    outgoing_edges: Mapped[List["KnowledgeEdgeModel"]] = relationship(
        "KnowledgeEdgeModel",
        foreign_keys="KnowledgeEdgeModel.source_node_id",
        back_populates="source_node",
        cascade="all, delete-orphan",
    )
    incoming_edges: Mapped[List["KnowledgeEdgeModel"]] = relationship(
        "KnowledgeEdgeModel",
        foreign_keys="KnowledgeEdgeModel.target_node_id",
        back_populates="target_node",
        cascade="all, delete-orphan",
    )


class KnowledgeEdgeModel(Base):
    __tablename__ = "knowledge_edges"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    source_node_id: Mapped[uuid.UUID] = mapped_column(
        GUID, sa.ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), index=True, nullable=False
    )
    target_node_id: Mapped[uuid.UUID] = mapped_column(
        GUID, sa.ForeignKey("knowledge_nodes.id", ondelete="CASCADE"), index=True, nullable=False
    )
    relationship: Mapped[str] = mapped_column(sa.String(100), index=True, nullable=False)
    strength: Mapped[float] = mapped_column(sa.Float, default=1.0, nullable=False)

    # Relationships
    source_node: Mapped["KnowledgeNodeModel"] = relationship(
        "KnowledgeNodeModel", foreign_keys=[source_node_id], back_populates="outgoing_edges"
    )
    target_node: Mapped["KnowledgeNodeModel"] = relationship(
        "KnowledgeNodeModel", foreign_keys=[target_node_id], back_populates="incoming_edges"
    )
