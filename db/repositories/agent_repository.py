"""
Agent Repository
"""

from __future__ import annotations

import uuid
from typing import List, Optional
import sqlalchemy as sa
from sqlalchemy.orm import Session

from db.models.agent import AgentModel
from db.repositories.base import BaseRepository


class AgentRepository(BaseRepository[AgentModel]):
    def __init__(self, session: Session):
        super().__init__(session, AgentModel)

    def get_by_key(self, agent_key: str) -> Optional[AgentModel]:
        stmt = sa.select(AgentModel).where(AgentModel.agent_key == agent_key)
        return self.session.scalars(stmt).first()

    def list_by_department(self, department_id: uuid.UUID | str) -> List[AgentModel]:
        if isinstance(department_id, str):
            department_id = uuid.UUID(department_id)
        stmt = sa.select(AgentModel).where(AgentModel.department_id == department_id)
        return list(self.session.scalars(stmt).all())

    def list_active(self) -> List[AgentModel]:
        return self.list(status="ACTIVE")
