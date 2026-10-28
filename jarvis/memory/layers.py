"""
JARVIS 5-Layer Persistent Memory Architecture
Implements the 5 canonical cognitive layers:
  1. RAW: Chronological unedited input/output transcripts
  2. SEMANTIC: Distilled knowledge, facts, and entity relations
  3. EPISODIC: Multi-turn conversational episodes and temporal session context
  4. WORKING: Short-term scratchpad for active task plans and intermediate states
  5. DIRECTIVE: Immutable user rules, behavioral boundaries, and standing orders
"""

import time
import uuid
import json
from typing import Dict, Any, List, Optional
from jarvis.memory.store import db_store

class MemoryLayerManager:
    LAYERS = ["RAW", "SEMANTIC", "EPISODIC", "WORKING", "DIRECTIVE"]

    def __init__(self):
        self.store = db_store

    def store_memory(
        self,
        layer: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        node_id: Optional[str] = None
    ) -> str:
        """Stores a new memory node in the specified cognitive layer."""
        layer_upper = layer.upper()
        if layer_upper not in self.LAYERS:
            raise ValueError(f"Unknown memory layer '{layer}'. Must be one of {self.LAYERS}")

        node_id = node_id or f"mem_{uuid.uuid4().hex[:12]}"
        now = time.time()
        meta_str = json.dumps(metadata or {})

        with self.store._get_connection() as conn:
            conn.execute("""
            INSERT INTO memory_nodes (id, layer, content, metadata, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                content = excluded.content,
                metadata = excluded.metadata,
                updated_at = excluded.updated_at
            """, (node_id, layer_upper, content, meta_str, now, now))
            conn.commit()

        return node_id

    def recall(self, layer: Optional[str] = None, query: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Recalls memory nodes filtered by layer and optional keyword matching."""
        sql = "SELECT * FROM memory_nodes WHERE 1=1"
        params: List[Any] = []

        if layer:
            sql += " AND layer = ?"
            params.append(layer.upper())

        if query:
            sql += " AND content LIKE ?"
            params.append(f"%{query}%")

        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)

        with self.store._get_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
            results = []
            for r in rows:
                item = dict(r)
                if item.get("metadata"):
                    try:
                        item["metadata"] = json.loads(item["metadata"])
                    except Exception:
                        pass
                results.append(item)
            return results

    def add_directive(self, rule_name: str, rule_text: str) -> str:
        """Adds an authoritative directive that Jarvis must obey in all planning loops."""
        return self.store_memory(
            layer="DIRECTIVE",
            content=rule_text,
            metadata={"rule_name": rule_name, "priority": "CRITICAL"}
        )

    def get_directives(self) -> List[Dict[str, Any]]:
        """Retrieves all standing user directives."""
        return self.recall(layer="DIRECTIVE", limit=50)

# Singleton Memory Manager
memory_manager = MemoryLayerManager()
