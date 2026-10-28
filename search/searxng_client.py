"""
JARVIS SearXNG Fresh-Web Search Client.
Used exclusively as an optional fallback when local results are insufficient.
All fetched web snippets are automatically indexed into the local search
corpus for subsequent millisecond retrieval.
"""

from typing import Any, Dict, List, Optional
import httpx


class SearXNGClient:
    def __init__(self, base_url: Optional[str] = None):
        if base_url is None:
            from jarvis.config import settings
            self.base_url = settings.searxng_url.rstrip("/")
        else:
            self.base_url = base_url.rstrip("/")

    async def is_healthy(self) -> bool:
        """Check if SearXNG container is active."""
        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                resp = await client.get(f"{self.base_url}/healthz")
                return resp.status_code == 200
        except Exception:
            return False

    async def search(
        self,
        query: str,
        limit: int = 10,
        categories: str = "general",
    ) -> List[Dict[str, Any]]:
        """
        Query SearXNG for fresh web research.
        Returns list of structured web results.
        """
        params = {
            "q": query,
            "format": "json",
            "categories": categories,
        }

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(f"{self.base_url}/search", params=params)
                if resp.status_code != 200:
                    return []

                data = resp.json()
                raw_results = data.get("results", [])
                results = []
                for item in raw_results[:limit]:
                    url = item.get("url", "")
                    title = item.get("title", "")
                    content = item.get("content", "")
                    engine = item.get("engine", "searxng")

                    if url and (title or content):
                        results.append(
                            {
                                "title": title,
                                "url": url,
                                "snippet": content,
                                "engine": engine,
                                "published_date": item.get("publishedDate"),
                                "score": float(item.get("score", 0.5)),
                            }
                        )
                return results
        except Exception:
            return []
