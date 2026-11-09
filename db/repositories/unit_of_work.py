"""
Unit of Work Pattern for SQLAlchemy 2.x
Manages atomic transactions and repository lifecycle.
"""

from __future__ import annotations

from typing import Optional
from sqlalchemy.orm import Session, sessionmaker

from db.repositories.goal_repository import GoalRepository
from db.repositories.task_repository import TaskRepository
from db.repositories.dependency_repository import DependencyRepository
from db.repositories.agent_repository import AgentRepository
from db.repositories.assignment_repository import AssignmentRepository
from db.repositories.execution_repository import ExecutionRepository
from db.repositories.memory_repository import MemoryRepository
from db.repositories.reflection_repository import ReflectionRepository
from db.repositories.capability_repository import CapabilityRepository
from db.repositories.improvement_repository import ImprovementRepository
from db.repositories.audit_repository import AuditRepository


class UnitOfWork:
    """
    Unit of Work context manager ensuring ACID transactional boundaries
    and providing unified access to all repositories on the active session.
    """

    def __init__(self, session_factory: sessionmaker[Session]):
        self.session_factory = session_factory
        self.session: Optional[Session] = None

    def __enter__(self) -> UnitOfWork:
        self.session = self.session_factory()
        self.goals = GoalRepository(self.session)
        self.tasks = TaskRepository(self.session)
        self.dependencies = DependencyRepository(self.session)
        self.agents = AgentRepository(self.session)
        self.assignments = AssignmentRepository(self.session)
        self.executions = ExecutionRepository(self.session)
        self.memories = MemoryRepository(self.session)
        self.reflections = ReflectionRepository(self.session)
        self.capabilities = CapabilityRepository(self.session)
        self.improvements = ImprovementRepository(self.session)
        self.audits = AuditRepository(self.session)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            if exc_type is not None:
                self.session.rollback()
            else:
                try:
                    self.session.commit()
                except Exception:
                    self.session.rollback()
                    raise
            self.session.close()

    def commit(self) -> None:
        if self.session:
            self.session.commit()

    def rollback(self) -> None:
        if self.session:
            self.session.rollback()
