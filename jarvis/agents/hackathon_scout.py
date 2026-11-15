"""Source-grounded hackathon discovery and research-note workflow.

This module discovers search leads, fetches source pages, and writes factual
research notes only. It does not create generic starter applications or submit
entries.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from jarvis.core.obscura_browser import obscura_browser
from jarvis.core.notifier import opportunity_notifier
from jarvis.core.web_recon import web_opportunity_recon
from jarvis.powers.browser_powers import browser_powers
from jarvis.security.ten_layer_shield import jarvis_security_suite

logger = logging.getLogger("jarvis.agents.hackathon_scout")


class ScoutAgent:
    """Discovers live search leads; does not synthesize offline opportunities."""

    async def scan_opportunities(self, query: str = "AI hackathon India 2026") -> List[Dict[str, Any]]:
        if not query.strip():
            return []
        return await obscura_browser.search_opportunities(query, limit=5)


class AnalystAgent:
    """Validates discovery records without inventing scores or event facts."""

    def evaluate_opportunities(self, raw_opps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []
        for opportunity in raw_opps:
            title = str(opportunity.get("title", "")).strip()
            url = str(opportunity.get("url", "")).strip()
            if not title or not url.startswith(("https://", "http://")):
                continue
            analyzed = dict(opportunity)
            analyzed["analysis_status"] = "not_ranked"
            analyzed["relevance_score"] = None
            analyzed["recommended_tech"] = []
            candidates.append(analyzed)
        return candidates


class ArchitectAgent:
    """Writes a research note only after a source page has actually been fetched."""

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = workspace_root or Path("workspace/hackathons")

    def scaffold_top_opportunity(self, opportunity: Dict[str, Any]) -> Path:
        title = str(opportunity.get("title", "")).strip()
        source_page = opportunity.get("source_page")
        if not title or not isinstance(source_page, dict):
            raise ValueError("Cannot create a project scaffold without a fetched source page.")

        text_excerpt = str(source_page.get("text_excerpt", "")).strip()
        source_url = str(source_page.get("url") or opportunity.get("url") or "").strip()
        if not text_excerpt or not source_url.startswith(("https://", "http://")):
            raise ValueError("Fetched source page has no verifiable URL or extracted text.")

        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:48] or "hackathon-research"
        project_dir = self.workspace_root / slug
        project_dir.mkdir(parents=True, exist_ok=True)

        research_note = web_opportunity_recon.generate_problem_statement_md(
            opportunity,
            project_name=slug,
        )
        research_path = project_dir / "HACKATHON_RESEARCH.md"
        research_path.write_text(research_note, encoding="utf-8")

        readme = f"""# {title}

This directory currently contains a source-grounded research note only.

- Research: [HACKATHON_RESEARCH.md](HACKATHON_RESEARCH.md)
- Official page fetched: {source_url}

