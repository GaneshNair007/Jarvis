"""
JARVIS 7-Layer Private Memory Vault Architecture
Implements the 7 canonical cognitive layers:
  1. CAPTURE: Real-time sensor, telemetry, and input event capture
  2. RAW: Chronological unedited input/output transcripts (append-only)
  3. EPISODIC: Multi-turn conversational episodes, sessions, and task traces
  4. SEMANTIC: Distilled knowledge, user profile, facts, and verified entity relations
  5. PROCEDURAL: Operational skills, learned workflows, tools, and user corrections
  6. WORKING: Short-term scratchpad for active task plans and intermediate states
  7. DIRECTIVE: Immutable user rules, behavioral boundaries, and standing orders
"""

import time
import uuid
import json
from typing import Dict, Any, List, Optional
from jarvis.memory.store import db_store

class MemoryLayerManager:
    LAYERS = ["CAPTURE", "RAW", "EPISODIC", "SEMANTIC", "PROCEDURAL", "WORKING", "DIRECTIVE"]

    def __init__(self):
        self.store = db_store

    def store_memory(
        self,
        layer: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        node_id: Optional[str] = None,
        is_hypothesis: bool = False,
        confidence: float = 1.0,
        evidence_count: int = 1
    ) -> str:
        """Stores a new memory node in the specified cognitive layer with fact/hypothesis metadata."""
        layer_upper = layer.upper()
        if layer_upper not in self.LAYERS:
            raise ValueError(f"Unknown memory layer '{layer}'. Must be one of {self.LAYERS}")

        node_id = node_id or f"mem_{uuid.uuid4().hex[:12]}"
        now = time.time()
        meta_str = json.dumps(metadata or {})
        hypo_int = 1 if is_hypothesis else 0

        with self.store._get_connection() as conn:
            conn.execute("""
            INSERT INTO memory_nodes (id, layer, content, metadata, is_hypothesis, confidence, evidence_count, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                content = excluded.content,
                metadata = excluded.metadata,
                is_hypothesis = excluded.is_hypothesis,
                confidence = excluded.confidence,
                evidence_count = excluded.evidence_count,
                updated_at = excluded.updated_at
            """, (node_id, layer_upper, content, meta_str, hypo_int, confidence, evidence_count, now, now))
            conn.commit()

        return node_id

    def add_fact(self, layer: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Stores an explicit user statement or verified fact (100% confidence)."""
        return self.store_memory(
            layer=layer,
            content=content,
            metadata=metadata,
            is_hypothesis=False,
            confidence=1.0,
            evidence_count=1
        )

    def add_hypothesis(
        self,
        layer: str,
        content: str,
        confidence: float = 0.7,
        evidence_count: int = 1,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Stores an inferred user pattern as a hypothesis requiring confidence and evidence count."""
        return self.store_memory(
            layer=layer,
            content=content,
            metadata=metadata,
            is_hypothesis=True,
            confidence=max(0.0, min(1.0, confidence)),
            evidence_count=max(1, evidence_count)
        )

    def recall(
        self,
        layer: Optional[str] = None,
        query: Optional[str] = None,
        is_hypothesis: Optional[bool] = None,
        min_confidence: float = 0.0,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Recalls memory nodes filtered by layer, query, hypothesis status, and confidence."""
        sql = "SELECT * FROM memory_nodes WHERE 1=1"
        params: List[Any] = []

        if layer:
            sql += " AND layer = ?"
            params.append(layer.upper())

        if query:
            sql += " AND content LIKE ?"
            params.append(f"%{query}%")

        if is_hypothesis is not None:
            sql += " AND is_hypothesis = ?"
            params.append(1 if is_hypothesis else 0)

        if min_confidence > 0.0:
            sql += " AND confidence >= ?"
            params.append(min_confidence)

        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)

        with self.store._get_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
            results = []
            for r in rows:
                item = dict(r)
                item["is_hypothesis"] = bool(item.get("is_hypothesis", 0))
                if item.get("metadata"):
                    try:
                        item["metadata"] = json.loads(item["metadata"])
                    except Exception:
                        pass
                results.append(item)
            return results

    def delete_memory(self, node_id: str) -> bool:
        """Deletes a memory node by ID."""
        with self.store._get_connection() as conn:
            cur = conn.execute("DELETE FROM memory_nodes WHERE id = ?", (node_id,))
            conn.commit()
            return cur.rowcount > 0

    def add_directive(self, rule_name: str, rule_text: str) -> str:
        """Adds an authoritative directive that Jarvis must obey in all planning loops."""
        return self.store_memory(
            layer="DIRECTIVE",
            content=rule_text,
            metadata={"rule_name": rule_name, "priority": "CRITICAL"},
            is_hypothesis=False,
            confidence=1.0
        )

    def get_directives(self) -> List[Dict[str, Any]]:
        """Retrieves all standing user directives."""
        return self.recall(layer="DIRECTIVE", limit=50)

    def get_storage_stats(self) -> Dict[str, Any]:
        """Returns storage metrics from the database."""
        return self.store.get_storage_stats()

# Singleton Memory Manager
memory_manager = MemoryLayerManager()
