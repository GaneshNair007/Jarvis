"""
Capability Service (Database Synchronization Layer)
Loads capabilities from PostgreSQL database into memory on startup and persists updates.
"""

from __future__ import annotations

from typing import List, Optional
from sqlalchemy.orm import Session

from jarvis.capabilities.models import CapabilityLevel, CapabilitySchema
from jarvis.capabilities.registry import CapabilityRegistry, capability_registry
from db.repositories.capability_repository import CapabilityRepository
from jarvis.core.logger import get_logger

logger = get_logger("capabilities.service")


class CapabilityService:
    """Service synchronizing the in-memory registry with persistent database storage."""

    def __init__(self, registry: Optional[CapabilityRegistry] = None):
        self.registry = registry or capability_registry

    def sync_from_database(self, session: Session) -> int:
        """Loads all capabilities from the database into the runtime registry."""
        repo = CapabilityRepository(session)
        db_caps = repo.list(limit=500)
        loaded = 0
        for db_cap in db_caps:
            try:
                level_enum = CapabilityLevel(db_cap.level)
            except ValueError:
                level_enum = CapabilityLevel.EXPERIMENTAL

            self.registry.register_capability(
                name=db_cap.name,
                level=level_enum,
                category=db_cap.category,
                description=db_cap.description,
                required_tools=db_cap.required_tools,
                success_rate=db_cap.success_rate,
                metadata=db_cap.metadata_json,
            )
            loaded += 1
        logger.info(f"CapabilityService: Synchronized {loaded} capabilities from database.")
        return loaded

    def persist_to_database(self, session: Session, name: str) -> bool:
        """Flushes an in-memory capability to the database."""
        caps = [c for c in self.registry.list_capabilities() if c.name == name]
        if not caps:
            return False
        cap = caps[0]
        repo = CapabilityRepository(session)
        repo.upsert_capability(
            name=cap.name,
            level=cap.level.value,
            category=cap.category,
            description=cap.description,
            required_tools=cap.required_tools,
            success_rate=cap.success_rate,
            metadata_json=cap.metadata,
        )
        session.flush()
        return True
