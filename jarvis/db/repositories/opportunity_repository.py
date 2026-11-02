"""
JARVIS Opportunity Repository
Career and competitive intelligence database queries (Hackathons, Internships, Jobs, Grants).
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any, Dict, List, Optional
import sqlalchemy as sa
from sqlalchemy.orm import Session

from jarvis.db.models.opportunity import OpportunityModel
from jarvis.db.repositories.base import BaseRepository


class OpportunityRepository(BaseRepository[OpportunityModel]):

    def __init__(self, session: Session):
        super().__init__(session, OpportunityModel)

    def record_opportunity(
        self,
        opportunity_type: str,
        title: str,
        source: str,
        score: float,
        justification: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        opportunity_id: Optional[uuid.UUID] = None,
    ) -> OpportunityModel:
        """Stores a high-value opportunity found during web scout tasks."""
        opp = OpportunityModel(
            id=opportunity_id or uuid.uuid4(),
            opportunity_type=opportunity_type.lower(),
            source=source,
            title=title,
            score=max(0.0, min(1.0, score)),
            justification=justification,
            metadata_json=metadata or {},
            discovered_at=datetime.datetime.now(datetime.timezone.utc),
        )
        self.session.add(opp)
        return opp

    def get_top_opportunities(self, limit: int = 10) -> List[OpportunityModel]:
        """Returns opportunities ranked by highest relevance score."""
        return (
            self.session.query(OpportunityModel)
            .order_by(OpportunityModel.score.desc())
            .limit(limit)
            .all()
        )

    def get_recent_opportunities(self, limit: int = 10) -> List[OpportunityModel]:
        """Returns newest opportunities discovered."""
        return (
            self.session.query(OpportunityModel)
            .order_by(OpportunityModel.discovered_at.desc())
            .limit(limit)
            .all()
        )

    def get_best_hackathons(self, min_score: float = 0.75, limit: int = 10) -> List[OpportunityModel]:
        """Filters high-value hackathons."""
        return (
            self.session.query(OpportunityModel)
            .filter(
                OpportunityModel.opportunity_type == "hackathon",
                OpportunityModel.score >= min_score,
            )
            .order_by(OpportunityModel.score.desc())
            .limit(limit)
            .all()
        )

    def filter_by_type(self, opportunity_type: str, limit: int = 20) -> List[OpportunityModel]:
        return (
            self.session.query(OpportunityModel)
            .filter(OpportunityModel.opportunity_type == opportunity_type.lower())
            .order_by(OpportunityModel.score.desc())
            .limit(limit)
            .all()
        )
