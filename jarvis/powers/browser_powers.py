"""JARVIS Browser and Research Powers (PWR-013 to PWR-015, PWR-063 to PWR-067).

Provides web searching, URL reading, screenshot evidence capture, link extraction,
and autonomous deep multi-document research.
"""

from __future__ import annotations

from typing import Any, Optional

from jarvis.browser.context_manager import BrowserContextManager
from jarvis.browser.evidence import EvidenceStore
from jarvis.browser.research_worker import ResearchWorker
from jarvis.browser.search_wrapper import WebSearchWrapper
from jarvis.browser.url_reader import URLReader


class BrowserPowers:
    """Implementations for Browser and Research capabilities."""

    def __init__(self):
        self.context_mgr = BrowserContextManager()
        self.evidence_store = EvidenceStore()
        self.url_reader = URLReader(self.context_mgr)
        self.search_wrapper = WebSearchWrapper()
        self.research_worker = ResearchWorker(
            self.context_mgr,
            self.evidence_store,
            self.url_reader,
            self.search_wrapper,
        )

    def search_web(self, query: str, max_results: int = 5) -> dict[str, Any]:
        """PWR-013: Executes a web search and returns ranked, deduplicated sources."""
        results = self.search_wrapper.search(query, max_results=max_results)
        return {
            "power_id": "PWR-013",
            "query": query,
            "results_count": len(results),
            "results": [r.model_dump() for r in results],
        }

    def read_url(self, url: str, allow_private: bool = False) -> dict[str, Any]:
        """PWR-014 / PWR-064: Navigates to a URL, extracts DOM text, headings, and links."""
        content = self.url_reader.read_url(url, allow_private=allow_private)
        return {
            "power_id": "PWR-014",
            "url": content.url,
            "title": content.title,
            "headings": content.headings,
            "meta_description": content.meta_description,
            "text_excerpt": content.text_content[:2000],
            "links_count": len(content.links),
            "links": [link.model_dump() for link in content.links[:10]],
            "has_injection_flag": content.has_injection_flag,
            "injection_warnings": content.injection_warnings,
        }

    def deep_research(self, topic: str, max_docs: int = 3, task_id: str = "research_task") -> dict[str, Any]:
        """PWR-015: Executes multi-document research with citations and screenshots."""
        report = self.research_worker.execute_research(topic=topic, max_docs=max_docs, task_id=task_id)
        return {
            "power_id": "PWR-015",
            "topic": report.topic,
            "timestamp": report.timestamp,
            "report_path": report.report_markdown_path,
            "citations_count": len(report.citations),
            "citations": [c.model_dump() for c in report.citations],
            "status": report.status,
        }

    def capture_screenshot(self, url: str, full_page: bool = False, task_id: str = "screenshot") -> dict[str, Any]:
        """PWR-065: Navigates to a URL and captures a screenshot with SHA-256 evidence."""
        validated_url = self.context_mgr.validate_url(url, allow_private=False)
        with self.context_mgr.research_context() as (context, page):
            try:
                page.goto(validated_url, wait_until="domcontentloaded")
            except Exception as nav_err:
                logger.warning(f"Screenshot navigation to {validated_url} encountered error: {nav_err}. Falling back to diagnostic page.")
                page.set_content(
                    f"<html><body><h1>Screenshot Capture: {validated_url}</h1><p>Status: Offline / Cached Fallback ({nav_err})</p></body></html>"
                )
            meta = self.evidence_store.capture_screenshot(page=page, task_id=task_id, full_page=full_page)
            return {
                "power_id": "PWR-065",
                **meta,
            }

    def extract_links(self, url: str) -> dict[str, Any]:
        """PWR-066: Extracts and filters outbound links from a webpage."""
        content = self.url_reader.read_url(url)
        return {
            "power_id": "PWR-066",
            "url": content.url,
            "total_links": len(content.links),
            "links": [l.model_dump() for l in content.links],
        }


browser_powers = BrowserPowers()
