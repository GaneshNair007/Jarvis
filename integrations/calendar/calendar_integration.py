"""
JARVIS Calendar Integration (PWR-340 to PWR-350)
PDF Spec: Pages 249-265 — Productivity & Calendar Powers

Provides:
- CalDAV calendar read/write (Nextcloud, Fastmail, iCloud, generic)
- Google Calendar API (OAuth2 / service account)
- Event creation, update, deletion
- Free/busy slot detection for scheduling
- Meeting prep digest (agenda + attendee research)
- All outbound actions gated at Tier 1 (reversible write)

Credentials:
  CALDAV_URL         CalDAV server URL
  CALDAV_USERNAME    CalDAV username
  CALDAV_PASSWORD    CalDAV password / app password
  GOOGLE_CLIENT_ID   Google OAuth client ID (optional)
  GOOGLE_CLIENT_SECRET
  GOOGLE_REFRESH_TOKEN
"""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from integrations.base.base_integration import BaseIntegration
from jarvis.core.logger import get_logger

logger = get_logger("integrations.calendar")

# ISO 8601 format used throughout
ISO_FMT = "%Y-%m-%dT%H:%M:%S%z"


class CalendarIntegration(BaseIntegration):
    """
    Unified calendar integration supporting CalDAV and Google Calendar.
    Falls back gracefully if only one backend is configured.
    """

    INTEGRATION_ID = "calendar"

    def __init__(self):
        super().__init__(
            integration_id=self.INTEGRATION_ID,
            display_name="Calendar",
            category="productivity",
            description=(
                "Read and write calendar events via CalDAV (Nextcloud, iCloud, Fastmail) "
                "and Google Calendar API."
            ),
            required_credentials=["CALDAV_URL"],
            danger_level="low",
            default_approval_tier=1,
            rate_limit_rpm=60,
            cost_model="free",
            data_sensitivity="high",
            documentation_url="https://tools.ietf.org/html/rfc4791",
        )
        self._caldav_client = None
        self._gcal_service = None

    # ── Connection ─────────────────────────────────────────────────────────────

    def connect(self) -> Dict[str, Any]:
        results = {}

        # CalDAV
        caldav_result = self._connect_caldav()
        results["caldav"] = caldav_result

        # Google Calendar (optional)
        gcal_result = self._connect_google()
        results["google_calendar"] = gcal_result

        any_connected = caldav_result.get("connected") or gcal_result.get("connected")
        if any_connected:
            self.connected = True
            self.enabled = True

        return {
            "status": "connected" if any_connected else "no_backends_available",
            "backends": results,
        }

    def disconnect(self) -> Dict[str, Any]:
        self._caldav_client = None
        self._gcal_service = None
        self.connected = False
        self.enabled = False
        return {"status": "disconnected"}

    def health_check(self) -> Dict[str, Any]:
        backends = {}
        if self._caldav_client:
            try:
                self._caldav_client.principal()
                backends["caldav"] = "healthy"
            except Exception as exc:
                backends["caldav"] = f"error: {exc}"
        if self._gcal_service:
            try:
                self._gcal_service.calendarList().list(maxResults=1).execute()
                backends["google_calendar"] = "healthy"
            except Exception as exc:
                backends["google_calendar"] = f"error: {exc}"
        return {
            "status": "healthy" if any(v == "healthy" for v in backends.values()) else "degraded",
            "backends": backends,
        }

    # ── Calendar listing ───────────────────────────────────────────────────────

    def list_calendars(self) -> Dict[str, Any]:
        """List all available calendars from connected backends."""
        calendars = []

        if self._caldav_client:
            try:
                principal = self._caldav_client.principal()
                for cal in principal.calendars():
                    calendars.append({
                        "backend": "caldav",
                        "id": str(cal.url),
                        "name": cal.name or str(cal.url),
                    })
            except Exception as exc:
                logger.warning(f"CalDAV list_calendars: {exc}")

        if self._gcal_service:
            try:
                result = self._gcal_service.calendarList().list().execute()
                for item in result.get("items", []):
                    calendars.append({
                        "backend": "google",
                        "id": item["id"],
                        "name": item.get("summary", item["id"]),
                        "color": item.get("colorId"),
                        "primary": item.get("primary", False),
                    })
            except Exception as exc:
                logger.warning(f"Google Calendar list_calendars: {exc}")

        return {
            "power_id": "PWR-340",
            "status": "SUCCESS",
            "count": len(calendars),
            "calendars": calendars,
        }

    # ── Event operations ───────────────────────────────────────────────────────

    def list_events(
        self,
        calendar_id: Optional[str] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        max_results: int = 20,
    ) -> Dict[str, Any]:
        """
        List upcoming events from the primary calendar.

        Args:
            calendar_id: Specific calendar ID (CalDAV URL or Google calendar ID).
            start: Start of time range (defaults to now).
            end: End of time range (defaults to 7 days from now).
            max_results: Maximum events to return.
        """
        now = datetime.now(timezone.utc)
        start = start or now
        end = end or (now + timedelta(days=7))
        events = []

        # ── Google Calendar ──────────────────────────────────────────────────
        if self._gcal_service:
            try:
                cal_id = calendar_id or "primary"
                result = self._gcal_service.events().list(
                    calendarId=cal_id,
                    timeMin=start.isoformat(),
                    timeMax=end.isoformat(),
                    maxResults=max_results,
                    singleEvents=True,
                    orderBy="startTime",
                ).execute()
                for item in result.get("items", []):
                    events.append(self._parse_google_event(item))
            except Exception as exc:
                logger.warning(f"Google Calendar list_events: {exc}")

        # ── CalDAV ────────────────────────────────────────────────────────────
        if self._caldav_client and not events:
            try:
                from caldav import Calendar  # type: ignore
                principal = self._caldav_client.principal()
                for cal in principal.calendars():
                    if calendar_id and str(cal.url) != calendar_id:
                        continue
                    cal_events = cal.date_search(start=start, end=end)
                    for event in cal_events[:max_results]:
                        events.append(self._parse_caldav_event(event))

            except Exception as exc:
                logger.warning(f"CalDAV list_events: {exc}")

        return {
            "power_id": "PWR-341",
            "status": "SUCCESS",
            "range_start": start.isoformat(),
            "range_end": end.isoformat(),
            "count": len(events),
            "events": events[:max_results],
        }

    def create_event(
        self,
        title: str,
        start: datetime,
        end: datetime,
        description: str = "",
        attendees: Optional[List[str]] = None,
        location: str = "",
        calendar_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new calendar event. Tier 1 — reversible write.
        """
        event_id = f"jarvis_{uuid.uuid4().hex[:8]}"
        attendees = attendees or []

        if self._gcal_service:
            try:
                event_body = {
                    "summary": title,
                    "description": description,
                    "location": location,
                    "start": {"dateTime": start.isoformat(), "timeZone": "UTC"},
                    "end": {"dateTime": end.isoformat(), "timeZone": "UTC"},
                    "attendees": [{"email": a} for a in attendees],
                }
                cal_id = calendar_id or "primary"
                result = self._gcal_service.events().insert(
                    calendarId=cal_id, body=event_body
                ).execute()
                logger.info(f"CalendarIntegration: event created (Google) — {result.get('id')}")
                return {
                    "power_id": "PWR-342",
                    "status": "SUCCESS",
                    "backend": "google",
                    "event_id": result.get("id"),
                    "html_link": result.get("htmlLink"),
                    "title": title,
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                }
            except Exception as exc:
                logger.warning(f"Google create_event: {exc}")

        if self._caldav_client:
            try:
                from icalendar import Calendar as ICalendar, Event  # type: ignore
                cal = ICalendar()
                cal.add("prodid", "-//JARVIS//EN")
                cal.add("version", "2.0")
                event = Event()
                event.add("summary", title)
                event.add("dtstart", start)
                event.add("dtend", end)
                event.add("description", description)
                event.add("location", location)
                event.add("uid", event_id)
                cal.add_component(event)

                principal = self._caldav_client.principal()
                calendars = principal.calendars()
                target = next(
                    (c for c in calendars if calendar_id and str(c.url) == calendar_id),
                    calendars[0] if calendars else None,
                )
                if target:
                    target.add_event(cal.to_ical().decode())
                    logger.info(f"CalendarIntegration: event created (CalDAV) — {event_id}")
                    return {
                        "power_id": "PWR-342",
                        "status": "SUCCESS",
                        "backend": "caldav",
                        "event_id": event_id,
                        "title": title,
                        "start": start.isoformat(),
                        "end": end.isoformat(),
                    }
            except Exception as exc:
                logger.warning(f"CalDAV create_event: {exc}")

        return {"power_id": "PWR-342", "status": "ERROR", "error": "No calendar backend available"}

    def delete_event(self, event_id: str, calendar_id: Optional[str] = None) -> Dict[str, Any]:
        """Delete an event. Tier 1 — reversible (moves to trash in Google)."""
        if self._gcal_service:
            try:
                cal_id = calendar_id or "primary"
                self._gcal_service.events().delete(calendarId=cal_id, eventId=event_id).execute()
                return {"power_id": "PWR-343", "status": "SUCCESS", "event_id": event_id, "backend": "google"}
            except Exception as exc:
                logger.warning(f"Google delete_event: {exc}")

        return {"power_id": "PWR-343", "status": "ERROR", "error": "Delete not completed"}

    # ── Scheduling intelligence ────────────────────────────────────────────────

    def find_free_slots(
        self,
        duration_minutes: int = 60,
        days_ahead: int = 5,
        calendar_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Find free time slots in the calendar for meeting scheduling."""
        now = datetime.now(timezone.utc)
        end_range = now + timedelta(days=days_ahead)

        events_result = self.list_events(
            calendar_id=calendar_id,
            start=now,
            end=end_range,
            max_results=50,
        )
        busy_slots = events_result.get("events", [])

        free_slots = []
        cursor = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        # Work hours: 9 AM – 6 PM
        while cursor < end_range and len(free_slots) < 5:
            if 9 <= cursor.hour < 18:  # work hours only
                slot_end = cursor + timedelta(minutes=duration_minutes)
                # Check no overlap with busy slots
                overlap = False
                for event in busy_slots:
                    ev_start = event.get("start")
                    ev_end = event.get("end")
                    if ev_start and ev_end:
                        try:
                            es = datetime.fromisoformat(ev_start)
                            ee = datetime.fromisoformat(ev_end)
                            if cursor < ee and slot_end > es:
                                overlap = True
                                break
                        except Exception:
                            pass
                if not overlap:
                    free_slots.append({
                        "start": cursor.isoformat(),
                        "end": slot_end.isoformat(),
                        "duration_minutes": duration_minutes,
                    })
            cursor += timedelta(minutes=30)

        return {
            "power_id": "PWR-344",
            "status": "SUCCESS",
            "duration_minutes": duration_minutes,
            "free_slots_found": len(free_slots),
            "free_slots": free_slots,
        }

    def get_today_agenda(self) -> Dict[str, Any]:
        """Return today's full agenda with meeting summaries."""
        now = datetime.now(timezone.utc)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        events_result = self.list_events(start=start_of_day, end=end_of_day, max_results=20)
        events = events_result.get("events", [])

        return {
            "power_id": "PWR-345",
            "status": "SUCCESS",
            "date": now.strftime("%Y-%m-%d"),
            "event_count": len(events),
            "agenda": events,
        }

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _connect_caldav(self) -> Dict[str, Any]:
        url = os.environ.get("CALDAV_URL", "")
        username = os.environ.get("CALDAV_USERNAME", "")
        password = os.environ.get("CALDAV_PASSWORD", "")
        if not url:
            return {"connected": False, "reason": "CALDAV_URL not set"}
        try:
            import caldav  # type: ignore
            client = caldav.DAVClient(url=url, username=username, password=password)
            client.principal()  # test connection
            self._caldav_client = client
            logger.info(f"CalendarIntegration: CalDAV connected to {url}")
            return {"connected": True, "url": url}
        except ImportError:
            return {"connected": False, "reason": "caldav package not installed"}
        except Exception as exc:
            return {"connected": False, "reason": str(exc)}

    def _connect_google(self) -> Dict[str, Any]:
        client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
        refresh_token = os.environ.get("GOOGLE_REFRESH_TOKEN", "")
        if not client_id or not refresh_token:
            return {"connected": False, "reason": "Google OAuth credentials not set"}
        try:
            from google.oauth2.credentials import Credentials  # type: ignore
            from googleapiclient.discovery import build  # type: ignore
            creds = Credentials(
                token=None,
                refresh_token=refresh_token,
                client_id=client_id,
                client_secret=os.environ.get("GOOGLE_CLIENT_SECRET", ""),
                token_uri="https://oauth2.googleapis.com/token",
            )
            self._gcal_service = build("calendar", "v3", credentials=creds)
            logger.info("CalendarIntegration: Google Calendar connected")
            return {"connected": True}
        except ImportError:
            return {"connected": False, "reason": "google-api-python-client not installed"}
        except Exception as exc:
            return {"connected": False, "reason": str(exc)}

    def _parse_google_event(self, item: Dict) -> Dict[str, Any]:
        start = item.get("start", {})
        end = item.get("end", {})
        return {
            "backend": "google",
            "id": item.get("id"),
            "title": item.get("summary", "Untitled"),
            "start": start.get("dateTime", start.get("date")),
            "end": end.get("dateTime", end.get("date")),
            "description": item.get("description", ""),
            "location": item.get("location", ""),
            "attendees": [a.get("email") for a in item.get("attendees", [])],
            "status": item.get("status"),
        }

    def _parse_caldav_event(self, event: Any) -> Dict[str, Any]:
        try:
            from icalendar import Calendar as ICalendar  # type: ignore
            cal = ICalendar.from_ical(event.data)
            for component in cal.walk():
                if component.name == "VEVENT":
                    return {
                        "backend": "caldav",
                        "id": str(component.get("uid", "")),
                        "title": str(component.get("summary", "Untitled")),
                        "start": str(component.get("dtstart", {}).dt if hasattr(component.get("dtstart", {}), "dt") else ""),
                        "end": str(component.get("dtend", {}).dt if hasattr(component.get("dtend", {}), "dt") else ""),
                        "description": str(component.get("description", "")),
                        "location": str(component.get("location", "")),
                    }
        except Exception:
            pass
        return {"backend": "caldav", "raw": str(event)[:200]}

    def get_service_status(self) -> Dict[str, Any]:
        return {
            "integration_id": self.INTEGRATION_ID,
            "display_name": self.display_name,
            "connected": self.connected,
            "enabled": self.enabled,
            "caldav_connected": self._caldav_client is not None,
            "google_calendar_connected": self._gcal_service is not None,
        }

    def list_powers(self):
        return [
            {"power_id": "PWR-340", "name": "List Calendars", "tier": 0},
            {"power_id": "PWR-341", "name": "List Events", "tier": 0},
            {"power_id": "PWR-342", "name": "Create Event", "tier": 1},
            {"power_id": "PWR-343", "name": "Delete Event", "tier": 1},
            {"power_id": "PWR-344", "name": "Find Free Slots", "tier": 0},
            {"power_id": "PWR-345", "name": "Today's Agenda", "tier": 0},
        ]

    def _execute_power_impl(self, power_id: str, payload: dict, approval_token=None):
        from datetime import datetime
        dispatch = {
            "PWR-340": lambda p: self.list_calendars(),
            "PWR-341": lambda p: self.list_events(
                calendar_id=p.get("calendar_id"),
                max_results=p.get("max_results", 20),
            ),
            "PWR-342": lambda p: self.create_event(
                title=p["title"],
                start=datetime.fromisoformat(p["start"]),
                end=datetime.fromisoformat(p["end"]),
                description=p.get("description", ""),
                attendees=p.get("attendees"),
            ),
            "PWR-343": lambda p: self.delete_event(p["event_id"], p.get("calendar_id")),
            "PWR-344": lambda p: self.find_free_slots(
                duration_minutes=p.get("duration_minutes", 60),
                days_ahead=p.get("days_ahead", 5),
            ),
            "PWR-345": lambda p: self.get_today_agenda(),
        }
        handler = dispatch.get(power_id)
        if not handler:
            return {"status": "ERROR", "error": f"Unknown power_id: {power_id}"}
        return handler(payload)


# ── Singleton ─────────────────────────────────────────────────────────────────
calendar_integration = CalendarIntegration()

__all__ = ["CalendarIntegration", "calendar_integration"]
