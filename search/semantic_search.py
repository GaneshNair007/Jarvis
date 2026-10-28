"""
JARVIS Semantic Local Search.
Uses local Ollama embeddings and Qdrant vector storage with an in-memory
vector index fallback for offline testing and air-gapped environments.
"""

import hashlib
import math
import time
from typing import Any, Dict, List, Optional
import httpx
from search.local_search_engine import SearchHit


class QdrantSemanticSearch:
    def __init__(
        self,
        qdrant_url: Optional[str] = None,
        collection: str = "jarvis_docs",
        embedder_url: Optional[str] = None,
        embed_model: str = "nomic-embed-text",
        vector_dim: int = 768,
    ):
        if qdrant_url is None:
            from jarvis.config import settings
            self.qdrant_url = settings.qdrant_url.rstrip("/")
            self.embedder_url = settings.ollama_base_url.rstrip("/")
            self.embed_model = settings.ollama_embed_model
        else:
            self.qdrant_url = qdrant_url.rstrip("/")
            self.embedder_url = embedder_url.rstrip("/") if embedder_url else "http://localhost:11434"
            self.embed_model = embed_model

        self.collection = collection
        self.vector_dim = vector_dim

        # In-memory vector cache fallback for offline testing
        self._in_memory_vectors: Dict[str, Dict[str, Any]] = {}
        self._ollama_offline_until: float = 0.0

    async def is_healthy(self) -> bool:
        """Check if Qdrant server is reachable."""
        try:
            async with httpx.AsyncClient(timeout=0.5) as client:
                resp = await client.get(f"{self.qdrant_url}/healthz")
                return resp.status_code == 200
        except Exception:
            return False

    async def init_collection(self) -> bool:
        """Initialize Qdrant collection if not already created."""
        try:
            async with httpx.AsyncClient(timeout=1.0) as client:
                resp = await client.get(f"{self.qdrant_url}/collections/{self.collection}")
                if resp.status_code == 200:
                    return True
                # Create collection
                create_resp = await client.put(
                    f"{self.qdrant_url}/collections/{self.collection}",
                    json={
                        "vectors": {
                            "size": self.vector_dim,
                            "distance": "Cosine",
                        }
                    },
                )
                return create_resp.status_code == 200
        except Exception:
            return False

    async def embed(self, text: str) -> List[float]:
        """
        Generate embedding vector using local Ollama.
        Falls back to deterministic hash-based embedding if Ollama is offline.
        """
        now = time.time()
        if now > self._ollama_offline_until:
            try:
                async with httpx.AsyncClient(timeout=0.5) as client:
                    resp = await client.post(
                        f"{self.embedder_url}/api/embeddings",
                        json={"model": self.embed_model, "prompt": text[:2000]},
                    )
                    if resp.status_code == 200:
                        return resp.json()["embedding"]
            except Exception:
                # Mark Ollama as offline for 10 seconds to fail fast
                self._ollama_offline_until = now + 10.0

        # Offline deterministic fallback embedding
        return self._fallback_embedding(text)

    def _fallback_embedding(self, text: str) -> List[float]:
        """Generate normalized 768-dim deterministic vector based on text tokens."""
        vec = [0.0] * self.vector_dim
        words = text.lower().split()
        if not words:
            vec[0] = 1.0
            return vec

        for word in words:
            h = int(hashlib.md5(word.encode()).hexdigest(), 16)
            idx = h % self.vector_dim
            vec[idx] += 1.0

        # Normalize vector
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec

    @staticmethod
    def _cosine_similarity(v1: List[float], v2: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        dot = sum(a * b for a, b in zip(v1, v2))
        norm1 = math.sqrt(sum(a * a for a in v1))
        norm2 = math.sqrt(sum(b * b for b in v2))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot / (norm1 * norm2)

    async def upsert(
        self,
        doc_id: str,
        title: str,
        text: str,
        source_type: str,
        url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Embed text and upsert point into Qdrant vector collection."""
        vector = await self.embed(text)
        payload = {
            "doc_id": doc_id,
            "title": title,
            "text": text[:1000],
            "source_type": source_type,
            "url": url,
            "metadata": metadata or {},
        }

        # Save to in-memory fallback
        self._in_memory_vectors[doc_id] = {
            "vector": vector,
            "payload": payload,
        }

        # Try Qdrant if reachable
        try:
            # Deterministic integer point ID from doc_id hash
            point_id = int(hashlib.md5(doc_id.encode()).hexdigest()[:8], 16)
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.put(
                    f"{self.qdrant_url}/collections/{self.collection}/points",
                    json={
                        "points": [
                            {
                                "id": point_id,
                                "vector": vector,
                                "payload": payload,
                            }
                        ]
                    },
                )
                return resp.status_code == 200
        except Exception:
            return True  # saved to in-memory fallback successfully

    async def search(
        self,
        query: str,
        limit: int = 10,
        source_type: Optional[str] = None,
    ) -> List[SearchHit]:
        """Perform semantic search using local vector query."""
        started = time.perf_counter()
        query_vector = await self.embed(query)

        # 1. Try Qdrant server
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                body: Dict[str, Any] = {
                    "vector": query_vector,
                    "limit": limit,
                    "with_payload": True,
                }
                if source_type:
                    body["filter"] = {
                        "must": [{"key": "source_type", "match": {"value": source_type}}]
                    }

                resp = await client.post(
                    f"{self.qdrant_url}/collections/{self.collection}/points/search",
                    json=body,
                )
                if resp.status_code == 200:
                    data = resp.json().get("result", [])
                    latency_ms = (time.perf_counter() - started) * 1000.0
                    hits = []
                    for item in data:
                        p = item.get("payload", {})
                        hits.append(
                            SearchHit(
                                doc_id=p.get("doc_id", ""),
                                title=p.get("title", ""),
                                url=p.get("url"),
                                snippet=p.get("text", "")[:350],
                                source_type=p.get("source_type", "semantic"),
                                score=float(item.get("score", 0.0)),
                                provider="qdrant_semantic",
                                latency_ms=latency_ms,
                                metadata=p.get("metadata", {}),
                            )
                        )
                    return hits
        except Exception:
            pass

        # 2. In-Memory Cosine Similarity Fallback
        latency_ms = (time.perf_counter() - started) * 1000.0
        scored = []
        for doc_id, entry in self._in_memory_vectors.items():
            payload = entry["payload"]
            if source_type and payload.get("source_type") != source_type:
                continue
            sim = self._cosine_similarity(query_vector, entry["vector"])
            scored.append((sim, payload))

        scored.sort(key=lambda x: x[0], reverse=True)
        hits = []
        for sim, p in scored[:limit]:
            hits.append(
                SearchHit(
                    doc_id=p.get("doc_id", ""),
                    title=p.get("title", ""),
                    url=p.get("url"),
                    snippet=p.get("text", "")[:350],
                    source_type=p.get("source_type", "semantic"),
                    score=round(sim, 4),
                    provider="local_vector_semantic",
                    latency_ms=latency_ms,
                    metadata=p.get("metadata", {}),
                )
            )
        return hits

    def delete_document(self, doc_id: str) -> bool:
        """Remove document vector from index."""
        if doc_id in self._in_memory_vectors:
            del self._in_memory_vectors[doc_id]
        return True
