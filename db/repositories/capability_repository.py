"""
Capability Repository
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional
import sqlalchemy as sa
from sqlalchemy.orm import Session

from db.models.capability import CapabilityModel
from db.repositories.base import BaseRepository


class CapabilityRepository(BaseRepository[CapabilityModel]):
    def __init__(self, session: Session):
        super().__init__(session, CapabilityModel)

    def get_by_name(self, name: str) -> Optional[CapabilityModel]:
        stmt = sa.select(CapabilityModel).where(CapabilityModel.name == name)
        return self.session.scalars(stmt).first()

    def list_by_level(self, level: str) -> List[CapabilityModel]:
        stmt = sa.select(CapabilityModel).where(CapabilityModel.level == level)
        return list(self.session.scalars(stmt).all())

    def find_missing(self) -> List[CapabilityModel]:
        stmt = sa.select(CapabilityModel).where(CapabilityModel.level == "MISSING")
        return list(self.session.scalars(stmt).all())

    def upsert_capability(
        self,
        name: str,
        level: str = "EXPERIMENTAL",
        category: str = "general",
        description: str = "",
        required_tools: Optional[List[str]] = None,
        success_rate: float = 1.0,
        metadata_json: Optional[Dict[str, Any]] = None,
    ) -> CapabilityModel:
        existing = self.get_by_name(name)
        if existing:
            existing.level = level
            existing.category = category
            existing.description = description or existing.description
            if required_tools is not None:
                existing.required_tools = required_tools
            existing.success_rate = success_rate
            if metadata_json:
                existing.metadata_json = metadata_json
            self.session.flush()
            return existing
        else:
            cap = CapabilityModel(
                name=name,
                level=level,
                category=category,
                description=description,
                required_tools=required_tools or [],
                success_rate=success_rate,
                metadata_json=metadata_json or {},
            )
            return self.create(cap)
