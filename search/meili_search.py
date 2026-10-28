"""
JARVIS Meilisearch Integration.
Provides instant typo-tolerant search-as-you-type (< 50ms)
with graceful fallback if Meilisearch container is not reachable.
"""

import time
from typing import Any, Dict, List, Optional
import httpx
from search.local_search_engine import SearchHit


class MeiliSearchEngine:
    def __init__(
        self,
        url: Optional[str] = None,
        master_key: Optional[str] = None,
        index_name: str = "jarvis_search",
    ):
        if url is None or master_key is None:
            from jarvis.config import settings
            self.url = url or settings.meilisearch_url.rstrip("/")
            self.master_key = master_key or settings.meilisearch_master_key
        else:
            self.url = url.rstrip("/")
            self.master_key = master_key

        self.index_name = index_name
        self.headers = {
            "Authorization": f"Bearer {self.master_key}",
            "Content-Type": "application/json",
        }

    async def is_healthy(self) -> bool:
        """Check if Meilisearch server is online."""
        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                resp = await client.get(f"{self.url}/health")
                return resp.status_code == 200 and resp.json().get("status") == "available"
        except Exception:
            return False

    async def init_index(self) -> bool:
        """Initialize and configure Meilisearch index."""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                # Create index with primary key
                await client.post(
                    f"{self.url}/indexes",
                    headers=self.headers,
                    json={"uid": self.index_name, "primaryKey": "doc_id"},
                )
                # Configure searchable attributes
                await client.put(
                    f"{self.url}/indexes/{self.index_name}/settings/searchable-attributes",
                    headers=self.headers,
                    json=["title", "content", "source_url"],
                )
                # Configure filterable attributes
                await client.put(
                    f"{self.url}/indexes/{self.index_name}/settings/filterable-attributes",
                    headers=self.headers,
                    json=["source_type"],
                )
                return True
        except Exception:
            return False

    async def index_document(
        self,
        doc_id: str,
        title: str,
        content: str,
        source_type: str,
        source_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Index a single document into Meilisearch."""
        return await self.index_documents(
            [
                {
                    "doc_id": doc_id,
                    "title": title,
                    "content": content[:5000],  # trim for fast instant indexing
                    "source_type": source_type,
                    "source_url": source_url,
                    "metadata": metadata or {},
                }
            ]
        )

    async def index_documents(self, documents: List[Dict[str, Any]]) -> bool:
        """Batch index documents into Meilisearch."""
        if not documents:
            return True
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.post(
                    f"{self.url}/indexes/{self.index_name}/documents",
                    headers=self.headers,
                    json=documents,
                )
                return resp.status_code in (200, 202)
        except Exception:
            return False

    async def search(
        self,
        query: str,
        limit: int = 20,
        source_type: Optional[str] = None,
    ) -> List[SearchHit]:
        """Execute instant Meilisearch query."""
        started = time.perf_counter()
        payload: Dict[str, Any] = {
            "q": query,
            "limit": limit,
            "attributesToHighlight": ["title", "content"],
            "highlightPreTag": "<b>",
            "highlightPostTag": "</b>",
        }
        if source_type:
            payload["filter"] = f'source_type = "{source_type}"'

        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.post(
                    f"{self.url}/indexes/{self.index_name}/search",
                    headers=self.headers,
                    json=payload,
                )
                if resp.status_code != 200:
                    return []

                latency_ms = (time.perf_counter() - started) * 1000.0
                data = resp.json()
                hits = []
                for item in data.get("hits", []):
                    formatted = item.get("_formatted", {})
                    snippet = formatted.get("content") or item.get("content", "")[:300]
                    # Score based on position
                    score = 1.0 - (len(hits) * 0.03)
                    hits.append(
                        SearchHit(
                            doc_id=item["doc_id"],
                            title=item["title"],
                            url=item.get("source_url"),
                            snippet=snippet[:400],
                            source_type=item.get("source_type", "unknown"),
                            score=max(score, 0.1),
                            provider="meilisearch",
                            latency_ms=latency_ms,
                            metadata=item.get("metadata", {}),
                        )
                    )
                return hits
        except Exception:
            return []

    async def delete_document(self, doc_id: str) -> bool:
        """Remove a document from Meilisearch."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.delete(
                    f"{self.url}/indexes/{self.index_name}/documents/{doc_id}",
                    headers=self.headers,
                )
                return resp.status_code in (200, 202)
        except Exception:
            return False
