"""Relational models for JARVIS's personal workspace.

Adapted from Nūs Desktop's semester/workspace concepts to JARVIS's existing
SQLAlchemy database. This module intentionally uses the existing database
engine, UUID type, JSON type, and migration conventions.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any, Dict, Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from jarvis.db.models.base import Base, GUID, UniversalJSON, TimestampMixin


class WorkspaceCourseModel(Base, TimestampMixin):
    """A course or learning track in the owner's personal workspace."""

    __tablename__ = "workspace_courses"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[str] = mapped_column(sa.String(100), default="ganesh", index=True, nullable=False)
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(sa.String(80), nullable=True)
    term: Mapped[Optional[str]] = mapped_column(sa.String(120), nullable=True)
    credit_hours: Mapped[float] = mapped_column(sa.Float, default=3.0, nullable=False)
    status: Mapped[str] = mapped_column(sa.String(24), default="active", index=True, nullable=False)
    metadata_json: Mapped[Dict[str, Any]] = mapped_column("metadata", UniversalJSON, default=dict, nullable=False)


class WorkspaceAssignmentModel(Base, TimestampMixin):
    """An assignment, exam, submission, or other course deadline."""

    __tablename__ = "workspace_assignments"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[str] = mapped_column(sa.String(100), default="ganesh", index=True, nullable=False)
    course_id: Mapped[uuid.UUID] = mapped_column(
        GUID, sa.ForeignKey("workspace_courses.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    due_at: Mapped[Optional[datetime.datetime]] = mapped_column(sa.DateTime(timezone=True), nullable=True, index=True)
    status: Mapped[str] = mapped_column(sa.String(24), default="pending", index=True, nullable=False)
    weight_pct: Mapped[Optional[float]] = mapped_column(sa.Float, nullable=True)
    score_pct: Mapped[Optional[float]] = mapped_column(sa.Float, nullable=True)
    expected_score_pct: Mapped[float] = mapped_column(sa.Float, default=90.0, nullable=False)
    estimated_minutes: Mapped[int] = mapped_column(sa.Integer, default=60, nullable=False)
    source_confidence: Mapped[str] = mapped_column(sa.String(24), default="manual", nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)


class WorkspaceTaskModel(Base, TimestampMixin):
    """A general personal task, optionally linked to a course or assignment."""

    __tablename__ = "workspace_tasks"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[str] = mapped_column(sa.String(100), default="ganesh", index=True, nullable=False)
    course_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID, sa.ForeignKey("workspace_courses.id", ondelete="SET NULL"), index=True, nullable=True
    )
    assignment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID, sa.ForeignKey("workspace_assignments.id", ondelete="SET NULL"), index=True, nullable=True
    )
    title: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    description: Mapped[str] = mapped_column(sa.Text, default="", nullable=False)
    due_at: Mapped[Optional[datetime.datetime]] = mapped_column(sa.DateTime(timezone=True), nullable=True, index=True)
    status: Mapped[str] = mapped_column(sa.String(24), default="todo", index=True, nullable=False)
    priority: Mapped[str] = mapped_column(sa.String(16), default="normal", index=True, nullable=False)
    estimated_minutes: Mapped[int] = mapped_column(sa.Integer, default=30, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    recurrence_key: Mapped[Optional[str]] = mapped_column(sa.String(120), nullable=True)


class WorkspaceCaptureModel(Base, TimestampMixin):
    """A review queue for notes, facts, ideas, and task proposals.

    Captures remain pending until the owner explicitly approves them. Approval
    is the only operation that promotes a capture into durable memory or a task.
    """

    __tablename__ = "workspace_captures"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[str] = mapped_column(sa.String(100), default="ganesh", index=True, nullable=False)
    kind: Mapped[str] = mapped_column(sa.String(24), index=True, nullable=False)
    content: Mapped[str] = mapped_column(sa.Text, nullable=False)
    context_json: Mapped[Dict[str, Any]] = mapped_column("context", UniversalJSON, default=dict, nullable=False)
    source: Mapped[str] = mapped_column(sa.String(120), default="chat", nullable=False)
    status: Mapped[str] = mapped_column(sa.String(24), default="pending", index=True, nullable=False)
    reviewed_at: Mapped[Optional[datetime.datetime]] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    linked_memory_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID, sa.ForeignKey("memories.id", ondelete="SET NULL"), nullable=True
    )
    linked_task_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID, sa.ForeignKey("workspace_tasks.id", ondelete="SET NULL"), nullable=True
    )
