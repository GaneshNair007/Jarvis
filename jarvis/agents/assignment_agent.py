"""
JARVIS Assignment Handler - Moodle & General LMS
Extract assignments, solve with LLM, humanize, convert to PDF, present for approval
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from jarvis.core.logger import get_logger
from jarvis.core.model_router import model_router, RoutingRequest

logger = get_logger("agents.assignment")


class AssignmentHandler:
    def __init__(self):
        self.output_dir = Path("artifacts/assignments")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.pending_approvals = {}

    async def extract_assignment(self, browser_orchestrator=None) -> Dict[str, Any]:
        if not browser_orchestrator:
            from jarvis.browser.agent_browser import browser_orchestrator
        content = await browser_orchestrator.extract_content()
        return {
            "url": content.get("url"),
            "title": content.get("title"),
            "text": content.get("text", "")[:10000],
            "extracted_at": datetime.utcnow().isoformat(),
        }

    async def solve_and_humanize(self, assignment_text: str, subject: str = "") -> Dict[str, Any]:
        prompt = f"""You are acting as a student completing this assignment in a natural, human way.
Do NOT use overly formal AI-sounding phrases. Write as a student would.
Solve accurately. Include proper formatting.

Subject: {subject}
Assignment:
{assignment_text}

Provide the complete answer in a clean format."""
        routing_req = RoutingRequest(task_id=f"assign_{datetime.utcnow().timestamp()}", user_intent=prompt, task_type="reasoning")
        decision = model_router.route(routing_req)
        result = await asyncio.to_thread(model_router.execute_inference, decision, prompt)
        answer = result.get("reply") or result.get("text") or result.get("content") or ""
        return {"answer": answer, "model": decision.selected_model}

    async def convert_to_pdf(self, title: str, content: str) -> str:
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet
            filename = self.output_dir / f"{title.replace(' ', '_')}_{int(time.time())}.pdf"
            doc = SimpleDocTemplate(str(filename), pagesize=letter)
            styles = getSampleStyleSheet()
            story = []
            story.append(Paragraph(title, styles['Title']))
            story.append(Spacer(1, 12))
            for para in content.split('\n\n'):
                if para.strip():
                    story.append(Paragraph(para.replace('\n', '<br/>'), styles['BodyText']))
                    story.append(Spacer(1, 6))
            doc.build(story)
            return str(filename)
        except Exception as e:
            # Fallback to text
            filename = self.output_dir / f"{title.replace(' ', '_')}_{int(time.time())}.txt"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            return str(filename)

    async def process_assignment(self, subject: str = "", auto_submit: bool = False) -> Dict[str, Any]:
        from jarvis.browser.agent_browser import browser_orchestrator
        await browser_orchestrator.initialize(headless=False)
        extracted = await self.extract_assignment(browser_orchestrator)
        solved = await self.solve_and_humanize(extracted.get("text", ""), subject)
        pdf_path = await self.convert_to_pdf(extracted.get("title", "Assignment"), solved.get("answer", ""))
        approval_id = f"appr_{int(datetime.utcnow().timestamp())}"
        self.pending_approvals[approval_id] = {
            "type": "moodle_assignment",
            "pdf": pdf_path,
            "answer": solved.get("answer"),
            "url": extracted.get("url"),
            "status": "PENDING_APPROVAL",
            "auto_submit": auto_submit
        }
        return {
            "status": "READY_FOR_REVIEW",
            "approval_id": approval_id,
            "pdf_path": pdf_path,
            "message": "Assignment processed. Review and approve before submission.",
            "approval_required": True
        }

    async def approve_and_submit(self, approval_id: str):
        if approval_id not in self.pending_approvals:
            return {"error": "Invalid approval_id"}
        approval = self.pending_approvals[approval_id]
        # Do NOT auto-submit - just mark approved and prepare
        approval["status"] = "APPROVED"
        return {"status": "APPROVED", "message": "Approved. Use browser to manually upload/submit or enable auto-submit with extreme caution.", "ready_to_submit": True}


assignment_handler = AssignmentHandler()
