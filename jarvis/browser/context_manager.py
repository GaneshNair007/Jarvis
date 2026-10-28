"""Browser Context Manager.

Enforces ephemeral, isolated browser contexts with zero credential retention
and SSRF protection against unauthorized internal network access.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse
from typing import Generator
from contextlib import contextmanager

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

from jarvis.core.logger import get_logger

logger = get_logger("browser.context")

# Blocked private and link-local subnets for SSRF defense
BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


class SSRFValidationError(PermissionError):
    """Raised when an outbound URL resolves to a protected private or local network."""
    pass


class BrowserContextManager:
    """Manages ephemeral Playwright browser sessions."""

    def __init__(self, headless: bool = True, timeout_ms: int = 15000):
        self.headless = headless
        self.timeout_ms = timeout_ms

    @staticmethod
    def validate_url(url: str, allow_private: bool = False) -> str:
        """Validates that a URL uses safe protocols and does not resolve to private subnets."""
        url = url.strip()
        if url.startswith("data:"):
            if allow_private:
                return url
            raise ValueError("Data URIs are only permitted in isolated private test contexts.")

        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"Unsupported protocol scheme: '{parsed.scheme}'. Only http and https are allowed.")

        hostname = parsed.hostname
        if not hostname:
            raise ValueError(f"Invalid URL without hostname: '{url}'")

        if allow_private:
            return url

        # Check for localhost literal
        if hostname.lower() in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
            raise SSRFValidationError(f"SSRF Alert: Request to local host '{hostname}' blocked.")

        # Resolve IP and check against blocked private ranges
        try:
            addr_info = socket.getaddrinfo(hostname, None)
            for item in addr_info:
                ip_str = item[4][0]
                ip_obj = ipaddress.ip_address(ip_str)
                for net in BLOCKED_NETWORKS:
                    if ip_obj in net:
                        raise SSRFValidationError(
                            f"SSRF Alert: Target hostname '{hostname}' resolves to private IP '{ip_str}' in '{net}'."
                        )
        except socket.gaierror:
            # Let Playwright handle DNS lookup errors if unresolvable
            logger.debug(f"DNS resolution failed during pre-check for '{hostname}'; passing to browser engine.")

        return url

    @contextmanager
    def research_context(self, allow_private: bool = False) -> Generator[tuple[BrowserContext, Page], None, None]:
        """Provides an ephemeral, isolated browser context with zero persistence.

        Yields:
            tuple[BrowserContext, Page]: Disposable browser context and fresh page.
        """
        logger.info("Initializing ephemeral research browser context.")
        with sync_playwright() as p:
            browser: Browser = p.chromium.launch(
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )
            context: BrowserContext = browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                ignore_https_errors=True,
            )
            context.set_default_timeout(self.timeout_ms)
            page: Page = context.new_page()

            try:
                yield context, page
            finally:
                try:
                    context.close()
                    browser.close()
                    logger.info("Ephemeral research browser context securely terminated.")
                except Exception as e:
                    logger.warning(f"Error closing browser context: {e}")
