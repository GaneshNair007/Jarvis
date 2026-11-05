"""Tests for JARVIS Local Calendar Powers."""

import datetime
from pathlib import Path
import pytest
from jarvis.powers.calendar_powers import CalendarPowers


@pytest.fixture
def temp_calendar(tmp_path: Path):
    ics_file = tmp_path / "test_calendar.ics"
    cal = CalendarPowers(default_calendar_path=ics_file)
    return cal, ics_file


def test_calendar_initialization(temp_calendar):
    cal, ics_file = temp_calendar
    assert ics_file.exists()
    content = ics_file.read_text(encoding="utf-8")
    assert "BEGIN:VCALENDAR" in content
    assert "END:VCALENDAR" in content


def test_calendar_add_and_read_event(temp_calendar):
    cal, ics_file = temp_calendar
    now = datetime.datetime.now()
    start_dt = now + datetime.timedelta(days=1)
    end_dt = start_dt + datetime.timedelta(hours=2)

    res = cal.add_event(
        summary="Quarterly Architecture Review",
        start_time=start_dt,
        end_time=end_dt,
        description="Deep dive on cognitive core memory",
        location="Lab 1",
    )
    assert res["success"] is True
    assert res["summary"] == "Quarterly Architecture Review"

    events = cal.read_ics_file()
    assert len(events) == 1
    ev = events[0]
    assert ev["summary"] == "Quarterly Architecture Review"
    assert ev["location"] == "Lab 1"
    assert "cognitive core memory" in ev["description"]


def test_calendar_upcoming_events(temp_calendar):
    cal, ics_file = temp_calendar
    now = datetime.datetime.now()

    # Event in 2 days (within 7-day horizon)
    cal.add_event(
        summary="Sprint Demo",
        start_time=now + datetime.timedelta(days=2),
    )
    # Event in 14 days (outside 7-day horizon)
    cal.add_event(
        summary="Annual Offsite",
        start_time=now + datetime.timedelta(days=14),
    )

    upcoming = cal.get_upcoming_events(days=7)
    assert upcoming["events_count"] == 1
    assert upcoming["events"][0]["summary"] == "Sprint Demo"


def test_calendar_search_events(temp_calendar):
    cal, ics_file = temp_calendar
    now = datetime.datetime.now()

    cal.add_event(
        summary="Security Compliance Audit",
        start_time=now + datetime.timedelta(days=1),
        description="Review of Tier-2 approval tokens",
    )
    cal.add_event(
        summary="Team Lunch",
        start_time=now + datetime.timedelta(days=2),
    )

    results = cal.search_events("compliance")
    assert results["matches_count"] == 1
    assert results["events"][0]["summary"] == "Security Compliance Audit"
