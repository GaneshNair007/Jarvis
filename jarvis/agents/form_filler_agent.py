"""
JARVIS Job & Ambassador Form Filler
Finds opportunities, fills forms with human-in-the-loop, NEVER auto-submits final forms
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from jarvis.core.logger import get_logger

logger = get_logger("agents.form_filler")


class FormFiller:
    def __init__(self):
        self.profile = {
            "full_name": os.getenv("JARVIS_FULL_NAME", "Ganesh Nair"),
            "email": os.getenv("JARVIS_EMAIL", ""),
            "phone": os.getenv("JARVIS_PHONE", ""),
            "college": os.getenv("JARVIS_COLLEGE", "Symbiosis Institute of Technology, Pune"),
            "degree": os.getenv("JARVIS_DEGREE", "B.Tech AI/ML"),
            "year": os.getenv("JARVIS_YEAR", ""),
            "skills": os.getenv("JARVIS_SKILLS", "Python,AI,ML,FastAPI,PyTorch"),
            "linkedin": os.getenv("JARVIS_LINKEDIN", ""),
            "github": os.getenv("JARVIS_GITHUB", "https://github.com/GaneshNair007"),
            "resume_path": os.getenv("JARVIS_RESUME", ""),
        }
        self.pending = {}

    async def scan_opportunities(self, radius: str = "pune", keywords: List[str] = None):
        if keywords is None:
            keywords = ["internship", "job", "student ambassador", "google student ambassador", "campus ambassador"]
        from jarvis.browser.agent_browser import browser_orchestrator
        await browser_orchestrator.initialize(headless=False)
        # Search on LinkedIn/jobs
        results = []
        for kw in keywords[:3]:
            try:
                await browser_orchestrator.navigate(f"https://www.google.com/search?q={kw}+{radius}")
                content = await browser_orchestrator.extract_content()
                results.append({"keyword": kw, "url": browser_orchestrator.page.url if browser_orchestrator.page else None})
            except Exception as e:
                logger.error(f"Error scanning {kw}: {e}")
        return {"status": "scanned", "results": results}

    async def fill_form(self, url: str, form_data: Dict[str, str] = None):
        from jarvis.browser.agent_browser import browser_orchestrator
        await browser_orchestrator.initialize(headless=False)
        await browser_orchestrator.navigate(url)
        data = form_data or self.profile
        filled = await browser_orchestrator.detect_and_fill_profile(data)
        approval_id = f"form_{int(datetime.utcnow().timestamp())}"
        self.pending[approval_id] = {
            "type": "form_fill",
            "url": url,
            "filled": filled,
            "status": "FILLED_PENDING_APPROVAL",
            "can_submit": False  # NEVER auto-submit
        }
        return {
            "status": "FILLED_READY_FOR_REVIEW",
            "approval_id": approval_id,
            "filled": filled,
            "message": "Form filled. REVIEW ALL FIELDS. Click submit manually or approve for assisted submit with confirmation.",
            "auto_submit_blocked": True
        }

    async def approve(self, approval_id: str):
        if approval_id not in self.pending:
            return {"error": "Invalid"}
        self.pending[approval_id]["status"] = "APPROVED_REVIEWED"
        self.pending[approval_id]["ready"] = True
        return {"status": "APPROVED", "message": "Approved for submission - do NOT auto-click submit without explicit user action"}


form_filler = FormFiller()
