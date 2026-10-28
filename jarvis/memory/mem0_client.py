"""
JARVIS Mem0 Memory Client Adapter
Integrates Mem0 as the user-scoped long-term memory layer.
Falls back to local persistent SQLite 7-layer memory vault when MEM0_API_KEY is not configured,
guaranteeing complete local-first autonomy without third-party dependencies.
"""

import os
import re
from typing import Dict, Any, List, Optional
from jarvis.config import settings
from jarvis.memory.layers import memory_manager
from jarvis.core.logger import get_logger

logger = get_logger("mem0_client")

STOPWORDS = {
    "what", "is", "my", "the", "a", "an", "in", "on", "at", "of", "for", "to",
    "and", "or", "tell", "me", "about", "do", "you", "know", "which", "how", "can", "user", "assistant"
}

class LocalMem0Adapter:
    """Zero-dependency local adapter mimicking Mem0 interface using the local SQLite vault."""

    def __init__(self):
        self.memory = memory_manager

    def search(self, query: str, filters: Optional[Dict[str, Any]] = None, limit: int = 5) -> List[Dict[str, Any]]:
        user_id = (filters or {}).get("user_id", settings.jarvis_user_id)
        
        candidate_scores: Dict[str, int] = {}
        candidate_objects: Dict[str, Dict[str, Any]] = {}

        # 1. Exact substring matches
        direct_matches = self.memory.recall(layer="SEMANTIC", query=query, limit=limit)
        for h in direct_matches:
            hid = h["id"]
            candidate_scores[hid] = candidate_scores.get(hid, 0) + 5
            candidate_objects[hid] = h

        # 2. Tokenized search for salient keywords
        tokens = [
            re.sub(r"[^\w]", "", w.lower())
            for w in query.split()
        ]
        tokens = [t for t in tokens if len(t) > 2 and t not in STOPWORDS]

        for token in tokens:
            hits = self.memory.recall(layer="SEMANTIC", query=token, limit=limit * 2)
            for h in hits:
                hid = h["id"]
                candidate_scores[hid] = candidate_scores.get(hid, 0) + 2
                candidate_objects[hid] = h

            dhits = self.memory.recall(layer="DIRECTIVE", query=token, limit=3)
            for h in dhits:
                hid = h["id"]
                candidate_scores[hid] = candidate_scores.get(hid, 0) + 3
                candidate_objects[hid] = h

        # Prioritize memories that contain answers over memories that contain echoes of questions
        for hid, obj in list(candidate_objects.items()):
            content_lower = obj.get("content", "").lower()
            if "remember that" in content_lower or "preference is" in content_lower:
                candidate_scores[hid] += 5

        if candidate_scores:
            sorted_ids = sorted(candidate_scores.keys(), key=lambda x: candidate_scores[x], reverse=True)[:limit]
            combined = [candidate_objects[sid] for sid in sorted_ids]
        else:
            combined = []

        return [{"id": r["id"], "memory": r["content"], "user_id": user_id} for r in combined]

    def add(self, messages: List[Dict[str, str]], user_id: str = "ganesh", metadata: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        created = []
        user_msg = ""
        asst_msg = ""
        for m in messages:
            if m.get("role") == "user":
                user_msg = m.get("content", "")
            elif m.get("role") == "assistant":
                asst_msg = m.get("content", "")

        content = f"User: {user_msg} | Assistant: {asst_msg}" if asst_msg else user_msg
        if content:
            node_id = self.memory.store_memory(
                layer="SEMANTIC",
                content=content,
                metadata={"user_id": user_id, **(metadata or {})},
                is_hypothesis=False,
                confidence=1.0,
                evidence_count=1
            )
            created.append({"id": node_id, "memory": content, "user_id": user_id})
        return created

    def delete(self, memory_id: str) -> bool:
        return self.memory.delete_memory(memory_id)

    def get_all(self, filters: Optional[Dict[str, Any]] = None, limit: int = 50) -> List[Dict[str, Any]]:
        results = self.memory.recall(layer="SEMANTIC", limit=limit)
        return [{"id": r["id"], "memory": r["content"]} for r in results]

def get_mem0_client():
    """Instantiates official Mem0 MemoryClient if API key exists, otherwise local SQLite adapter."""
    api_key = settings.mem0_api_key
    if api_key and api_key != "your_mem0_key" and not api_key.startswith("mock"):
        try:
            from mem0 import MemoryClient
            logger.info("Connecting to official Mem0 Cloud Memory service")
            return MemoryClient(api_key=api_key)
        except Exception as e:
            logger.warning("Failed to initialize Mem0 Cloud client (%s); falling back to local adapter", e)

    logger.info("Using local-first Mem0 SQLite adapter")
    return LocalMem0Adapter()

# Singleton memory client
mem0_client = get_mem0_client()
