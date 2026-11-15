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


def test_select_tools_for_read_only_email_query(binder):
    query = "List pending emails from my outbox"
    tools = binder.select_tools_for_query(query, limit=3)
    names = [t["function"]["name"] for t in tools]
    assert "email_scan_opportunities" in names
    assert all(binder._tools[name]["privilege_level"] <= 1 for name in names)
    cloud_tools = binder.select_tools_for_query(query, limit=3, max_privilege_level=0)
    cloud_names = [tool["function"]["name"] for tool in cloud_tools]
    assert "email_scan_opportunities" not in cloud_names
    assert "email_list_outbox" not in cloud_names


def test_irrelevant_query_does_not_receive_arbitrary_tools(binder):
    assert binder.select_tools_for_query("Explain eigenvalues and eigenvectors") == []


def test_mutating_tools_are_not_selected_by_default(binder):
    names = [t["function"]["name"] for t in binder.select_tools_for_query("Draft an email and send it", limit=10)]
    assert "email_draft" not in names
    assert "email_send" not in names
    assert "calendar_add_event" not in names
    assert "home_call_service" not in names


def test_execute_tool_rejects_mutating_tools(binder, monkeypatch):
    called = False

    def forbidden_send(**_kwargs):
        nonlocal called
        called = True
        return {"status": "success"}

    binder._tools["email_send"]["func"] = forbidden_send
    result = binder.execute_tool("email_send", {"to": "user@example.com", "subject": "Test", "body": "Test"})
    assert result["success"] is False
    assert result["error"] == "APPROVAL_REQUIRED"
    assert called is False


def test_execute_tool_propagates_provider_failure(binder):
    binder._tools["browser_search"]["func"] = lambda **_kwargs: {
        "status": "unavailable",
        "error": "Search provider unavailable",
    }
    result = binder.execute_tool("browser_search", {"query": "hackathons"})
    assert result["success"] is False
    assert result["error"] == "Search provider unavailable"


def test_execute_tool_success(binder):
    res = binder.execute_tool("calendar_get_upcoming", {"days": 1})
    assert res["success"] is True
    assert res["tool"] == "calendar_get_upcoming"
    assert "events" in res["result"]


def test_execute_unknown_tool(binder):
    res = binder.execute_tool("nonexistent_tool", {})
    assert res["success"] is False
    assert "not found" in res["error"]
