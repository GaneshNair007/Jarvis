"""
JARVIS Opportunity Service
Career intelligence service discovering, ranking, and notifying high-value hackathons & internships.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from jarvis.db.unit_of_work import UnitOfWork
from jarvis.db.models.opportunity import OpportunityModel
from jarvis.db.events import event_bus, OpportunityDiscoveredEvent
from jarvis.core.logger import get_logger

logger = get_logger("services.opportunity")


class OpportunityService:

    def __init__(self, uow_factory=UnitOfWork):
        self.uow_factory = uow_factory

    def ingest_opportunity(
        self,
        opportunity_type: str,
        title: str,
        source: str,
        score: float,
        justification: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> OpportunityModel:
        """Stores new opportunity and broadcasts discovery event."""
        with self.uow_factory() as uow:
            opp = uow.opportunities.record_opportunity(
                opportunity_type=opportunity_type,
                title=title,
                source=source,
                score=score,
                justification=justification,
                metadata=metadata,
            )
            uow.commit()

            event_bus.publish(OpportunityDiscoveredEvent(
                opportunity_id=str(opp.id),
                opportunity_type=opp.opportunity_type,
                title=opp.title,
                score=opp.score,
                source=opp.source,
            ))
            logger.info(f"Opportunity discovered: '{title}' [{opportunity_type}] (Score: {score})")
            return opp

    def get_top_hackathons(self, min_score: float = 0.75, limit: int = 10) -> List[OpportunityModel]:
        with self.uow_factory() as uow:
            return uow.opportunities.get_best_hackathons(min_score=min_score, limit=limit)

    def get_top_internships(self, limit: int = 10) -> List[OpportunityModel]:
        with self.uow_factory() as uow:
            return uow.opportunities.filter_by_type("internship", limit=limit)
