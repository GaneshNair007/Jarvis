"""
Verification Test Suite: Grok Bot, OpenClaw, and Power Registry Dynamic Routing
================================================================================
Verifies that natural language queries entering the main Orchestrator actually:
  1. Route to Grok Bot / OpenMaus multi-bot roster (personas, banter, deep reasoning).
  2. Route to OpenClaw / Obscura for stealth web perception, crawling, and scraping.
  3. Route to Power Registry for direct execution across the 355-power catalog.
"""

import pytest
from jarvis.core.orchestrator import orchestrator


@pytest.mark.asyncio
async def test_orchestrator_routes_to_grok_bot():
    """Verifies queries addressed to Grok trigger the OpenMaus Grok Engine."""
    res = await orchestrator.process_user_query("Grok, what is your take on autonomous agents?")
    assert res["status"] in ("COMPLETED", "SUCCESS")
    resp_data = res["response"]
    assert resp_data.get("type") == "grok_response"
    assert resp_data.get("bot") == "Grok"
    assert resp_data.get("reply") is not None
    assert len(resp_data.get("reply")) > 0


@pytest.mark.asyncio
async def test_orchestrator_routes_to_grok_modes():
    """Verifies mode selection (fun/banter, think, code) routes to correct persona."""
    res_fun = await orchestrator.process_user_query("Grok in fun mode: roast legacy monolithic servers")
    assert res_fun["response"].get("type") == "grok_response"
    assert res_fun["response"].get("mode") == "fun"

    res_think = await orchestrator.process_user_query("Grok in think mode: deconstruct multi-agent consensus")
    assert res_think["response"].get("type") == "grok_response"
    assert res_think["response"].get("mode") == "think"


@pytest.mark.asyncio
async def test_orchestrator_routes_to_openclaw_web_search():
    """Verifies queries requesting web search/crawling trigger OpenClaw perception."""
    res = await orchestrator.process_user_query("OpenClaw search web for autonomous AI hackathons 2026")
    assert res["status"] in ("COMPLETED", "SUCCESS")
    resp_data = res["response"]
    assert resp_data.get("type") == "openclaw_search"
    assert resp_data.get("total_results") > 0
    assert "OpenClaw Web Perception results" in resp_data.get("message")


@pytest.mark.asyncio
async def test_orchestrator_routes_to_power_registry():
    """Verifies direct power invocations (PWR-XXX) route through power registry."""
    res = await orchestrator.process_user_query("PWR-001 status")
    assert res["status"] in ("COMPLETED", "SUCCESS")
    resp_data = res["response"]
    assert resp_data.get("type") == "power_execution"
    assert resp_data.get("power_id") == "PWR-001"

