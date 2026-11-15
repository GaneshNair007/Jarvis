"""
JARVIS Obscura CDP & Stealth Web Perception Engine
Inspired by h4ckf0r0day/obscura ultra-lightweight CDP browser and stealth scraping.
Supports direct Chrome DevTools Protocol (CDP) WebSocket sessions and
high-speed stealth HTTP DOM parsing with anti-bot headers.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import urllib.parse
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger("jarvis.perception.obscura")


class ObscuraBrowserClient:
    """
    Ultra-lightweight web perception engine.
    Connects to local Chrome DevTools Protocol on port 9222 or executes
    high-concurrency stealth HTTP scraping with DOM text and link extraction.
    """

    STEALTH_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }

    def __init__(self, cdp_endpoint: str = "http://127.0.0.1:9222", timeout_sec: float = 12.0):
        self.cdp_endpoint = cdp_endpoint
        self.timeout_sec = timeout_sec

    async def is_cdp_available(self) -> bool:
        """Checks if a local Chrome DevTools Protocol instance is listening on port 9222."""
        try:
            async with httpx.AsyncClient(timeout=1.0) as client:
                res = await client.get(f"{self.cdp_endpoint}/json/version")
                return res.status_code == 200
        except Exception:
            return False

    async def fetch_page_content(self, url: str) -> Dict[str, Any]:
        """
        Fetches web page and extracts title, cleaned text, and discovered links.
        Emulates real browser headers to bypass basic scraping filters.
        """
        try:
            async with httpx.AsyncClient(
                headers=self.STEALTH_HEADERS,
                follow_redirects=True,
                timeout=self.timeout_sec,
            ) as client:
                response = await client.get(url)
                html = response.text

                # Extract title
                title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
                title = title_match.group(1).strip() if title_match else "No Title"

                # Strip script and style tags
                cleaned_html = re.sub(
                    r"<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE
                )
                # Strip remaining HTML tags
                plain_text = re.sub(r"<[^>]+>", " ", cleaned_html)
                plain_text = re.sub(r"\s+", " ", plain_text).strip()

                # Extract hyperlinks
                links = []
                for m in re.finditer(
                    r'<a\s+(?:[^>]*?\s+)?href=["\'](https?://[^"\']+)["\'][^>]*>(.*?)</a>',
                    html,
                    re.IGNORECASE | re.DOTALL,
                ):
                    href = m.group(1)
                    anchor_text = re.sub(r"<[^>]+>", "", m.group(2)).strip()
                    if anchor_text and len(anchor_text) < 120 and href not in [l["href"] for l in links]:
                        links.append({"title": anchor_text, "href": href})

                return {
                    "url": str(response.url),
                    "status_code": response.status_code,
                    "title": title,
                    "text_preview": plain_text[:2500],
                    "total_chars": len(plain_text),
                    "links_found": len(links),
                    "links": links[:15],
                }

        except Exception as exc:
            logger.warning(f"Obscura fetch error on {url}: {exc}")
            return {
                "url": url,
                "status_code": 0,
                "title": "Error",
                "text_preview": f"Error fetching URL: {exc}",
                "total_chars": 0,
                "links_found": 0,
                "links": [],
                "error": str(exc),
            }

    async def search_opportunities(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Return live search leads only. Search snippets are not verified event pages."""
        from jarvis.browser.search_wrapper import WebSearchWrapper

        if not query or limit <= 0:
            return []

        try:
            searcher = WebSearchWrapper(timeout_sec=self.timeout_sec)
            search_results = await asyncio.to_thread(searcher.search, query, limit)
        except Exception as exc:
            logger.warning("Live opportunity search failed: %s", exc)
            return []

        results: List[Dict[str, Any]] = []
        for result in search_results[:limit]:
            item = result.model_dump() if hasattr(result, "model_dump") else dict(result)
            url = str(item.get("url", "")).strip()
            title = str(item.get("title", "")).strip()
            snippet = str(item.get("snippet", "")).strip()
            if not title or not url.startswith(("https://", "http://")):
                continue
            results.append(
                {
                    "title": title,
                    "snippet": snippet,
                    "url": url,
                    "source": "duckduckgo_html",
                    "verification_status": "discovery_only",
                }
            )
        return results


# Global Obscura Browser perception singleton
obscura_browser = ObscuraBrowserClient()
