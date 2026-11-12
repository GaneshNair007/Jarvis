"""Unit tests for the Nūs-inspired JARVIS personal workspace."""

import datetime as dt

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from jarvis.db.models import Base, MemoryModel
from jarvis.db.models.workspace import WorkspaceTaskModel
from jarvis.workspace.service import WorkspaceService

UTC = dt.timezone.utc


def make_service():
    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    return WorkspaceService(factory, owner_id="ganesh-test"), engine, factory


def test_course_assignment_and_task_persist():
    service, engine, _factory = make_service()
    try:
        course = service.create_course("Supervised Machine Learning", code="SML", term="2026-27")
        assignment = service.create_assignment(
            course["id"], "Classification practical", due_at="2026-11-20T10:00:00+05:30", weight_pct=20
        )
        task = service.create_task("Prepare viva", course_id=course["id"], due_at="2026-11-19T09:00:00Z")
        assert service.list_courses()[0]["name"] == "Supervised Machine Learning"
        assert service.list_assignments(course["id"])[0]["id"] == assignment["id"]
        assert service.list_tasks()[0]["id"] == task["id"]
    finally:
        engine.dispose()


def test_capture_is_not_memory_until_approved():
    service, engine, factory = make_service()
    try:
        capture = service.create_capture("fact", "User prefers Ollama as the primary model.")
        session = factory()
        try:
            assert session.query(MemoryModel).count() == 0
        finally:
            session.close()

        reviewed = service.review_capture(capture["id"], approved=True)
        assert reviewed["status"] == "approved"
        assert reviewed["linked_memory_id"]
        session = factory()
        try:
            memory = session.query(MemoryModel).one()
            assert memory.content["text"] == "User prefers Ollama as the primary model."
        finally:
            session.close()
    finally:
        engine.dispose()


def test_approved_task_capture_creates_a_task_but_pending_capture_does_not():
    service, engine, factory = make_service()
    try:
        capture = service.create_capture(
            "task",
            "Revise graph theory",
            context={"due_at": "2026-11-18T10:00:00Z", "priority": "high"},
        )
        session = factory()
        try:
            assert session.query(WorkspaceTaskModel).count() == 0
        finally:
            session.close()

        approved = service.review_capture(capture["id"], approved=True)
        assert approved["linked_task_id"]
        assert service.list_tasks()[0]["title"] == "Revise graph theory"
    finally:
        engine.dispose()


def test_dismiss_capture_does_not_create_memory_or_task():
    service, engine, factory = make_service()
    try:
        capture = service.create_capture("note", "Temporary note.")
        dismissed = service.review_capture(capture["id"], approved=False)
        assert dismissed["status"] == "dismissed"
        session = factory()
        try:
            assert session.query(MemoryModel).count() == 0
            assert session.query(WorkspaceTaskModel).count() == 0
        finally:
            session.close()
    finally:
        engine.dispose()


def test_daily_briefing_ranks_overdue_task_ahead_of_future_deadline():
    service, engine, _factory = make_service()
    now = dt.datetime(2026, 11, 13, 12, tzinfo=UTC)
    try:
        course = service.create_course("Discrete Mathematics")
        service.create_assignment(
            course["id"], "High-weight exam", due_at=now + dt.timedelta(days=1), weight_pct=60
        )
        service.create_task("Overdue report", due_at=now - dt.timedelta(days=1), priority="high")
        briefing = service.daily_briefing(now=now, horizon_days=7)
        assert briefing["summary"]["overdue_items"] == 1
        assert briefing["next_actions"][0]["title"] == "Overdue report"
        assert briefing["ranking"] == "deterministic_deadline_priority_v1"
    finally:
        engine.dispose()


def test_completed_tasks_are_removed_from_daily_open_actions():
    service, engine, _factory = make_service()
    try:
        task = service.create_task("Submit lab report")
        service.complete_task(task["id"])
        briefing = service.daily_briefing()
        assert briefing["summary"]["open_tasks"] == 0
        assert all(item["title"] != "Submit lab report" for item in briefing["next_actions"])
    finally:
        engine.dispose()


def test_bad_dates_and_invalid_capture_kinds_are_rejected():
    service, engine, _factory = make_service()
    try:
        try:
            service.create_task("Bad date", due_at="tomorrow maybe")
            assert False, "bad date should raise ValueError"
        except ValueError:
            pass
        try:
            service.create_capture("random", "content")
            assert False, "bad kind should raise ValueError"
        except ValueError:
            pass
    finally:
        engine.dispose()
