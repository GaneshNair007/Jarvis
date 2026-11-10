"""Unit tests for JARVIS Firecrawl Adapter."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from jarvis.browser.firecrawl_adapter import FirecrawlAdapter


def test_firecrawl_html_to_markdown():
    sample_html = """
    <html>
        <head><title>Test Page</title></head>
        <body>
            <h1>Main Title</h1>
            <p>This is a paragraph with <a href="https://example.com">a link</a> and <b>bold text</b>.</p>
            <script>console.log("ignore me");</script>
            <h2>Subheading</h2>
            <p>Another paragraph.</p>
        </body>
    </html>
    """
    md = FirecrawlAdapter._html_to_markdown(sample_html)
    assert "# Main Title" in md
    assert "## Subheading" in md
    assert "[a link](https://example.com)" in md
    assert "**bold text**" in md
    assert "ignore me" not in md


@patch("urllib.request.urlopen")
def test_firecrawl_cloud_scrape_success(mock_urlopen):
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = json.dumps(
        {
            "data": {
                "markdown": "# Mocked Firecrawl Markdown\n\nContent here.",
                "metadata": {"title": "Firecrawl Scrape"},
            }
        }
    ).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_urlopen.return_value = mock_resp

    adapter = FirecrawlAdapter()
    adapter.api_key = "fc-test-key"

    result = adapter.scrape_url("https://example.com")
    assert result["status"] == "success"
    assert result["engine"] == "firecrawl_cloud"
    assert "Mocked Firecrawl Markdown" in result["markdown"]


@patch("urllib.request.urlopen")
def test_firecrawl_local_fallback_success(mock_urlopen):
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = (
        b"<html><title>Sample</title><body><h1>Local Scrape</h1><p>Works offline</p></body></html>"
    )
    mock_resp.__enter__.return_value = mock_resp
    mock_urlopen.return_value = mock_resp

    adapter = FirecrawlAdapter()
    adapter.api_key = ""  # Force local fallback

    result = adapter.scrape_url("https://example.com")
    assert result["status"] == "success"
    assert result["engine"] == "local_stealth_extractor"
    assert "# Local Scrape" in result["markdown"]
    assert "Works offline" in result["markdown"]
