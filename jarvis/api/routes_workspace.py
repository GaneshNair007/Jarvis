"""REST API for JARVIS's personal workspace."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from jarvis.workspace.service import workspace_service

router = APIRouter(prefix="/workspace", tags=["Personal Workspace"])


class CourseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    code: Optional[str] = Field(default=None, max_length=80)
    term: Optional[str] = Field(default=None, max_length=120)
    credit_hours: float = Field(default=3.0, gt=0, le=60)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AssignmentCreate(BaseModel):
    course_id: str
    title: str = Field(min_length=1, max_length=255)
    due_at: Optional[datetime] = None
    status: str = "pending"
    weight_pct: Optional[float] = Field(default=None, ge=0, le=100)
    score_pct: Optional[float] = Field(default=None, ge=0, le=100)
    expected_score_pct: float = Field(default=90, ge=0, le=100)
    estimated_minutes: int = Field(default=60, ge=1, le=100000)
    source_confidence: str = "manual"
    notes: Optional[str] = None


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = ""
    due_at: Optional[datetime] = None
    priority: str = "normal"
    estimated_minutes: int = Field(default=30, ge=1, le=100000)
    course_id: Optional[str] = None
    assignment_id: Optional[str] = None
    notes: Optional[str] = None
    recurrence_key: Optional[str] = None


class CaptureCreate(BaseModel):
    kind: str
    content: str = Field(min_length=1, max_length=20000)
    context: Dict[str, Any] = Field(default_factory=dict)
    source: str = "chat"


class CaptureReview(BaseModel):
    approved: bool


def _call(operation):
    try:
        return operation()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/courses")
def list_courses(include_archived: bool = False):
    return {"courses": workspace_service.list_courses(include_archived=include_archived)}


@router.post("/courses", status_code=201)
def create_course(request: CourseCreate):
    return _call(lambda: workspace_service.create_course(**request.model_dump()))


@router.get("/assignments")
def list_assignments(course_id: Optional[str] = None):
    return _call(lambda: {"assignments": workspace_service.list_assignments(course_id=course_id)})


@router.post("/assignments", status_code=201)
def create_assignment(request: AssignmentCreate):
    return _call(lambda: workspace_service.create_assignment(**request.model_dump()))


@router.get("/tasks")
def list_tasks(status: Optional[str] = Query(default=None)):
    return _call(lambda: {"tasks": workspace_service.list_tasks(status=status)})


@router.post("/tasks", status_code=201)
def create_task(request: TaskCreate):
    return _call(lambda: workspace_service.create_task(**request.model_dump()))


@router.post("/tasks/{task_id}/complete")
def complete_task(task_id: str):
    return _call(lambda: workspace_service.complete_task(task_id))


@router.get("/captures")
def list_captures(status: Optional[str] = "pending"):
    return {"captures": workspace_service.list_captures(status=status)}


@router.post("/captures", status_code=201)
def create_capture(request: CaptureCreate):
    return _call(lambda: workspace_service.create_capture(**request.model_dump()))


@router.post("/captures/{capture_id}/review")
def review_capture(capture_id: str, request: CaptureReview):
    return _call(lambda: workspace_service.review_capture(capture_id, approved=request.approved))


@router.get("/briefing/today")
def today_briefing(horizon_days: int = Query(default=7, ge=0, le=365)):
    return _call(lambda: workspace_service.daily_briefing(horizon_days=horizon_days))
