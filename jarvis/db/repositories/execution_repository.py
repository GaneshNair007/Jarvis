"""
JARVIS Execution Repository
Tracks tool calls, latencies, payloads, and execution results for auditing and telemetry.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any, Dict, List, Optional
import sqlalchemy as sa
from sqlalchemy.orm import Session

from jarvis.db.models.execution import ExecutionModel
from jarvis.db.repositories.base import BaseRepository


class ExecutionRepository(BaseRepository[ExecutionModel]):
    def __init__(self, session: Session):
        super().__init__(session, ExecutionModel)

    def record_execution(
        self,
        task_id: uuid.UUID,
        tool_name: str,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        status: str = "SUCCESS",
        execution_time: float = 0.0,
        agent_id: Optional[uuid.UUID] = None,
        execution_id: Optional[uuid.UUID] = None,
    ) -> ExecutionModel:
        """Records an execution event forever in the database."""
        exec_record = ExecutionModel(
            id=execution_id or uuid.uuid4(),
            task_id=task_id,
            agent_id=agent_id,
            tool_name=tool_name,
            input_data=input_data,
            output_data=output_data,
            status=status.upper(),
            execution_time=execution_time,
            created_at=datetime.datetime.now(datetime.timezone.utc),
        )
        self.session.add(exec_record)
        return exec_record

    def get_execution(self, execution_id: uuid.UUID) -> Optional[ExecutionModel]:
        return self.session.query(ExecutionModel).filter(ExecutionModel.id == execution_id).first()

    def get_task_executions(self, task_id: uuid.UUID) -> List[ExecutionModel]:
        """Returns all tool executions recorded for a given task."""
        return (
            self.session.query(ExecutionModel)
            .filter(ExecutionModel.task_id == task_id)
            .order_by(ExecutionModel.created_at.asc())
            .all()
        )

    def get_agent_executions(self, agent_id: uuid.UUID, limit: int = 50) -> List[ExecutionModel]:
        """Returns recent tool executions performed by a given agent."""
        return (
            self.session.query(ExecutionModel)
            .filter(ExecutionModel.agent_id == agent_id)
            .order_by(ExecutionModel.created_at.desc())
            .limit(limit)
            .all()
        )
