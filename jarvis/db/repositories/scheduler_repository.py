"""
JARVIS Scheduler Repository
Autonomous recurring schedule database queries and execution triggers.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any, Dict, List, Optional
import sqlalchemy as sa
from sqlalchemy.orm import Session

from jarvis.db.models.schedule import ScheduleModel
from jarvis.db.repositories.base import BaseRepository


class SchedulerRepository(BaseRepository[ScheduleModel]):

    def __init__(self, session: Session):
        super().__init__(session, ScheduleModel)

    def add_schedule(
        self,
        task_name: str,
        cron_expression: str,
        enabled: bool = True,
        next_run: Optional[datetime.datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
        schedule_id: Optional[uuid.UUID] = None,
    ) -> ScheduleModel:
        """Schedules recurring autonomous operations."""
        sched = ScheduleModel(
            id=schedule_id or uuid.uuid4(),
            task_name=task_name,
            cron_expression=cron_expression,
            enabled=enabled,
            last_run=None,
            next_run=next_run or datetime.datetime.now(datetime.timezone.utc),
            metadata_json=metadata or {},
        )
        self.session.add(sched)
        return sched

    def enable_schedule(self, schedule_id: uuid.UUID) -> Optional[ScheduleModel]:
        sched = self.session.query(ScheduleModel).filter(ScheduleModel.id == schedule_id).first()
        if sched:
            sched.enabled = True
            self.session.add(sched)
        return sched

    def disable_schedule(self, schedule_id: uuid.UUID) -> Optional[ScheduleModel]:
        sched = self.session.query(ScheduleModel).filter(ScheduleModel.id == schedule_id).first()
        if sched:
            sched.enabled = False
            self.session.add(sched)
        return sched

    def get_due_schedules(self, current_time: Optional[datetime.datetime] = None) -> List[ScheduleModel]:
        """Returns all enabled schedules whose next_run timestamp is <= current_time."""
        now = current_time or datetime.datetime.now(datetime.timezone.utc)
        return (
            self.session.query(ScheduleModel)
            .filter(
                ScheduleModel.enabled.is_(True),
                ScheduleModel.next_run <= now,
            )
            .all()
        )

    def update_run_time(
        self,
        schedule_id: uuid.UUID,
        last_run: Optional[datetime.datetime] = None,
        next_run: Optional[datetime.datetime] = None,
    ) -> Optional[ScheduleModel]:
        sched = self.session.query(ScheduleModel).filter(ScheduleModel.id == schedule_id).first()
        if sched:
            sched.last_run = last_run or datetime.datetime.now(datetime.timezone.utc)
            if next_run:
                sched.next_run = next_run
            self.session.add(sched)
        return sched
