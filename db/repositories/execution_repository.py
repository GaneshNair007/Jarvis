"""
Execution Repository
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any, Dict, List, Optional
import sqlalchemy as sa
from sqlalchemy.orm import Session

from db.models.execution import ExecutionModel
from db.repositories.base import BaseRepository


class ExecutionRepository(BaseRepository[ExecutionModel]):
    def __init__(self, session: Session):
        super().__init__(session, ExecutionModel)

    def get_by_task(self, task_id: uuid.UUID | str) -> List[ExecutionModel]:
        if isinstance(task_id, str):
            task_id = uuid.UUID(task_id)
        stmt = (
            sa.select(ExecutionModel)
            .where(ExecutionModel.task_id == task_id)
            .order_by(ExecutionModel.started_at.desc())
        )
        return list(self.session.scalars(stmt).all())

    def record_execution(
        self,
        task_id: uuid.UUID | str,
        goal_id: uuid.UUID | str,
        status: str,
        outputs: Dict[str, Any],
        duration_seconds: float,
        agent_id: Optional[uuid.UUID | str] = None,
        verification_score: Optional[float] = None,
        verification_passed: Optional[bool] = None,
        error_message: Optional[str] = None,
    ) -> ExecutionModel:
        if isinstance(task_id, str):
            task_id = uuid.UUID(task_id)
        if isinstance(goal_id, str):
            goal_id = uuid.UUID(goal_id)
        if agent_id and isinstance(agent_id, str):
            agent_id = uuid.UUID(agent_id)

        now = datetime.datetime.now(datetime.timezone.utc)
        execution = ExecutionModel(
            task_id=task_id,
            goal_id=goal_id,
            agent_id=agent_id,
            status=status,
            started_at=now - datetime.timedelta(seconds=duration_seconds),
            finished_at=now,
            duration_seconds=duration_seconds,
            outputs=outputs,
            verification_score=verification_score,
            verification_passed=verification_passed,
            error_message=error_message,
        )
        return self.create(execution)
