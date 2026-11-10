"""JARVIS Obscure Browser Adapter.

Stealth web fetcher with Windows SSL certificate resolution and SSRF defense.
"""

from __future__ import annotations

import ipaddress
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, Optional


class ObscureBrowserAdapter:
    """Stealth HTTP scraper with robust Windows SSL context handling."""

    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/130.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-CH-UA": '"Chromium";v="130", "Google Chrome";v="130"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"Windows"',
    }

    def __init__(self, timeout: float = 15.0, allow_internal_networks: bool = False):
        self.timeout = timeout
        self.allow_internal_networks = allow_internal_networks
        self._ssl_context = self._build_ssl_context()

    def _build_ssl_context(self) -> ssl.SSLContext:
        """Injects certifi CA bundle on Windows to prevent SSL certificate failures."""
        try:
            import certifi

            return ssl.create_default_context(cafile=certifi.where())
        except (ImportError, Exception):
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            return ctx

    def _check_ssrf(self, url: str) -> None:
        """Blocks requests to loopback and private subnets."""
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"Invalid scheme: {parsed.scheme}")

        hostname = parsed.hostname or ""
        if not self.allow_internal_networks:
            if hostname.lower() in ("localhost", "127.0.0.1", "::1"):
                raise PermissionError(f"Access to loopback target '{hostname}' is blocked.")
            try:
                ip = ipaddress.ip_address(hostname)
                if ip.is_private or ip.is_loopback:
                    raise PermissionError(f"Access to private IP '{hostname}' is blocked.")
            except ValueError:
                pass

    def fetch(self, url: str) -> str:
        """Fetches web page content using realistic desktop browser headers."""
        self._check_ssrf(url)
        req = urllib.request.Request(url, headers=self.DEFAULT_HEADERS)
        try:
            with urllib.request.urlopen(req, context=self._ssl_context, timeout=self.timeout) as resp:
                content = resp.read()
                charset = resp.headers.get_content_charset() or "utf-8"
                return content.decode(charset, errors="replace")
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"HTTP fetch error {e.code}: {e.reason}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"Network connection failed: {e.reason}") from e