No application code, project architecture, deadline, prize, eligibility rule or Devpost submission has been generated or assumed. Choose the event and confirm its official rules before starting implementation.
"""
        (project_dir / "README.md").write_text(readme, encoding="utf-8")
        return research_path


class DispatcherAgent:
    """Formats a preview; external messaging is not automatic in discovery runs."""

    async def notify_user(
        self,
        opportunities: List[Dict[str, Any]],
        phone_number: str = "+91 9324094474",
        send: bool = False,
    ) -> Dict[str, Any]:
        message = opportunity_notifier.format_whatsapp_hackathon_digest(
            opportunities=opportunities,
            recipient_name="Ganesh",
            location="India / Remote",
        )
        if not send:
            return {
                "status": "not_requested",
                "channel": None,
                "recipient": phone_number,
                "formatted_message": message,
                "message": "No external message was sent. This is only a preview.",
            }
        result = await opportunity_notifier.send_whatsapp_message(
            phone_number=phone_number,
            message=message,
        )
        delivered = result.get("status") == "sent"
        return {
            "status": "sent" if delivered else "not_delivered",
            "dispatch_result": result,
            "formatted_message": message,
        }


class HackathonScoutSwarm:
    """Coordinates live search, official-page fetching and factual research-note creation."""

    def __init__(self):
        self.scout = ScoutAgent()
        self.analyst = AnalystAgent()
        self.architect = ArchitectAgent()
        self.dispatcher = DispatcherAgent()

    async def execute_autonomous_scout_cycle(
        self,
        target_phone: str = "+91 9324094474",
        search_query: str = "AI hackathons India",
        send_notification: bool = False,
    ) -> Dict[str, Any]:
        """Discover leads and write research notes only for pages successfully fetched."""
        cycle_start = time.time()
        try:
            jarvis_security_suite.layer9_audit.log_event(
                "HACKATHON_SWARM_START",
                f"Live scout cycle started for query: {search_query}",
            )
        except Exception as exc:
            logger.warning("Unable to record scout start audit event: %s", exc)

        raw_opportunities = await self.scout.scan_opportunities(search_query)
        if not raw_opportunities:
            return {
                "status": "unavailable",
                "error": "LIVE_OPPORTUNITY_SEARCH_UNAVAILABLE",
                "message": "Live search returned no usable opportunity pages. No mock or curated entries were substituted.",
                "query": search_query,
                "total_discovered": 0,
                "opportunities": [],
                "research_notes": [],
                "notification": {
                    "status": "not_requested",
                    "message": "No external notification was sent.",
                },
            }

        opportunities = self.analyst.evaluate_opportunities(raw_opportunities)
        research_notes: List[str] = []
        page_failures: List[Dict[str, str]] = []

        for opportunity in opportunities[:2]:
            try:
                page = await asyncio.to_thread(browser_powers.read_url, opportunity["url"])
                if (
                    not isinstance(page, dict)
                    or page.get("status") != "completed"
                    or not str(page.get("text_excerpt", "")).strip()
                    or not str(page.get("url", "")).startswith(("https://", "http://"))
                ):
                    opportunity["verification_status"] = "page_fetch_failed"
                    page_failures.append(
                        {"url": opportunity["url"], "error": "Page reader returned no verified extracted text."}
                    )
                    continue

                opportunity["source_page"] = page
                opportunity["verification_status"] = "page_fetched"
                research_path = self.architect.scaffold_top_opportunity(opportunity)
                opportunity["research_note_path"] = str(research_path)
                research_notes.append(str(research_path))
            except Exception as exc:
                opportunity["verification_status"] = "page_fetch_failed"
                page_failures.append({"url": opportunity["url"], "error": str(exc)[:300]})

        if research_notes and not page_failures:
            status = "completed"
        elif research_notes:
            status = "partial_failure"
        else:
            status = "unavailable"

        notification = await self.dispatcher.notify_user(
            opportunities=opportunities,
            phone_number=target_phone,
            send=send_notification,
        )
        duration_sec = round(time.time() - cycle_start, 2)
        try:
            jarvis_security_suite.layer9_audit.log_event(
                "HACKATHON_SWARM_FINISHED",
                f"Scout status={status}; fetched_pages={len(research_notes)}; page_failures={len(page_failures)}",
            )
        except Exception as exc:
            logger.warning("Unable to record scout completion audit event: %s", exc)

        return {
            "status": status,
            "duration_sec": duration_sec,
            "query": search_query,
            "total_discovered": len(opportunities),
            "pages_fetched": len(research_notes),
            "opportunities": opportunities,
            "research_notes": research_notes,
            "page_failures": page_failures,
            "notification": notification,
            "next_steps": [
                "Confirm event activity, deadline, eligibility and judging rules from the official page.",
                "Choose one event before project architecture or code generation begins.",
                "Approve any GitHub repository creation, external notification or form submission separately.",
            ],
        }


hackathon_scout_swarm = HackathonScoutSwarm()
