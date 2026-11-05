"""Tests for JARVIS Dynamic Power Binder and Tool Schema Generation."""

import pytest
from jarvis.core.power_binder import PowerBinder


@pytest.fixture
def binder():
    return PowerBinder(max_concurrent_tools=4)


def test_power_binder_initialization(binder):
    assert len(binder._tools) >= 8
    assert "calendar_get_upcoming" in binder._tools
    assert "email_draft" in binder._tools
    assert "home_get_state" in binder._tools


def test_tool_schema_structure(binder):
    schema = binder._tools["calendar_add_event"]["schema"]
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "calendar_add_event"
    assert "properties" in schema["function"]["parameters"]
    assert "summary" in schema["function"]["parameters"]["properties"]


def test_select_tools_for_calendar_query(binder):
    query = "Check my calendar for meetings tomorrow"
    tools = binder.select_tools_for_query(query, limit=2)
    assert len(tools) <= 2
    names = [t["function"]["name"] for t in tools]
    assert any("calendar" in n for n in names)


def test_select_tools_for_email_query(binder):
    query = "Draft an email to partner"
    tools = binder.select_tools_for_query(query, limit=3)
    names = [t["function"]["name"] for t in tools]
    assert any("email" in n for n in names)


def test_execute_tool_success(binder):
    res = binder.execute_tool("calendar_get_upcoming", {"days": 1})
    assert res["success"] is True
    assert res["tool"] == "calendar_get_upcoming"
    assert "events" in res["result"]


def test_execute_unknown_tool(binder):
    res = binder.execute_tool("nonexistent_tool", {})
    assert res["success"] is False
    assert "not found" in res["error"]
