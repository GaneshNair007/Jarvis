"""
JARVIS Search Orchestrator.
Master coordinator uniting Redis hot cache, SQLite FTS5 keyword search,
Meilisearch instant search, Qdrant semantic vectors, and SearXNG fresh-web fallback.
"""

import hashlib
import time
import uuid
from typing import Any, Dict, List, Optional
from jarvis.config import settings
from jarvis.core.audit import audit_ledger
from search.hybrid_ranker import HybridRanker
from search.ingestors.web_cache_ingestor import WebCacheIngestor
from search.local_search_engine import LocalSearchEngine
from search.meili_search import MeiliSearchEngine
from search.search_cache import SearchCache
from search.searxng_client import SearXNGClient
from search.semantic_search import QdrantSemanticSearch


class SearchOrchestrator:
    def __init__(
        self,
        local_engine: Optional[LocalSearchEngine] = None,
        semantic_search: Optional[QdrantSemanticSearch] = None,
        meili_search: Optional[MeiliSearchEngine] = None,
        cache: Optional[SearchCache] = None,
        searxng: Optional[SearXNGClient] = None,
    ):
        self.local = local_engine or LocalSearchEngine(str(settings.search_db_path))
        self.semantic = semantic_search or QdrantSemanticSearch(
            qdrant_url=settings.qdrant_url,
            embedder_url=settings.ollama_base_url,
            embed_model=settings.ollama_embed_model,
        )
        self.meili = meili_search or MeiliSearchEngine(
            url=settings.meilisearch_url,
            master_key=settings.meilisearch_master_key,
        )
        self.cache = cache or SearchCache(settings.redis_url)
        self.web = searxng or SearXNGClient(settings.searxng_url)
        self.ranker = HybridRanker()
        self.web_ingestor = WebCacheIngestor(
            local_engine=self.local,
            semantic_engine=self.semantic,
            meili_engine=self.meili,
        )

    async def search(
        self,
        query: str,
        mode: str = "hybrid",  # "keyword", "semantic", "hybrid", "research"
        limit: int = 10,
        source_type: Optional[str] = None,
        refresh_web: bool = False,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        user_id = user_id or settings.jarvis_user_id
        """
        Execute full local-first search pipeline:
        1. Query normalization
        2. Hot cache lookup (< 5ms)
        3. Parallel local engines (FTS5 + Qdrant + Meilisearch)
        4. Hybrid RRF ranking
        5. Optional fresh-web refresh if local hits are insufficient
        6. Citations & audit logging
        """
        start_time = time.perf_counter()
        query_norm = query.strip()
        if not query_norm:
            return {
                "query": "",
                "mode": mode,
                "latency_ms": 0.0,
                "results": [],
                "citations": [],
                "total_results": 0,
            }

        # Step 1: Hot Cache Lookup (Redis / Memory)
        if not refresh_web:
            cached = self.cache.get(query_norm, mode)
            if cached:
                cached["latency_ms"] = round((time.perf_counter() - start_time) * 1000.0, 2)
                return cached

        query_id = f"qry_{uuid.uuid4().hex[:10]}"
        keyword_hits = []
        semantic_hits = []
        instant_hits = []
        providers_used = []

        # Step 2: Local Keyword Search (SQLite FTS5)
        if mode in ("keyword", "hybrid", "research"):
            keyword_hits = self.local.keyword_search(query_norm, limit=limit * 2, source_type=source_type)
            if keyword_hits:
                providers_used.append("sqlite_fts5")

        # Step 3: Local Semantic Search (Qdrant / In-Memory Fallback)
        if mode in ("semantic", "hybrid", "research"):
            try:
                semantic_hits = await self.semantic.search(query_norm, limit=limit * 2, source_type=source_type)
                if semantic_hits:
                    providers_used.append("qdrant_semantic")
            except Exception:
                pass

        # Step 4: Instant Typo-Tolerant Search (Meilisearch)
        if mode in ("hybrid", "research"):
            try:
                instant_hits = await self.meili.search(query_norm, limit=limit * 2, source_type=source_type)
                if instant_hits:
                    providers_used.append("meilisearch")
            except Exception:
                pass

        # Step 5: Hybrid RRF Merge & Ranking
        if mode == "keyword":
            ranked_results = [h.to_dict() for h in keyword_hits[:limit]]
            for r in ranked_results:
                r["citation"] = self.ranker._create_citation(r, query_id)
        elif mode == "semantic":
            ranked_results = [h.to_dict() for h in semantic_hits[:limit]]
            for r in ranked_results:
                r["citation"] = self.ranker._create_citation(r, query_id)
        else:
            ranked_results = self.ranker.merge(
                keyword_hits=keyword_hits,
                semantic_hits=semantic_hits,
                instant_hits=instant_hits,
                limit=limit,
                query_id=query_id,
            )

        # Step 6: Optional Fresh-Web Refresh (SearXNG)
        # Triggered if explicitly requested OR if local results are completely empty in research mode
        web_refreshed = False
        if refresh_web or (mode == "research" and len(ranked_results) < 2):
            fresh_web_hits = await self.web.search(query_norm, limit=5)
            if fresh_web_hits:
                web_refreshed = True
                providers_used.append("searxng_web")
                # Index fresh web snippets into local index so next lookup is sub-5ms local!
                await self.web_ingestor.ingest_web_results(query_norm, fresh_web_hits)

                # Re-query local engines with newly indexed web results
                fresh_keyword = self.local.keyword_search(query_norm, limit=limit)
                fresh_semantic = await self.semantic.search(query_norm, limit=limit)
                ranked_results = self.ranker.merge(
                    keyword_hits=fresh_keyword,
                    semantic_hits=fresh_semantic,
                    instant_hits=[],
                    limit=limit,
                    query_id=query_id,
                )

        latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

        # Extract Citations
        citations = [item["citation"] for item in ranked_results if "citation" in item]

        # Record query telemetry in local DB
        self.local.record_query(
            query_id=query_id,
            user_id=user_id,
            query=query_norm,
            mode=mode,
            providers_used=providers_used,
            result_count=len(ranked_results),
            latency_ms=latency_ms,
        )

        # Record citations in local DB
        for cit in citations:
            self.local.record_citation(
                citation_id=cit["citation_id"],
                doc_id=cit["doc_id"],
                query_id=query_id,
                title=cit["title"],
                url=cit.get("url"),
                excerpt=cit["excerpt"],
                score=cit["score"],
                provider=",".join(cit.get("providers", ["local"])),
            )

        # Append to audit ledger
        audit_ledger.record(
            actor=user_id,
            action="LOCAL_SEARCH_QUERY",
            target=query_norm[:50],
            payload={
                "query_id": query_id,
                "mode": mode,
                "latency_ms": latency_ms,
                "result_count": len(ranked_results),
                "providers": providers_used,
                "web_refreshed": web_refreshed,
            },
            result="SUCCESS",
        )

        response_payload = {
            "query": query_norm,
            "query_id": query_id,
            "mode": mode,
            "latency_ms": latency_ms,
            "providers_used": providers_used,
            "web_refreshed": web_refreshed,
            "total_results": len(ranked_results),
            "results": ranked_results,
            "citations": citations,
        }

        # Save to Hot Cache
        self.cache.set(query_norm, mode, response_payload)

        return response_payload
