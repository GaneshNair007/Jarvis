"""JARVIS Firecrawl Scraper & Markdown Extraction Adapter.

Integrates the firecrawl capability into JARVIS for extracting clean, structured
Markdown and metadata from web pages. Provides seamless zero-dependency local
HTML-to-Markdown fallback when no external API key is present.
"""

from __future__ import annotations

import html
import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from jarvis.browser.context_manager import BrowserContextManager
from jarvis.core.logger import get_logger

logger = get_logger("browser.firecrawl")


class FirecrawlAdapter:
    """Production adapter for Firecrawl web extraction with local fallback."""

    def __init__(self, context_manager: Optional[BrowserContextManager] = None):
        self.api_key = os.getenv("FIRECRAWL_API_KEY", "")
        self.api_url = os.getenv("FIRECRAWL_API_URL", "https://api.firecrawl.dev/v1/scrape")
        self.ctx_mgr = context_manager or BrowserContextManager()

    def scrape_url(self, url: str, allow_private: bool = False) -> Dict[str, Any]:
        """Scrapes a URL and returns clean Markdown content and structured metadata.

        Args:
            url: Target URL to scrape.
            allow_private: Whether private local networks are permitted.

        Returns:
            Dict containing markdown, title, status, and metadata.
        """
        validated_url = self.ctx_mgr.validate_url(url, allow_private=allow_private)

        # 1. If external Firecrawl API key is available, attempt cloud extraction
        if self.api_key:
            try:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "Jarvis-Firecrawl/1.0",
                }
                payload = json.dumps({"url": validated_url, "formats": ["markdown"]}).encode("utf-8")
                req = urllib.request.Request(self.api_url, data=payload, headers=headers, method="POST")

                with urllib.request.urlopen(req, timeout=15.0) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        scrape_data = data.get("data", {})
                        markdown = scrape_data.get("markdown", "")
                        return {
                            "status": "success",
                            "engine": "firecrawl_cloud",
                            "url": validated_url,
                            "markdown": markdown,
                            "metadata": scrape_data.get("metadata", {}),
                        }
            except Exception as e:
                logger.warning(f"Firecrawl API call failed ({e}); falling back to local extractor.")

        # 2. Local zero-dependency stealth Markdown extractor
        return self._local_extract_markdown(validated_url)

    def _local_extract_markdown(self, url: str) -> Dict[str, Any]:
        """Extracts structured Markdown locally using realistic stealth headers."""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        req = urllib.request.Request(url, headers=headers)

        try:
            try:
                import certifi
                import ssl

                ssl_ctx = ssl.create_default_context(cafile=certifi.where())
            except Exception:
                import ssl

                ssl_ctx = ssl._create_unverified_context()

            with urllib.request.urlopen(req, timeout=12.0, context=ssl_ctx) as resp:
                raw_html = resp.read().decode("utf-8", errors="ignore")
                title_match = re.search(r"<title[^>]*>(.*?)</title>", raw_html, re.IGNORECASE | re.DOTALL)
                title = title_match.group(1).strip() if title_match else ""

                markdown = self._html_to_markdown(raw_html)
                return {
                    "status": "success",
                    "engine": "local_stealth_extractor",
                    "url": url,
                    "title": title,
                    "markdown": markdown,
                    "metadata": {"source": "local_dom_sanitizer"},
                }
        except Exception as e:
            logger.error(f"Local Markdown extraction failed for {url}: {e}")
            return {
                "status": "error",
                "engine": "local_stealth_extractor",
                "url": url,
                "markdown": "",
                "error": str(e),
            }

    @staticmethod
    def _html_to_markdown(raw_html: str) -> str:
        """Converts raw HTML into clean GitHub-flavored Markdown."""
        # Strip script, style, head, and svg tags
        clean = re.sub(
            r"<(script|style|head|svg|noscript)[^>]*>.*?</\1>", "", raw_html, flags=re.DOTALL | re.IGNORECASE
        )

        # Convert headings
        for i in range(6, 0, -1):
            clean = re.sub(
                rf"<h{i}[^>]*>(.*?)</h{i}>", rf"\n\n{'#' * i} \1\n\n", clean, flags=re.IGNORECASE | re.DOTALL
            )

        # Convert links [text](url)
        clean = re.sub(
            r'<a\s+(?:[^>]*?\s+)?href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
            r"[\2](\1)",
            clean,
            flags=re.IGNORECASE | re.DOTALL,
        )

        # Convert bold / strong
        clean = re.sub(r"<(?P<tag>strong|b)\b[^>]*>(.*?)</(?P=tag)>", r"**\2**", clean, flags=re.IGNORECASE | re.DOTALL)

        # Convert paragraphs & breaks
        clean = re.sub(r"<p[^>]*>(.*?)</p>", r"\n\n\1\n\n", clean, flags=re.IGNORECASE | re.DOTALL)
        clean = re.sub(r"<br\s*/?>", r"\n", clean, flags=re.IGNORECASE)

        # Strip remaining tags
        clean = re.sub(r"<[^>]+>", " ", clean)

        # Decode HTML entities
        clean = html.unescape(clean)

        # Normalize multiple spaces and blank lines
        lines = [line.strip() for line in clean.splitlines()]
        clean_text = "\n".join(lines)
        clean_text = re.sub(r"\n{3,}", "\n\n", clean_text).strip()

        return clean_text


firecrawl_adapter = FirecrawlAdapter()
