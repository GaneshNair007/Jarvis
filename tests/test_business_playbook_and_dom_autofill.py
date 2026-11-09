"""
Tests for JARVIS Business Playbook Engine and DOM Autonomous Form Autofill
Validates:
1. Catalog Loading: 200 AI Business Ideas indexed from data/business_ideas.json
2. Search & Filter: Domain matching and full-text keyword search
3. Hardware Feasibility: RTX 4050 6GB VRAM allocation and 105-workforce assignment
4. Grok Bot Workflow 01: Lead Follow-Up drafts with strict approval boundary
5. Grok Bot Workflow 02: Ad Pulse aggregated reporting (CTR, CPC, CPA, ROAS)
6. Grok Bot Workflow 03: The Weekly Ops Sweep (Overdue tasks, stalled leads, human decisions)
7. DOM Form Autofill: Real ephemeral Playwright session filling form fields and halting before submit
"""

from __future__ import annotations

import os
import pytest
from pathlib import Path

from jarvis.business.playbook_engine import business_playbook_engine
from jarvis.career.form_autofill_agent import autonomous_form_filler, CandidateProfile


class TestBusinessPlaybookEngine:
    """Verifies the 200 AI business ideas and Grok Bot operational workflows."""

    def test_200_ideas_catalog_loaded(self):
        """Ensures all 200 business ideas from Ayman William's guide are loaded."""
        assert business_playbook_engine.total_ideas == 200

    def test_search_and_filter_ideas(self):
        """Verifies semantic search and domain filtering across the catalog."""
        # Domain search
        podcast_ideas = business_playbook_engine.search_ideas("podcast", limit=3)
        assert len(podcast_ideas) > 0
        assert any("podcast" in i.title.lower() or "podcast" in i.toolkit.lower() for i in podcast_ideas)

        # ID lookup
        idea1 = business_playbook_engine.get_idea_by_id("IDEA-001")
        assert idea1 is not None
        assert idea1.number == 1
        assert "repurposing studio" in idea1.title.lower()

    def test_hardware_feasibility_evaluation_rtx4050(self):
        """Verifies feasibility evaluation against operator's RTX 4050 6GB GPU."""
        eval_result = business_playbook_engine.evaluate_idea_execution("IDEA-001")
        assert "error" not in eval_result
        assert eval_result["hardware_feasibility"]["target_device"] == "NVIDIA GeForce RTX 4050 (6GB VRAM)"
        assert eval_result["hardware_feasibility"]["verdict"] == "100% Executable on Operator Rig"
        assert len(eval_result["assigned_workforce_pod"]) == 5
        assert "Day 1" in eval_result["seven_day_plan"]
        assert "Strict Human-in-the-Loop Gate" in eval_result["operator_safety_rule"]

    def test_grokbot_workflow_01_lead_followup(self):
        """Verifies lead follow-up drafts and strict approval boundary."""
        test_leads = [
            {"lead_id": "L1", "name": "Sarah Connor", "company": "Cyberdyne", "status": "new", "days_stalled": 0},
            {"lead_id": "L2", "name": "Miles Dyson", "company": "SkyNet R&D", "status": "waiting", "days_stalled": 5},
        ]
        drafts = business_playbook_engine.run_lead_followup_workflow(test_leads, company_name="JARVIS Systems")
        assert len(drafts) == 2
        assert drafts[0].approval_required is True
        assert drafts[0].status == "draft_ready"
        assert "Sarah" in drafts[0].draft_message
        assert "Miles" in drafts[1].draft_message

    def test_grokbot_workflow_02_ad_pulse(self):
        """Verifies multi-channel ad reporting, CTR, CPC, CPA, ROAS and threshold flags."""
        metrics = [
            {
                "campaign_name": "GSoC AI Launch",
                "channel": "google",
                "spend_usd": 150.0,
                "impressions": 10000,
                "clicks": 400,
                "conversions": 10,
                "revenue_usd": 600.0,
            },
            {
                "campaign_name": "Subagent Beta Test",
                "channel": "meta",
                "spend_usd": 300.0,
                "impressions": 5000,
                "clicks": 25,
                "conversions": 1,
                "revenue_usd": 50.0,
            },
        ]
        ad_pulse = business_playbook_engine.run_ad_pulse_workflow(metrics)
        assert ad_pulse.total_spend_usd == 450.0
        assert ad_pulse.total_clicks == 425
        assert ad_pulse.total_conversions == 11
        assert ad_pulse.roas > 1.0
        assert len(ad_pulse.flagged_campaigns) >= 1  # Meta campaign had low CTR (0.5%) and high CPA ($300)
        assert "DAILY AD PULSE REPORT" in ad_pulse.summary_report

    def test_grokbot_workflow_03_weekly_ops_sweep(self):
        """Verifies the weekly ops sweep auditing overdue tasks, stalled leads, and priorities."""
        tasks = [
            {"title": "Deploy AES-256 Vault", "is_overdue": True, "owner": "Security Agent"},
            {"title": "Draft Profile README", "is_overdue": False, "owner": "DevOps Agent"},
        ]
        leads = [
            {"lead_id": "L1", "name": "Alex", "company": "Tech Corp", "days_stalled": 6},
            {"lead_id": "L2", "name": "Jordan", "company": "Cloud Inc", "days_stalled": 1},
        ]
        ads = [
            {
                "campaign_name": "Test Ad",
                "channel": "meta",
                "spend_usd": 100.0,
                "impressions": 1000,
                "clicks": 5,
                "conversions": 0,
                "revenue_usd": 0.0,
            }
        ]

        sweep = business_playbook_engine.run_weekly_ops_sweep(tasks, leads, ads)
        assert len(sweep.overdue_tasks) == 1
        assert len(sweep.stalled_leads) == 1
        assert len(sweep.human_decisions_needed) >= 2
        assert len(sweep.top_three_priorities) == 3
        assert "WEEKLY OPS SWEEP SUMMARY" in sweep.executive_brief


