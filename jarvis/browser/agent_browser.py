"""
JARVIS Unified Browser Orchestrator
Handles web navigation, form filling, Moodle assignments, job applications with human-in-the-loop approval.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from jarvis.core.logger import get_logger

logger = get_logger("browser.orchestrator")


class BrowserOrchestrator:
    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None
        self._initialized = False
        self.profile_dir = Path(os.getenv("JARVIS_BROWSER_PROFILE", "data/browser_profile"))
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.approval_required_for = {"submit", "apply", "enroll", "register", "post", "pay"}

    async def initialize(self, headless: bool = False):
        if self._initialized:
            return True
        try:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
            # Try to use chromium with persistent context
            self.context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.profile_dir),
                headless=headless,
                viewport={"width": 1920, "height": 1080},
                args=["--disable-blink-features=AutomationControlled"],
            )
            if self.context.pages:
                self.page = self.context.pages[0]
            else:
                self.page = await self.context.new_page()
            self._initialized = True
            logger.info("Browser orchestrator initialized with persistent profile")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize browser: {e}")
            return False

    async def navigate(self, url: str):
        if not self._initialized:
            await self.initialize()
        await self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
        return {"url": self.page.url, "title": await self.page.title()}

    async def extract_content(self):
        if not self._initialized or not self.page:
            return {}
        content = await self.page.content()
        text = await self.page.inner_text("body") if await self.page.query_selector("body") else ""
        return {"html": content[:50000], "text": text[:50000], "url": self.page.url}

    async def fill_form(self, fields: Dict[str, str], submit: bool = False):
        if not self._initialized or not self.page:
            await self.initialize()
        results = {}
        for selector, value in fields.items():
            try:
                elem = await self.page.query_selector(selector)
                if elem:
                    await elem.fill(value)
                    results[selector] = "filled"
                else:
                    # Try by label/name
                    results[selector] = "not_found"
            except Exception as e:
                results[selector] = f"error: {e}"
        if submit:
            # NEVER auto-submit without approval - just report
            return {"filled": results, "submit_requested": True, "approval_required": True, "action": "PENDING_APPROVAL"}
        return {"filled": results}

    async def detect_and_fill_profile(self, profile: Dict[str, str]):
        if not self._initialized or not self.page:
            await self.initialize()
        # Generic form filling
        filled = {}
        for key, value in profile.items():
            if not value:
                continue
            # Try common selectors
            for sel in [f'input[name*="{key}"]', f'input[id*="{key}"]', f'textarea[name*="{key}"]']:
                try:
                    elem = await self.page.query_selector(sel)
                    if elem and await elem.is_visible():
                        await elem.fill(str(value))
                        filled[key] = sel
                        break
                except:
                    continue
        return {"filled": filled, "approval_required_for_submit": True}

    async def close(self):
        try:
            if self.context:
                await self.context.close()
            if self._playwright:
                await self._playwright.stop()
            self._initialized = False
        except Exception as e:
            logger.error(f"Error closing browser: {e}")


browser_orchestrator = BrowserOrchestrator()
