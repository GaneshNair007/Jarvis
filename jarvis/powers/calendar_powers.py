"""JARVIS Local Calendar Powers (PWR-041 to PWR-045).

Provides keyless, offline RFC 5545 (.ics) calendar reading, upcoming event extraction,
event creation, and semantic keyword searching.
"""

from __future__ import annotations

import datetime
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
import uuid

from jarvis.config import settings
from jarvis.core.logger import get_logger

logger = get_logger("powers.calendar")


class CalendarPowers:
    """Implementations for local offline calendar operations using RFC 5545 (.ics)."""

    def __init__(self, default_calendar_path: Optional[Path] = None):
        self.default_calendar_path = default_calendar_path or (settings.data_dir / "calendar" / "jarvis_calendar.ics")
        self.default_calendar_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.default_calendar_path.exists():
            self._initialize_empty_ics(self.default_calendar_path)

    def _initialize_empty_ics(self, path: Path) -> None:
        """Creates an empty valid iCalendar structure."""
        content = (
            "BEGIN:VCALENDAR\r\n"
            "VERSION:2.0\r\n"
            "PRODID:-//JARVIS Local AI//EN\r\n"
            "CALSCALE:GREGORIAN\r\n"
            "METHOD:PUBLISH\r\n"
            "END:VCALENDAR\r\n"
        )
        path.write_text(content, encoding="utf-8")

    def _parse_datetime(self, val_str: str) -> Optional[datetime.datetime]:
        """Parses iCalendar date or datetime strings into datetime objects."""
        clean = val_str.strip().replace("Z", "")
        # Remove any inline TZID params if passed before colon
        if ":" in clean:
            clean = clean.split(":")[-1]

        # Format: YYYYMMDDTHHMMSS
        if len(clean) >= 15 and "T" in clean:
            try:
                return datetime.datetime.strptime(clean[:15], "%Y%m%dT%H%M%S")
            except ValueError:
                pass
        # Format: YYYYMMDD
        if len(clean) == 8 and clean.isdigit():
            try:
                dt = datetime.datetime.strptime(clean, "%Y%m%d")
                return dt
            except ValueError:
                pass
        return None

    def read_ics_file(self, file_path: Optional[str | Path] = None) -> List[Dict[str, Any]]:
        """Parses all VEVENT blocks in a given .ics file."""
        target_path = Path(file_path) if file_path else self.default_calendar_path
        if not target_path.exists():
            return []

        text = target_path.read_text(encoding="utf-8", errors="ignore")
        # Unfold lines (RFC 5545: lines starting with space or tab continue previous line)
        unfolded = re.sub(r"\r?\n[ \t]", "", text)

        events: List[Dict[str, Any]] = []
        raw_events = re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", unfolded, re.DOTALL)

        for raw_event in raw_events:
            event_dict: Dict[str, Any] = {
                "uid": None,
                "summary": "Untitled Event",
                "start": None,
                "end": None,
                "description": "",
                "location": "",
                "status": "CONFIRMED",
            }

            for line in raw_event.strip().splitlines():
                line = line.strip()
                if not line or ":" not in line:
                    continue
                header, val = line.split(":", 1)
                prop = header.split(";")[0].upper()

                if prop == "UID":
                    event_dict["uid"] = val
                elif prop == "SUMMARY":
                    event_dict["summary"] = val
                elif prop == "DTSTART":
                    event_dict["start"] = val
                    event_dict["start_dt"] = self._parse_datetime(val)
                elif prop == "DTEND":
                    event_dict["end"] = val
                    event_dict["end_dt"] = self._parse_datetime(val)
                elif prop == "DESCRIPTION":
                    event_dict["description"] = val.replace("\\n", "\n").replace("\\,", ",")
                elif prop == "LOCATION":
                    event_dict["location"] = val.replace("\\,", ",")
                elif prop == "STATUS":
                    event_dict["status"] = val

            events.append(event_dict)

        return events

    def get_upcoming_events(self, days: int = 7, file_path: Optional[str | Path] = None) -> Dict[str, Any]:
        """PWR-041: Retrieves upcoming calendar events within the specified day window."""
        events = self.read_ics_file(file_path)
        now = datetime.datetime.now()
        horizon = now + datetime.timedelta(days=days)

        upcoming = []
        for e in events:
            s_dt = e.get("start_dt")
            if s_dt:
                # Include events that occur between now and horizon, or started today
                if now.date() <= s_dt.date() <= horizon.date():
                    clean_e = {k: v for k, v in e.items() if not k.endswith("_dt")}
                    clean_e["start_iso"] = s_dt.isoformat()
                    upcoming.append(clean_e)

        # Sort by start_iso
        upcoming.sort(key=lambda x: x.get("start_iso", ""))

        return {
            "power_id": "PWR-041",
            "horizon_days": days,
            "events_count": len(upcoming),
            "events": upcoming,
        }

    def add_event(
        self,
        summary: str,
        start_time: str | datetime.datetime,
        end_time: Optional[str | datetime.datetime] = None,
        description: str = "",
        location: str = "",
        file_path: Optional[str | Path] = None,
    ) -> Dict[str, Any]:
        """PWR-042: Safely appends a new calendar event into the local RFC 5545 .ics file."""
        target_path = Path(file_path) if file_path else self.default_calendar_path
        if not target_path.exists():
            self._initialize_empty_ics(target_path)

        # Normalize start_time
        if isinstance(start_time, str):
            try:
                start_dt = datetime.datetime.fromisoformat(start_time)
            except ValueError:
                start_dt = self._parse_datetime(start_time) or datetime.datetime.now()
        else:
            start_dt = start_time

        # Normalize end_time
        if not end_time:
            end_dt = start_dt + datetime.timedelta(hours=1)
        elif isinstance(end_time, str):
            try:
                end_dt = datetime.datetime.fromisoformat(end_time)
            except ValueError:
                end_dt = self._parse_datetime(end_time) or (start_dt + datetime.timedelta(hours=1))
        else:
            end_dt = end_time

        uid = f"jarvis-{uuid.uuid4()}@localhost"
        dtstamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        dtstart_str = start_dt.strftime("%Y%m%dT%H%M%S")
        dtend_str = end_dt.strftime("%Y%m%dT%H%M%S")
        clean_desc = description.strip().replace("\n", "\\n")
        clean_summary = summary.strip()
        clean_loc = location.strip()

        vevent_block = (
            "BEGIN:VEVENT\r\n"
            f"UID:{uid}\r\n"
            f"DTSTAMP:{dtstamp}\r\n"
            f"DTSTART:{dtstart_str}\r\n"
            f"DTEND:{dtend_str}\r\n"
            f"SUMMARY:{clean_summary}\r\n"
            f"DESCRIPTION:{clean_desc}\r\n"
            f"LOCATION:{clean_loc}\r\n"
            "STATUS:CONFIRMED\r\n"
            "END:VEVENT\r\n"
        )

        existing_text = target_path.read_text(encoding="utf-8")
        if "END:VCALENDAR" in existing_text:
            updated_text = existing_text.replace("END:VCALENDAR", vevent_block + "END:VCALENDAR")
        else:
            updated_text = existing_text + "\r\n" + vevent_block + "END:VCALENDAR\r\n"

        target_path.write_text(updated_text, encoding="utf-8")

        return {
            "power_id": "PWR-042",
            "success": True,
            "uid": uid,
            "summary": summary,
            "start": dtstart_str,
            "end": dtend_str,
            "calendar_file": str(target_path),
        }

    def search_events(self, query: str, file_path: Optional[str | Path] = None) -> Dict[str, Any]:
        """PWR-043: Searches calendar events for matching keywords."""
        events = self.read_ics_file(file_path)
        q = query.lower().strip()
        matched = []

        for e in events:
            text_corpus = f"{e.get('summary', '')} {e.get('description', '')} {e.get('location', '')}".lower()
            if q in text_corpus:
                clean_e = {k: v for k, v in e.items() if not k.endswith("_dt")}
                if e.get("start_dt"):
                    clean_e["start_iso"] = e["start_dt"].isoformat()
                matched.append(clean_e)

        return {
            "power_id": "PWR-043",
            "query": query,
            "matches_count": len(matched),
            "events": matched,
        }


calendar_powers = CalendarPowers()
