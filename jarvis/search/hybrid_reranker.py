"""LLM-Search & Elastic-Labs inspired Reciprocal Rank Fusion (RRF) Hybrid Reranker.

Combines sparse lexical (keyword/BM25) and dense semantic search results into
a fused relevance-ranked list using Reciprocal Rank Fusion (RRF):
    RRF_Score(d) = sum( 1.0 / (k + rank(d)) )
with k=60 as standard in information retrieval.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from jarvis.core.logger import get_logger

logger = get_logger("search.hybrid_reranker")


class ReciprocalRankFusion:
    """Combines multiple ranked retrieval lists into a unified relevance list."""

    def __init__(self, k: int = 60):
        self.k = k

    def fuse(
        self,
        ranked_lists: List[List[Dict[str, Any]]],
        id_key: str = "id",
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Calculates RRF scores across all ranked lists and returns sorted items."""
        scores: Dict[str, float] = {}
        items_map: Dict[str, Dict[str, Any]] = {}

        for ranked_list in ranked_lists:
            for rank_idx, item in enumerate(ranked_list, start=1):
                item_id = str(item.get(id_key, f"doc_{id(item)}"))
                if item_id not in items_map:
                    items_map[item_id] = dict(item)

                # RRF calculation: 1 / (k + rank)
                current_rrf = 1.0 / (self.k + rank_idx)
                scores[item_id] = scores.get(item_id, 0.0) + current_rrf

        # Sort by total RRF score descending
        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)

        results: List[Dict[str, Any]] = []
        for doc_id in sorted_ids:
            doc_data = items_map[doc_id]
            doc_data["rrf_score"] = round(scores[doc_id], 6)
            results.append(doc_data)

        if limit is not None:
            results = results[:limit]

        return results


def fuse_lexical_and_semantic(
    lexical_results: List[Dict[str, Any]],
    semantic_results: List[Dict[str, Any]],
    id_key: str = "id",
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Convenience helper to combine lexical and semantic search results via RRF."""
    reranker = ReciprocalRankFusion(k=60)
    return reranker.fuse([lexical_results, semantic_results], id_key=id_key, limit=limit)
