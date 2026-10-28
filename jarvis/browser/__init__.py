"""JARVIS Browser Subsystem.

Provides ephemeral Playwright research sessions, DOM parsing, screenshot
checksumming, SSRF protection, and citation-backed research workers.
"""

from jarvis.browser.context_manager import BrowserContextManager
from jarvis.browser.evidence import EvidenceStore
from jarvis.browser.url_reader import URLReader
from jarvis.browser.research_worker import ResearchWorker

__all__ = [
    "BrowserContextManager",
    "EvidenceStore",
    "URLReader",
    "ResearchWorker",
]
