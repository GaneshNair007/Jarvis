"""Web Search Engine Wrapper.

Executes live DuckDuckGo HTML search. Offline or blocked searches return no
results rather than fabricated documentation links.
"""

from __future__ import annotations

import re
from typing import Optional
from urllib.parse import unquote

import httpx
from pydantic import BaseModel

from jarvis.core.logger import get_logger
from jarvis.constants import DEFAULT_USER_AGENT, DEFAULT_DUCKDUCKGO_SEARCH_URL
from jarvis.config import settings

logger = get_logger("browser.search")


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str


class WebSearchWrapper:
    """Provides privacy-friendly web search querying."""

    def __init__(self, timeout_sec: Optional[float] = None):
        self.timeout_sec = timeout_sec if timeout_sec is not None else settings.browser_search_timeout_sec
        self.headers = {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        """Performs a web search and returns ranked, deduplicated results.

        Args:
            query: The search term.
            max_results: Maximum number of links to return.

        Returns:
            list[SearchResult]: Search results with title, URL, and snippet.
        """
        logger.info(f"Executing web search for: '{query}'")
        if not query or not query.strip() or max_results <= 0:
            return []

        results: list[SearchResult] = []
        try:
            with httpx.Client(timeout=self.timeout_sec, follow_redirects=True) as client:
                resp = client.post(
                    DEFAULT_DUCKDUCKGO_SEARCH_URL,
                    data={"q": query},
                    headers=self.headers,
                )
                if resp.status_code == 200:
                    results = self._parse_ddg_html(resp.text, max_results)
        except Exception as e:
            logger.warning(f"DuckDuckGo search query failed or timed out: {e}")

        if not results:
            logger.warning(
                "Live DuckDuckGo search returned no parseable results. "
                "No synthetic fallback links will be returned."
            )

        return results[:max_results]

    def _parse_ddg_html(self, html: str, max_results: int) -> list[SearchResult]:
        """Parses titles, links, and snippets from DuckDuckGo HTML."""
        results: list[SearchResult] = []

        # Find result link anchors: <a class="result__snippet" ...> or <a class="result__url" ...>
        # Match standard DDG html links
        link_matches = re.findall(r'<a class="result__url" href="([^"]+)">(?:<b>)?([^<]+)(?:</b>)?</a>', html)
        snippet_matches = re.findall(r'<a class="result__snippet[^"]*"[^>]*>(.*?)</a>', html, re.DOTALL)

        for i, (raw_url, title) in enumerate(link_matches[:max_results]):
            # DDG wraps external URLs in /l/?kh=-1&uddg=ENCODED_URL
            clean_url = raw_url
            if "uddg=" in raw_url:
                try:
                    clean_url = unquote(raw_url.split("uddg=")[1].split("&")[0])
                except Exception:
                    clean_url = raw_url

            snippet = ""
            if i < len(snippet_matches):
                snippet = re.sub(r"<[^>]+>", "", snippet_matches[i]).strip()

            results.append(
                SearchResult(
                    title=title.strip() or clean_url,
                    url=clean_url,
                    snippet=snippet,
                )
            )

        return results
