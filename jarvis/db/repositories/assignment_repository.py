"""
JARVIS Agent Assignment Repository
Tracks delegation records linking tasks to assigned worker agents.
"""

from __future__ import annotations

import datetime
import uuid
from typing import List, Optional
import sqlalchemy as sa
from sqlalchemy.orm import Session

from jarvis.db.models.assignment import AssignmentModel
from jarvis.db.repositories.base import BaseRepository


class AssignmentRepository(BaseRepository[AssignmentModel]):
    def __init__(self, session: Session):
        super().__init__(session, AssignmentModel)

    def assign_task(self, task_id: uuid.UUID, agent_id: uuid.UUID) -> AssignmentModel:
        """Creates an assignment record binding task to agent."""
        assignment = AssignmentModel(
            id=uuid.uuid4(),
            task_id=task_id,
            agent_id=agent_id,
            assigned_at=datetime.datetime.now(datetime.timezone.utc),
            completed_at=None,
        )
        self.session.add(assignment)
        return assignment

    def active_assignments(self) -> List[AssignmentModel]:
        """Returns all assignments currently pending or in-progress."""
        return self.session.query(AssignmentModel).filter(AssignmentModel.completed_at.is_(None)).all()

    def completed_assignments(self) -> List[AssignmentModel]:
        """Returns all completed assignments."""
        return self.session.query(AssignmentModel).filter(AssignmentModel.completed_at.isnot(None)).all()

    def complete_assignment(self, assignment_id: uuid.UUID) -> Optional[AssignmentModel]:
        """Marks assignment as completed with UTC timestamp."""
        assignment = self.session.query(AssignmentModel).filter(AssignmentModel.id == assignment_id).first()
        if assignment:
            assignment.completed_at = datetime.datetime.now(datetime.timezone.utc)
            self.session.add(assignment)
        return assignment
