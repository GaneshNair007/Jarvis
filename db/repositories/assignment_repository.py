"""
Assignment Repository
"""

from __future__ import annotations

import datetime
import uuid
from typing import List, Optional
import sqlalchemy as sa
from sqlalchemy.orm import Session

from db.models.assignment import AssignmentModel
from db.repositories.base import BaseRepository


class AssignmentRepository(BaseRepository[AssignmentModel]):
    def __init__(self, session: Session):
        super().__init__(session, AssignmentModel)

    def get_by_task(self, task_id: uuid.UUID | str) -> Optional[AssignmentModel]:
        if isinstance(task_id, str):
            task_id = uuid.UUID(task_id)
        stmt = (
            sa.select(AssignmentModel)
            .where(AssignmentModel.task_id == task_id)
            .order_by(AssignmentModel.assigned_at.desc())
        )
        return self.session.scalars(stmt).first()

    def list_by_agent(self, agent_id: uuid.UUID | str) -> List[AssignmentModel]:
        if isinstance(agent_id, str):
            agent_id = uuid.UUID(agent_id)
        stmt = sa.select(AssignmentModel).where(AssignmentModel.agent_id == agent_id)
        return list(self.session.scalars(stmt).all())

    def complete_assignment(self, assignment_id: uuid.UUID | str) -> Optional[AssignmentModel]:
        assignment = self.get_by_id(assignment_id)
        if assignment:
            assignment.status = "COMPLETED"
            assignment.completed_at = datetime.datetime.now(datetime.timezone.utc)
            self.session.flush()
        return assignment
