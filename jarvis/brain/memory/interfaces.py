"""Abstract Base Classes & Interfaces for Brain Memory Subsystems."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional
from jarvis.brain.schemas import CanonicalMemoryRecord, MemoryQueryFilter


class MemoryRepositoryInterface(ABC):
    """Authoritative persistent repository interface for canonical memory records."""

    @abstractmethod
    def add(self, record: CanonicalMemoryRecord) -> CanonicalMemoryRecord:
        """Persist a canonical memory record."""
        pass

    @abstractmethod
    def get_by_id(self, memory_id: str, user_id: str) -> Optional[CanonicalMemoryRecord]:
        """Retrieve a specific memory record enforcing user ownership."""
        pass

    @abstractmethod
    def search(self, filters: MemoryQueryFilter) -> List[CanonicalMemoryRecord]:
        """Search and filter records by user, project, category, and status."""
        pass

    @abstractmethod
    def correct(
        self,
        memory_id: str,
        user_id: str,
        new_content: str,
        supersedes_id: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> Optional[CanonicalMemoryRecord]:
        """Supercede an existing record with a corrected factual assertion."""
        pass

    @abstractmethod
    def delete(self, memory_id: str, user_id: str, hard_delete: bool = False) -> bool:
        """Soft delete (tombstone) or purge an authoritative memory record."""
        pass

    @abstractmethod
    def delete_by_project(self, user_id: str, project_id: str) -> int:
        """Prune all memory records associated with a specific project."""
        pass
