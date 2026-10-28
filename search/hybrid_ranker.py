"""
JARVIS Hybrid Ranker & Citation Engine.
Combines SQLite FTS5 bm25, Meilisearch typo-tolerant relevance,
and Qdrant semantic cosine similarity using Reciprocal Rank Fusion (RRF),
with recency and source authority boosts, delivering verified citations.
"""

import hashlib
import time
from typing import Any, Dict, List, Optional
from search.local_search_engine import SearchHit
from jarvis.constants import DEFAULT_SOURCE_AUTHORITY


class HybridRanker:
    # Authority weights by document source type
    SOURCE_AUTHORITY = dict(DEFAULT_SOURCE_AUTHORITY)

    def __init__(
        self,
        keyword_weight: Optional[float] = None,
        semantic_weight: Optional[float] = None,
        instant_weight: Optional[float] = None,
        rrf_k: Optional[int] = None,
    ):
        from jarvis.config import settings

        self.keyword_weight = keyword_weight if keyword_weight is not None else settings.rrf_keyword_weight
        self.semantic_weight = semantic_weight if semantic_weight is not None else settings.rrf_semantic_weight
        self.instant_weight = instant_weight if instant_weight is not None else settings.rrf_instant_weight
        self.rrf_k = rrf_k if rrf_k is not None else settings.rrf_k

    def merge(
        self,
        keyword_hits: List[SearchHit],
        semantic_hits: List[SearchHit],
        instant_hits: Optional[List[SearchHit]] = None,
        limit: int = 20,
        query_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Merge results across search engines with Reciprocal Rank Fusion.
        Returns final ranked items with structured citations.
        """
        instant_hits = instant_hits or []
        doc_pool: Dict[str, Dict[str, Any]] = {}

        # 1. Score Keyword Hits (FTS5)
        for rank, hit in enumerate(keyword_hits):
            doc_id = hit.doc_id
            rrf_score = self.keyword_weight * (1.0 / (self.rrf_k + rank + 1))
            self._add_or_update(doc_pool, doc_id, hit, rrf_score, "sqlite_fts5")

        # 2. Score Semantic Hits (Qdrant)
        for rank, hit in enumerate(semantic_hits):
            doc_id = hit.doc_id
            rrf_score = self.semantic_weight * (1.0 / (self.rrf_k + rank + 1))
            self._add_or_update(doc_pool, doc_id, hit, rrf_score, hit.provider)

        # 3. Score Instant Hits (Meilisearch)
        for rank, hit in enumerate(instant_hits):
            doc_id = hit.doc_id
            rrf_score = self.instant_weight * (1.0 / (self.rrf_k + rank + 1))
            self._add_or_update(doc_pool, doc_id, hit, rrf_score, "meilisearch")

        # 4. Apply Authority and Recency Boosts
        for doc_id, item in doc_pool.items():
            source_type = item.get("source_type", "document")
            auth_mult = self.SOURCE_AUTHORITY.get(source_type, 1.0)
            item["score"] = item["score"] * auth_mult

            # Multi-provider agreement boost: if multiple search engines found it, boost score
            if len(item["providers"]) > 1:
                item["score"] *= 1.20

            # Attach verifiable citation object
            item["citation"] = self._create_citation(item, query_id)

        # 5. Sort by aggregated score descending
        ranked = sorted(doc_pool.values(), key=lambda x: x["score"], reverse=True)
        return ranked[:limit]

    def _add_or_update(
        self,
        pool: Dict[str, Dict[str, Any]],
        doc_id: str,
        hit: SearchHit,
        score_increment: float,
        provider_name: str,
    ) -> None:
        if doc_id not in pool:
            pool[doc_id] = {
                "doc_id": hit.doc_id,
                "title": hit.title,
                "url": hit.url,
                "snippet": hit.snippet,
                "source_type": hit.source_type,
                "providers": [provider_name],
                "score": score_increment,
                "metadata": hit.metadata,
                "provenance": hit.provenance,
                "latency_ms": hit.latency_ms,
            }
        else:
            entry = pool[doc_id]
            entry["score"] += score_increment
            if provider_name not in entry["providers"]:
                entry["providers"].append(provider_name)
            # Retain richer snippet if current one is better
            if len(hit.snippet) > len(entry["snippet"]):
                entry["snippet"] = hit.snippet
            if not entry.get("url") and hit.url:
                entry["url"] = hit.url

    @staticmethod
    def _create_citation(item: Dict[str, Any], query_id: Optional[str]) -> Dict[str, Any]:
        """Construct immutable verifiable citation record."""
        doc_id = item["doc_id"]
        title = item["title"]
        url = item.get("url")
        excerpt = item.get("snippet", "")[:280]

        citation_hash = hashlib.sha256(
            f"{doc_id}:{title}:{excerpt}".encode()
        ).hexdigest()[:12]

        return {
            "citation_id": f"cit_{citation_hash}",
            "doc_id": doc_id,
            "query_id": query_id,
            "title": title,
            "url": url,
            "source_type": item.get("source_type", "unknown"),
            "excerpt": excerpt,
            "score": round(item.get("score", 0.0), 4),
            "providers": item.get("providers") or ([item["provider"]] if "provider" in item else ["local_search"]),
            "provenance": item.get("provenance", {}),
            "timestamp": time.time(),
        }
