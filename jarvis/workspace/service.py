"""Business logic for JARVIS's Nūs-inspired personal workspace.

All writes use the existing SQLAlchemy session factory. Dates and deadline
ranking are deterministic; model calls are deliberately not used for scores.
"""
from __future__ import annotations

import datetime as dt
import uuid
from typing import Any, Callable, Dict, Optional

import sqlalchemy as sa
from sqlalchemy.orm import Session

from jarvis.config import settings
from jarvis.db.session import SessionFactory
from jarvis.db.models.goal import GoalModel
from jarvis.db.models.memory import MemoryModel
from jarvis.db.models.workspace import (
    WorkspaceAssignmentModel,
    WorkspaceCaptureModel,
    WorkspaceCourseModel,
    WorkspaceTaskModel,
)

UTC = dt.timezone.utc
CAPTURE_KINDS = {"note", "fact", "idea", "task"}
TASK_STATUSES = {"todo", "in_progress", "completed", "cancelled"}
PRIORITIES = {"low", "normal", "high", "urgent"}


def _now() -> dt.datetime:
    return dt.datetime.now(UTC)


def _parse_datetime(value: Any) -> Optional[dt.datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, dt.datetime):
        parsed = value
    elif isinstance(value, dt.date):
        parsed = dt.datetime.combine(value, dt.time.min)
    elif isinstance(value, str):
        try:
            parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("Dates must be ISO-8601 values, for example 2026-11-20T17:00:00+05:30.") from exc
    else:
        raise ValueError("Date must be an ISO-8601 string or datetime.")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _as_utc(value: Optional[dt.datetime]) -> Optional[dt.datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _uuid(value: str | uuid.UUID) -> uuid.UUID:
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("The supplied identifier is not a valid UUID.") from exc


def _iso(value: Optional[dt.datetime]) -> Optional[str]:
    value = _as_utc(value)
    return value.isoformat() if value else None


def _course_dict(row: WorkspaceCourseModel) -> Dict[str, Any]:
    return {
        "id": str(row.id), "owner_id": row.owner_id, "name": row.name, "code": row.code,
        "term": row.term, "credit_hours": row.credit_hours, "status": row.status,
        "metadata": row.metadata_json or {}, "created_at": _iso(row.created_at),
    }


def _assignment_dict(row: WorkspaceAssignmentModel, course_name: Optional[str] = None) -> Dict[str, Any]:
    return {
        "id": str(row.id), "course_id": str(row.course_id), "course_name": course_name,
        "title": row.title, "due_at": _iso(row.due_at), "status": row.status,
        "weight_pct": row.weight_pct, "score_pct": row.score_pct,
        "expected_score_pct": row.expected_score_pct, "estimated_minutes": row.estimated_minutes,
        "source_confidence": row.source_confidence, "notes": row.notes,
    }


def _task_dict(row: WorkspaceTaskModel) -> Dict[str, Any]:
    return {
        "id": str(row.id), "course_id": str(row.course_id) if row.course_id else None,
        "assignment_id": str(row.assignment_id) if row.assignment_id else None,
        "title": row.title, "description": row.description, "due_at": _iso(row.due_at),
        "status": row.status, "priority": row.priority, "estimated_minutes": row.estimated_minutes,
        "notes": row.notes, "recurrence_key": row.recurrence_key,
    }


def _capture_dict(row: WorkspaceCaptureModel) -> Dict[str, Any]:
    return {
        "id": str(row.id), "kind": row.kind, "content": row.content,
        "context": row.context_json or {}, "source": row.source, "status": row.status,
        "created_at": _iso(row.created_at), "reviewed_at": _iso(row.reviewed_at),
        "linked_memory_id": str(row.linked_memory_id) if row.linked_memory_id else None,
        "linked_task_id": str(row.linked_task_id) if row.linked_task_id else None,
    }


def _urgency(days: Optional[int]) -> float:
    if days is None:
        return 0.3
    if days < 0:
        return 3.0
    if days == 0:
        return 2.5
    if days <= 2:
        return 2.0
    if days <= 7:
        return 1.0
    return 0.3


class WorkspaceService:
    """Transactional operations for personal context and day-to-day work."""

    def __init__(self, session_factory: Callable[[], Session] = SessionFactory, owner_id: Optional[str] = None):
        self.session_factory = session_factory
        self.owner_id = owner_id or settings.jarvis_user_id

    def _write(self, operation):
        session = self.session_factory()
        try:
            result = operation(session)
            session.commit()
            return result
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _read(self, operation):
        session = self.session_factory()
        try:
            return operation(session)
        finally:
            session.close()

    def create_course(self, name: str, code: Optional[str] = None, term: Optional[str] = None,
                      credit_hours: float = 3.0, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        clean_name = str(name or "").strip()
        if not clean_name or len(clean_name) > 255:
            raise ValueError("Course name is required and must be at most 255 characters.")
        if not 0 < float(credit_hours) <= 60:
            raise ValueError("credit_hours must be greater than 0 and at most 60.")

        def op(session):
            row = WorkspaceCourseModel(owner_id=self.owner_id, name=clean_name, code=(code or "").strip() or None,
                                        term=(term or "").strip() or None, credit_hours=float(credit_hours),
                                        metadata_json=metadata or {})
            session.add(row)
            session.flush()
            return _course_dict(row)
        return self._write(op)

    def list_courses(self, include_archived: bool = False) -> list[Dict[str, Any]]:
        def op(session):
            query = session.query(WorkspaceCourseModel).filter_by(owner_id=self.owner_id)
            if not include_archived:
                query = query.filter(WorkspaceCourseModel.status == "active")
            return [_course_dict(row) for row in query.order_by(WorkspaceCourseModel.name.asc()).all()]
        return self._read(op)

    def create_assignment(self, course_id: str, title: str, due_at: Any = None, status: str = "pending",
                          weight_pct: Optional[float] = None, score_pct: Optional[float] = None,
                          expected_score_pct: float = 90.0, estimated_minutes: int = 60,
                          source_confidence: str = "manual", notes: Optional[str] = None) -> Dict[str, Any]:
        clean_title = str(title or "").strip()
        if not clean_title or len(clean_title) > 255:
            raise ValueError("Assignment title is required and must be at most 255 characters.")
        parsed_due = _parse_datetime(due_at)
        clean_status = str(status or "pending").strip().lower()
        if clean_status not in {"pending", "in_progress", "completed", "graded", "cancelled"}:
            raise ValueError("Unsupported assignment status.")
        if weight_pct is not None and not 0 <= float(weight_pct) <= 100:
            raise ValueError("weight_pct must be between 0 and 100.")
        if score_pct is not None and not 0 <= float(score_pct) <= 100:
            raise ValueError("score_pct must be between 0 and 100.")
        if not 0 <= float(expected_score_pct) <= 100:
            raise ValueError("expected_score_pct must be between 0 and 100.")
        if int(estimated_minutes) < 1 or int(estimated_minutes) > 100000:
            raise ValueError("estimated_minutes must be between 1 and 100000.")

        def op(session):
            course = session.query(WorkspaceCourseModel).filter_by(
                id=_uuid(course_id), owner_id=self.owner_id
            ).first()
            if course is None:
                raise LookupError("Course not found.")
            row = WorkspaceAssignmentModel(
                owner_id=self.owner_id, course_id=course.id, title=clean_title, due_at=parsed_due,
                status=clean_status, weight_pct=weight_pct, score_pct=score_pct,
                expected_score_pct=float(expected_score_pct), estimated_minutes=int(estimated_minutes),
                source_confidence=source_confidence, notes=notes,
            )
            session.add(row)
            session.flush()
            return _assignment_dict(row, course.name)
        return self._write(op)

    def list_assignments(self, course_id: Optional[str] = None) -> list[Dict[str, Any]]:
        def op(session):
            query = session.query(WorkspaceAssignmentModel, WorkspaceCourseModel.name).join(
                WorkspaceCourseModel, WorkspaceAssignmentModel.course_id == WorkspaceCourseModel.id
            ).filter(WorkspaceAssignmentModel.owner_id == self.owner_id)
            if course_id:
                query = query.filter(WorkspaceAssignmentModel.course_id == _uuid(course_id))
            rows = query.order_by(WorkspaceAssignmentModel.due_at.asc().nullslast()).all()
            return [_assignment_dict(row, name) for row, name in rows]
        return self._read(op)

    def create_task(self, title: str, description: str = "", due_at: Any = None, priority: str = "normal",
                    estimated_minutes: int = 30, course_id: Optional[str] = None,
                    assignment_id: Optional[str] = None, notes: Optional[str] = None,
                    recurrence_key: Optional[str] = None) -> Dict[str, Any]:
        clean_title = str(title or "").strip()
        clean_priority = str(priority or "normal").strip().lower()
        if not clean_title or len(clean_title) > 255:
            raise ValueError("Task title is required and must be at most 255 characters.")
        if clean_priority not in PRIORITIES:
            raise ValueError("priority must be low, normal, high, or urgent.")
        if int(estimated_minutes) < 1 or int(estimated_minutes) > 100000:
            raise ValueError("estimated_minutes must be between 1 and 100000.")
        parsed_due = _parse_datetime(due_at)

        def op(session):
            course_uuid = _uuid(course_id) if course_id else None
            assignment_uuid = _uuid(assignment_id) if assignment_id else None
            if course_uuid and not session.query(WorkspaceCourseModel).filter_by(
                id=course_uuid, owner_id=self.owner_id
            ).first():
                raise LookupError("Course not found.")
            if assignment_uuid and not session.query(WorkspaceAssignmentModel).filter_by(
                id=assignment_uuid, owner_id=self.owner_id
            ).first():
                raise LookupError("Assignment not found.")
            row = WorkspaceTaskModel(
                owner_id=self.owner_id, title=clean_title, description=str(description or ""),
                due_at=parsed_due, priority=clean_priority, estimated_minutes=int(estimated_minutes),
                course_id=course_uuid, assignment_id=assignment_uuid, notes=notes,
                recurrence_key=recurrence_key,
            )
            session.add(row)
            session.flush()
            return _task_dict(row)
        return self._write(op)

    def list_tasks(self, status: Optional[str] = None) -> list[Dict[str, Any]]:
        def op(session):
            query = session.query(WorkspaceTaskModel).filter_by(owner_id=self.owner_id)
            if status:
                clean_status = status.strip().lower()
                if clean_status not in TASK_STATUSES:
                    raise ValueError("Unsupported task status.")
                query = query.filter(WorkspaceTaskModel.status == clean_status)
            rows = query.order_by(WorkspaceTaskModel.due_at.asc().nullslast()).all()
            return [_task_dict(row) for row in rows]
        return self._read(op)

    def complete_task(self, task_id: str) -> Dict[str, Any]:
        def op(session):
            row = session.query(WorkspaceTaskModel).filter_by(
                id=_uuid(task_id), owner_id=self.owner_id
            ).first()
            if row is None:
                raise LookupError("Task not found.")
            row.status = "completed"
            session.flush()
            return _task_dict(row)
        return self._write(op)

    def create_capture(self, kind: str, content: str, context: Optional[Dict[str, Any]] = None,
                       source: str = "chat") -> Dict[str, Any]:
        clean_kind = str(kind or "").strip().lower()
        clean_content = str(content or "").strip()
        if clean_kind not in CAPTURE_KINDS:
            raise ValueError("Capture kind must be note, fact, idea, or task.")
        if not clean_content or len(clean_content) > 20000:
            raise ValueError("Capture content is required and must be at most 20000 characters.")

        def op(session):
            row = WorkspaceCaptureModel(
                owner_id=self.owner_id, kind=clean_kind, content=clean_content,
                context_json=context or {}, source=(source or "chat")[:120], status="pending",
            )
            session.add(row)
            session.flush()
            return _capture_dict(row)
        return self._write(op)

    def list_captures(self, status: Optional[str] = "pending") -> list[Dict[str, Any]]:
        def op(session):
            query = session.query(WorkspaceCaptureModel).filter_by(owner_id=self.owner_id)
            if status:
                query = query.filter(WorkspaceCaptureModel.status == status.strip().lower())
            rows = query.order_by(WorkspaceCaptureModel.created_at.desc()).limit(500).all()
            return [_capture_dict(row) for row in rows]
        return self._read(op)

    def review_capture(self, capture_id: str, approved: bool) -> Dict[str, Any]:
        def op(session):
            row = session.query(WorkspaceCaptureModel).filter_by(
                id=_uuid(capture_id), owner_id=self.owner_id
            ).with_for_update().first()
            if row is None:
                raise LookupError("Capture not found.")
            if row.status != "pending":
                raise ValueError("This capture has already been reviewed.")
            row.reviewed_at = _now()
            if not approved:
                row.status = "dismissed"
                session.flush()
                return _capture_dict(row)

            context = row.context_json or {}
            if row.kind == "task":
                title = str(context.get("title") or row.content).strip()
                course_uuid = _uuid(context["course_id"]) if context.get("course_id") else None
                if course_uuid and not session.query(WorkspaceCourseModel).filter_by(
                    id=course_uuid, owner_id=self.owner_id
                ).first():
                    raise LookupError("Course not found for captured task.")
                task = WorkspaceTaskModel(
                    owner_id=self.owner_id,
                    title=title[:255],
                    description=str(context.get("description") or ""),
                    due_at=_parse_datetime(context.get("due_at")),
                    priority=str(context.get("priority") or "normal").lower(),
                    estimated_minutes=int(context.get("estimated_minutes") or 30),
                    course_id=course_uuid,
                )
                if task.priority not in PRIORITIES:
                    raise ValueError("Captured task priority is invalid.")
                session.add(task)
                session.flush()
                row.linked_task_id = task.id
            else:
                memory = MemoryModel(
                    category="workspace_" + row.kind,
                    content={"text": row.content, "context": context, "source": row.source},
                    importance_score=1.0,
                )
                session.add(memory)
                session.flush()
                row.linked_memory_id = memory.id
            row.status = "approved"
            session.flush()
            return _capture_dict(row)
        return self._write(op)

    def daily_briefing(self, now: Optional[dt.datetime] = None, horizon_days: int = 7) -> Dict[str, Any]:
        if not 0 <= int(horizon_days) <= 365:
            raise ValueError("horizon_days must be between 0 and 365.")
        current = _as_utc(now or _now())
        cutoff = current + dt.timedelta(days=int(horizon_days))

        def op(session):
            tasks = session.query(WorkspaceTaskModel).filter(
                WorkspaceTaskModel.owner_id == self.owner_id,
                WorkspaceTaskModel.status.in_(["todo", "in_progress"]),
            ).all()
            assignments = session.query(WorkspaceAssignmentModel, WorkspaceCourseModel.name).join(
                WorkspaceCourseModel, WorkspaceAssignmentModel.course_id == WorkspaceCourseModel.id
            ).filter(
                WorkspaceAssignmentModel.owner_id == self.owner_id,
                WorkspaceAssignmentModel.status.in_(["pending", "in_progress"]),
            ).all()

            next_actions = []
            overdue = 0
            due_today = 0
            for task in tasks:
                due = _as_utc(task.due_at)
                if due and due > cutoff:
                    continue
                days = (due.date() - current.date()).days if due else None
                factor = {"urgent": 2.0, "high": 1.5, "normal": 1.0, "low": 0.7}[task.priority]
                score = _urgency(days) * factor
                reason = "No due date; ranked by priority." if days is None else (
                    "Overdue." if days < 0 else "Due today." if days == 0 else
                    f"Due in {days} day(s)."
                )
                if days is not None and days < 0:
                    overdue += 1
                if days == 0:
                    due_today += 1
                next_actions.append({
                    "item_type": "task", "id": str(task.id), "title": task.title,
                    "due_at": _iso(task.due_at), "priority": task.priority,
                    "score": round(score, 4), "reason": reason, "status": task.status,
                })

            for assignment, course_name in assignments:
                due = _as_utc(assignment.due_at)
                if due and due > cutoff:
                    continue
                days = (due.date() - current.date()).days if due else None
                weight_factor = max(float(assignment.weight_pct or 0), 5.0) / 100.0
                score = _urgency(days) * weight_factor
                if days is None:
                    reason = "No due date; review when convenient."
                elif days < 0:
                    reason = "Overdue."
                elif days == 0:
                    reason = "Due today."
                elif assignment.weight_pct is not None:
                    reason = f"Due in {days} day(s), worth {assignment.weight_pct}% in {course_name}."
                else:
                    reason = f"Due in {days} day(s) in {course_name}."
                if days is not None and days < 0:
                    overdue += 1
                if days == 0:
                    due_today += 1
                next_actions.append({
                    "item_type": "assignment", "id": str(assignment.id), "title": assignment.title,
                    "course_name": course_name, "due_at": _iso(assignment.due_at),
                    "weight_pct": assignment.weight_pct, "score": round(score, 4),
                    "reason": reason, "status": assignment.status,
                })

            next_actions.sort(key=lambda item: (-item["score"], item["due_at"] or "9999"))
            goal_rows = session.query(GoalModel).filter(
                GoalModel.created_by == self.owner_id, GoalModel.status.in_(["PENDING", "RUNNING"])
            ).order_by(GoalModel.created_at.desc()).limit(20).all()
            goals = [{"id": str(g.id), "title": g.title, "description": g.description,
                      "priority": g.priority, "status": g.status} for g in goal_rows]
            return {
                "generated_at": current.isoformat(),
                "horizon_days": int(horizon_days),
                "summary": {
                    "open_tasks": len(tasks), "open_assignments": len(assignments),
                    "overdue_items": overdue, "due_today": due_today, "active_goals": len(goals),
                },
                "next_actions": next_actions[:20],
                "tasks": [_task_dict(task) for task in tasks],
                "active_goals": goals,
                "ranking": "deterministic_deadline_priority_v1",
            }
        return self._read(op)


workspace_service = WorkspaceService()