class TestPlaywrightDOMFormAutofill:
    """Verifies live DOM form detection and autofill with Playwright."""

    def test_dom_autofill_ephemeral_browser(self, tmp_path):
        """Loads a synthetic HTML form via data: URI, inspects DOM, fills fields, and halts before submit."""
        synthetic_form_html = """data:text/html,<html>
          <head><title>Hackathon Application</title></head>
          <body>
            <h1>Apply for AI Hackathon 2026</h1>
            <form id="appForm">
              <input type="text" name="first_name" id="first_name" placeholder="First Name" />
              <input type="text" name="last_name" id="last_name" placeholder="Last Name" />
              <input type="email" name="user_email" id="email" placeholder="Your Email" />
              <input type="tel" name="phone" id="phone" placeholder="Phone Number" />
              <input type="url" name="github_url" id="github" placeholder="GitHub Profile URL" />
              <input type="url" name="linkedin_url" id="linkedin" placeholder="LinkedIn Profile" />
              <textarea name="why_apply" id="why_apply" placeholder="Why are you interested in this hackathon?"></textarea>
              <button type="submit" id="submitBtn">Submit Application</button>
            </form>
          </body>
        </html>""".strip()

        result = autonomous_form_filler.autofill_web_form(
            url=synthetic_form_html,
            headless=True,
            dry_run=False,
            allow_submit=False,
            allow_private=True,
            screenshot_dir=str(tmp_path),
        )

        assert result["candidate"] == "Ganesh Nair"
        assert result["total_fields_filled"] >= 5
        assert result["submit_button_found"] is True
        assert result["submitted"] is False
        assert result["human_approval_required"] is True
        assert result["status"] == "ready_for_human_review"
        assert os.path.exists(result["screenshot_evidence"])


class TestVenturesAndGrokbotAPI:
    """Verifies FastAPI REST endpoints for the 200 business ideas and Grokbot workflows."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from jarvis.api.server import app

        return TestClient(app)

    def test_api_list_ideas(self, client):
        resp = client.get("/ventures/ideas?limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert len(data["ideas"]) == 5

    def test_api_evaluate_idea(self, client):
        resp = client.get("/ventures/evaluate/IDEA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["idea_id"] == "IDEA-001"
        assert "RTX 4050" in data["hardware_feasibility"]["target_device"]

    def test_api_grokbot_leads(self, client):
        resp = client.post(
            "/ventures/grokbot/leads",
            json={
                "leads": [{"lead_id": "L1", "name": "John Doe", "company": "Acme Inc", "status": "new"}],
                "company_name": "JARVIS Automation",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_drafts"] == 1
        assert data["drafts"][0]["approval_required"] is True

    def test_api_grokbot_ad_pulse(self, client):
        resp = client.post(
            "/ventures/grokbot/ad-pulse",
            json={
                "metrics": [
                    {
                        "campaign_name": "Test",
                        "channel": "google",
                        "spend_usd": 100,
                        "impressions": 1000,
                        "clicks": 50,
                        "conversions": 5,
                        "revenue_usd": 200,
                    }
                ],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_spend_usd"] == 100.0
        assert data["total_conversions"] == 5
