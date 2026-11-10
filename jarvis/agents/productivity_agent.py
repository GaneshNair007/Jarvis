"""
JARVIS Productivity Specialist Agent
PDF Spec: Multi-Agent & Orchestration — Productivity & Time Management

Executes scheduling and personal productivity tasks:
- RFC 5545 iCalendar (.ics) event creation, parsing, and management
- Horizon deadline tracking and upcoming calendar inspection
- Deterministic event search and task scheduling
"""

from __future__ import annotations

import datetime
from pathlib import Path
import time
from typing import Any, Dict, List, Optional

from jarvis.agents.base import AgentContext, AgentResult, AgentTask, BaseSpecialistAgent
from jarvis.core.logger import get_logger
from jarvis.powers.calendar_powers import CalendarPowers

logger = get_logger("agents.productivity")


class ProductivityAgent(BaseSpecialistAgent):
    """
    Specialist agent for personal productivity, calendar management,
    deadlines, and task scheduling.
    """

    name: str = "ProductivityAgent"
    role: str = "productivity"
    permitted_tools: List[str] = [
        "calendar_read",
        "calendar_add_event",
        "calendar_search",
        "task_scheduler",
        "deadline_tracker",
        "calendar",
    ]

    def __init__(self, calendar_powers: Optional[CalendarPowers] = None):
        self._cal = calendar_powers or CalendarPowers()

    def add_event(
        self,
        summary: str,
        start_time: str | datetime.datetime,
        end_time: Optional[str | datetime.datetime] = None,
        description: str = "",
        location: str = "",
        file_path: Optional[str | Path] = None,
    ) -> Dict[str, Any]:
        """Safely creates and records an event in the RFC 5545 calendar."""
        return self._cal.add_event(
            summary=summary,
            start_time=start_time,
            end_time=end_time,
            description=description,
            location=location,
            file_path=file_path,
        )

    def get_upcoming_events(
        self,
        days: int = 7,
        file_path: Optional[str | Path] = None,
    ) -> Dict[str, Any]:
        """Queries calendar events within the horizon window."""
        return self._cal.get_upcoming_events(days=days, file_path=file_path)

    def read_ics_file(self, file_path: Optional[str | Path] = None) -> List[Dict[str, Any]]:
        """Parses and returns all VEVENT blocks in the calendar."""
        return self._cal.read_ics_file(file_path=file_path)

    def _parse_datetime(self, val_str: str) -> Optional[datetime.datetime]:
        """Parses ISO or iCalendar datetime strings, safely handling malformed inputs."""
        return self._cal._parse_datetime(val_str=val_str)

    def search_events(
        self,
        keyword: str,
        file_path: Optional[str | Path] = None,
    ) -> List[Dict[str, Any]]:
        """Searches events in the calendar matching the given keyword."""
        all_events = self._cal.read_ics_file(file_path=file_path)
        kw = (keyword or "").lower()
        if not kw:
            return all_events
        return [
            e
            for e in all_events
            if kw in e.get("summary", "").lower()
            or kw in e.get("description", "").lower()
            or kw in e.get("location", "").lower()
        ]

    def parse_and_schedule(
        self,
        task_description: str,
        deadline_str: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Parses an unstructured task description and schedules it into the calendar."""
        now = datetime.datetime.now()
        start = now + datetime.timedelta(days=1, hours=9)
        end = start + datetime.timedelta(hours=1)
        if deadline_str:
            parsed = self._parse_datetime(deadline_str)
            if parsed:
                end = parsed
                start = end - datetime.timedelta(hours=1)

        res = self.add_event(
            summary=task_description,
            start_time=start,
            end_time=end,
            description=f"Auto-scheduled by JARVIS Productivity Agent for: {task_description}",
        )
        return {
            "status": "SCHEDULED",
            "task": task_description,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "calendar_result": res,
        }

    async def execute(self, task: AgentTask, context: AgentContext) -> AgentResult:
        """Executes assigned productivity/scheduling task using permitted tools."""
        start = time.time()
        params = task.parameters
        goal = (task.goal or "").lower()
        tools_used: List[str] = []
        output: Any = None
        status = "SUCCESS"
        error: Optional[str] = None

        try:
            if "add" in goal or "create" in goal or "start_time" in params:
                tools_used.append("calendar_add_event")
                st = params.get("start_time") or (datetime.datetime.now() + datetime.timedelta(days=1))
                et = params.get("end_time")
                output = self.add_event(
                    summary=params.get("summary", task.goal),
                    start_time=st,
                    end_time=et,
                    description=params.get("description", ""),
                    location=params.get("location", ""),
                    file_path=params.get("file_path"),
                )
            elif "upcoming" in goal or "deadlines" in goal or "days" in params:
                tools_used.append("deadline_tracker")
                days = int(params.get("days", 7))
                output = self.get_upcoming_events(days=days, file_path=params.get("file_path"))
            elif "search" in goal or "keyword" in params:
                tools_used.append("calendar_search")
                output = self.search_events(
                    keyword=params.get("keyword", task.goal),
                    file_path=params.get("file_path"),
                )
            else:
                tools_used.append("calendar_read")
                output = self.read_ics_file(file_path=params.get("file_path"))

            duration_ms = round((time.time() - start) * 1000, 2)
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                role=self.role,
                status=status,
                output=output,
                evidence={"tools": tools_used, "goal": task.goal},
                tools_used=tools_used,
                duration_ms=duration_ms,
                error=error,
            )
        except Exception as exc:
            duration_ms = round((time.time() - start) * 1000, 2)
            logger.error(f"ProductivityAgent.execute failed: {exc}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                role=self.role,
                status="FAILED",
                output=None,
                error=str(exc),
                duration_ms=duration_ms,
            )


# ── Singletons & Aliases ─────────────────────────────────────────────────────
productivity_agent = ProductivityAgent()
agent = productivity_agent

__all__ = ["ProductivityAgent", "productivity_agent", "agent"]
