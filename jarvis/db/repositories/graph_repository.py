"""
JARVIS Knowledge Graph Repository
Models interconnected entities, tools, domains, and skills across nodes and weighted edges.
Compatible with SQLite/Postgres and ready for Neo4j synchronization.
"""

from __future__ import annotations

import uuid
from collections import deque
from typing import Any, Dict, List, Optional, Set
import sqlalchemy as sa
from sqlalchemy.orm import Session

from jarvis.db.models.knowledge import KnowledgeNodeModel, KnowledgeEdgeModel
from jarvis.db.repositories.base import BaseRepository


class KnowledgeGraphRepository(BaseRepository[KnowledgeNodeModel]):

    def __init__(self, session: Session):
        super().__init__(session, KnowledgeNodeModel)

    def create_node(
        self,
        node_type: str,
        name: str,
        metadata: Optional[Dict[str, Any]] = None,
        node_id: Optional[uuid.UUID] = None,
    ) -> KnowledgeNodeModel:
        """Creates a knowledge entity node."""
        node = KnowledgeNodeModel(
            id=node_id or uuid.uuid4(),
            node_type=node_type.lower(),
            name=name,
            metadata_json=metadata or {},
        )
        self.session.add(node)
        return node

    def get_node_by_name(self, name: str, node_type: Optional[str] = None) -> Optional[KnowledgeNodeModel]:
        query = self.session.query(KnowledgeNodeModel).filter(KnowledgeNodeModel.name == name)
        if node_type:
            query = query.filter(KnowledgeNodeModel.node_type == node_type.lower())
        return query.first()

    def create_edge(
        self,
        source_node_id: uuid.UUID,
        target_node_id: uuid.UUID,
        relationship: str,
        strength: float = 1.0,
        edge_id: Optional[uuid.UUID] = None,
    ) -> KnowledgeEdgeModel:
        """Creates a directed relationship between two knowledge nodes."""
        edge = KnowledgeEdgeModel(
            id=edge_id or uuid.uuid4(),
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            relationship=relationship.upper(),
            strength=strength,
        )
        self.session.add(edge)
        return edge

    def find_related(
        self,
        node_id: uuid.UUID,
        relationship: Optional[str] = None,
    ) -> List[KnowledgeNodeModel]:
        """Finds all adjacent target nodes connected by outgoing edges."""
        query = (
            self.session.query(KnowledgeNodeModel)
            .join(KnowledgeEdgeModel, KnowledgeEdgeModel.target_node_id == KnowledgeNodeModel.id)
            .filter(KnowledgeEdgeModel.source_node_id == node_id)
        )
        if relationship:
            query = query.filter(KnowledgeEdgeModel.relationship == relationship.upper())
        return query.all()

    def find_path(
        self,
        start_node_id: uuid.UUID,
        end_node_id: uuid.UUID,
        max_depth: int = 5,
    ) -> List[uuid.UUID]:
        """Breadth-First Search (BFS) finding shortest path between two knowledge nodes."""
        if start_node_id == end_node_id:
            return [start_node_id]

        queue: deque[List[uuid.UUID]] = deque([[start_node_id]])
        visited: Set[uuid.UUID] = {start_node_id}

        while queue:
            path = queue.popleft()
            if len(path) > max_depth:
                continue

            current = path[-1]
            edges = (
                self.session.query(KnowledgeEdgeModel)
                .filter(KnowledgeEdgeModel.source_node_id == current)
                .all()
            )

            for e in edges:
                if e.target_node_id == end_node_id:
                    return path + [e.target_node_id]

                if e.target_node_id not in visited:
                    visited.add(e.target_node_id)
                    queue.append(path + [e.target_node_id])

        return []

    def semantic_search(self, term: str, limit: int = 10) -> List[KnowledgeNodeModel]:
        """Searches entity names and types matching term."""
        return (
            self.session.query(KnowledgeNodeModel)
            .filter(
                sa.or_(
                    KnowledgeNodeModel.name.ilike(f"%{term}%"),
                    KnowledgeNodeModel.node_type.ilike(f"%{term}%"),
                )
            )
            .limit(limit)
            .all()
        )
