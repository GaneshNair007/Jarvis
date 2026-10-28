"""
JARVIS Web Cache Ingestor.
Caches and indexes fresh web search results from SearXNG,
turning ephemeral internet lookups into persistent, instant local knowledge.
"""

import hashlib
from typing import Any, Dict, List, Optional
from search.ingestors.base_ingestor import BaseIngestor


class WebCacheIngestor(BaseIngestor):
    async def ingest_web_results(
        self,
        query: str,
        results: List[Dict[str, Any]],
    ) -> List[str]:
        """Ingest fresh web search hits into the local search index."""
        ingested_ids = []
        for item in results:
            url = item.get("url")
            title = item.get("title") or "Web Search Result"
            snippet = item.get("snippet") or ""

            if not url or not snippet:
                continue

            url_hash = hashlib.sha256(url.encode()).hexdigest()[:12]
            doc_id = f"webcache:{url_hash}"

            prov = self.build_provenance(
                source_type="web_cache",
                author=item.get("engine", "searxng"),
                extra={
                    "query": query,
                    "target_url": url,
                    "published_date": item.get("published_date"),
                },
            )

            success = await self.index_document(
                doc_id=doc_id,
                title=title,
                content=snippet,
                source_type="web_cache",
                source_url=url,
                metadata={"query": query, "engine": item.get("engine")},
                provenance=prov,
            )
            if success:
                ingested_ids.append(doc_id)

        return ingested_ids
