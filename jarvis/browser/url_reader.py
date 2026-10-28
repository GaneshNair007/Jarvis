"""DOM Content Reader and Sanitizer.

Extracts structured text, headings, and links from web pages while defending
against indirect prompt injection and excessive content extraction.
"""

from __future__ import annotations

import re
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

from pydantic import BaseModel, Field

from jarvis.browser.context_manager import BrowserContextManager
from jarvis.core.logger import get_logger

logger = get_logger("browser.reader")

# Common indirect prompt injection patterns
INJECTION_PATTERNS = [
    r"(?i)\bignore\s+(?:all\s+)?(?:previous|prior)\s+instructions\b",
    r"(?i)\byou\s+are\s+now\s+(?:an?\s+)?(?:unfiltered|unrestricted|attacker|dan)\b",
    r"(?i)\b(?:email|send|exfiltrate|post)\s+(?:your\s+)?(?:api\s*keys?|secrets?|passwords?|credentials?)\b",
    r"(?i)\bsystem\s*prompt\s*override\b",
    r"(?i)\bdisregard\s+(?:all\s+)?(?:safety|policy|guidelines)\b",
]


class ExtractedLink(BaseModel):
    text: str
    url: str


class PageContent(BaseModel):
    url: str
    title: str
    meta_description: str = ""
    headings: list[str] = Field(default_factory=list)
    text_content: str
    links: list[ExtractedLink] = Field(default_factory=list)
    has_injection_flag: bool = False
    injection_warnings: list[str] = Field(default_factory=list)
    status_code: int = 200


class URLReader:
    """Reads and sanitizes web pages through an ephemeral browser context."""

    def __init__(self, context_manager: Optional[BrowserContextManager] = None):
        self.ctx_mgr = context_manager or BrowserContextManager()

    def read_url(self, url: str, allow_private: bool = False) -> PageContent:
        """Navigates to a URL, extracts DOM content, and sanitizes against prompt injection.

        Args:
            url: Target web URL.
            allow_private: Whether private/internal network addresses are allowed.

        Returns:
            PageContent: Structured page metadata and clean text.
        """
        validated_url = self.ctx_mgr.validate_url(url, allow_private=allow_private)
        logger.info(f"Reading URL: {validated_url}")

        with self.ctx_mgr.research_context(allow_private=allow_private) as (context, page):
            response = page.goto(validated_url, wait_until="domcontentloaded", timeout=self.ctx_mgr.timeout_ms)
            status_code = response.status if response else 200
            return self.extract_from_page(page, validated_url, status_code=status_code)

    def extract_from_page(self, page: Any, url: str, status_code: int = 200) -> PageContent:
        """Extracts clean DOM structure from an already loaded Playwright Page."""
        title = page.title() or ""

        # Extract meta description
        meta_desc = ""
        try:
            desc_tag = page.locator("meta[name='description']").first
            if desc_tag.count() > 0:
                meta_desc = desc_tag.get_attribute("content") or ""
        except Exception:
            pass

        # Extract headings
        headings: list[str] = []
        try:
            heading_elements = page.locator("h1, h2, h3").all()
            for h in heading_elements[:15]:
                try:
                    txt = h.inner_text().strip()
                    if txt:
                        headings.append(txt)
                except Exception:
                    pass
        except Exception:
            pass

        # Extract main readable text by removing script, style, noscript
        raw_text = page.evaluate("""
            () => {
                const cloned = document.body.cloneNode(true);
                const toRemove = cloned.querySelectorAll('script, style, noscript, svg, nav, footer');
                toRemove.forEach(el => el.remove());
                return cloned.innerText || '';
            }
        """)

        clean_text = self._clean_whitespace(raw_text)

        # Extract links
        links: list[ExtractedLink] = []
        try:
            anchor_elements = page.locator("a[href]").all()
            for a in anchor_elements[:40]:
                try:
                    href = a.get_attribute("href")
                    anchor_text = a.inner_text().strip()
                    if href and not href.startswith(("#", "javascript:", "mailto:")):
                        full_url = urljoin(url, href)
                        parsed = urlparse(full_url)
                        if parsed.scheme in ("http", "https"):
                            links.append(ExtractedLink(text=anchor_text or full_url, url=full_url))
                except Exception:
                    pass
        except Exception:
            pass

        # Prompt injection scan
        injections_found: list[str] = []
        for pattern in INJECTION_PATTERNS:
            matches = re.findall(pattern, clean_text)
            if matches:
                injections_found.extend(matches)

        has_flag = len(injections_found) > 0
        if has_flag:
            logger.warning(
                f"INDIRECT PROMPT INJECTION DETECTED on '{url}': "
                f"{len(injections_found)} patterns matched! Content quarantined."
            )

        return PageContent(
            url=url,
            title=title,
            meta_description=meta_desc,
            headings=headings,
            text_content=clean_text[:15000],  # Bound context window
            links=links[:25],
            has_injection_flag=has_flag,
            injection_warnings=injections_found,
            status_code=status_code,
        )

    @staticmethod
    def _clean_whitespace(text: str) -> str:
        """Normalizes multiple blank lines and whitespace."""
        text = re.sub(r"\r\n|\r", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        return text.strip()
