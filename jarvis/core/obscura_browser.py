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
        """
        Performs web search across public opportunity directories.
        Falls back to structured real-time curated mock data when offline.
        """
        encoded_query = urllib.parse.quote_plus(query)
        search_url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
        results: List[Dict[str, Any]] = []

        try:
            async with httpx.AsyncClient(headers=self.STEALTH_HEADERS, timeout=8.0) as client:
                resp = await client.get(search_url)
                if resp.status_code == 200:
                    html = resp.text
                    # Parse DuckDuckGo html snippets
                    snippets = re.findall(
                        r'<a class="result__snippet[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                        html,
                        re.IGNORECASE | re.DOTALL,
                    )
                    for raw_url, raw_snip in snippets[:limit]:
                        clean_snip = re.sub(r"<[^>]+>", "", raw_snip).strip()
                        results.append(
                            {
                                "title": clean_snip[:80] + "...",
                                "snippet": clean_snip,
                                "url": raw_url,
                                "source": "duckduckgo_stealth",
                            }
                        )
        except Exception as e:
            logger.debug(f"DuckDuckGo search error: {e}")

        # If live search returned fewer than required results, return curated high-tier hackathons
        if len(results) < limit:
            curated = [
                {
                    "title": "Google Summer of Code (GSoC) 2026",
                    "snippet": "Global program focused on bringing new contributors into open source software development. Stipends awarded for high-impact AI/ML and systems contributions.",
                    "url": "https://summerofcode.withgoogle.com",
                    "source": "gsoc_curated",
                    "tags": ["Open Source", "Google", "Python", "Systems", "Stipend"],
                    "deadline": "April 2026",
                    "mode": "Remote / Online",
                },
                {
                    "title": "Smart India Hackathon (SIH) 2026 - Hardware & Software",
                    "snippet": "World's biggest open innovation model bringing students to solve pressing national challenges in Smart Automation, Robotics, and Generative AI.",
                    "url": "https://sih.gov.in",
                    "source": "sih_curated",
                    "tags": ["National", "Generative AI", "Smart Automation", "Cash Prize"],
                    "deadline": "August 2026",
                    "mode": "Hybrid / India",
                },
                {
                    "title": "HackMIT & ETHGlobal AI Agent Autonomous Hackathon",
                    "snippet": "Premier collegiate and web3 AI agent hackathon. Build autonomous desktop agents, multi-agent frameworks, and local LLM perception pipelines.",
                    "url": "https://ethglobal.com",
                    "source": "hackathon_curated",
                    "tags": ["AI Agents", "Autonomous Systems", "FastAPI", "High Prize Pool"],
                    "deadline": "May 2026",
                    "mode": "Online / Global",
                },
                {
                    "title": "Devpost Global GenAI Agents & Voice Multimodal Hackathon",
                    "snippet": "Build production voice-first AI assistants and agent swarms utilizing local edge hardware and cloud inference multiplexing.",
                    "url": "https://devpost.com/hackathons",
                    "source": "devpost_curated",
                    "tags": ["Voice AI", "LLM", "RTX GPU Acceleration", "Devpost"],
                    "deadline": "Rolling / Active",
                    "mode": "Remote",
                },
                {
                    "title": "Unstop National Innovation Challenge & AI Internship Drive",
                    "snippet": "Top engineering firms and AI labs recruiting backend and AI agent engineers through live problem-solving challenges and hackathons.",
                    "url": "https://unstop.com/hackathons",
                    "source": "unstop_curated",
                    "tags": ["Internship PPO", "Python", "FastAPI", "Machine Learning"],
                    "deadline": "Upcoming Month",
                    "mode": "India / Hybrid",
                },
            ]
            results.extend(curated[: (limit - len(results))])

        return results


# Global Obscura Browser perception singleton
obscura_browser = ObscuraBrowserClient()
