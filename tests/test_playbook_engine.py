"""
Unit and Integration Tests for JARVIS Playbook Engine
Validates:
  1. 200 AI Business Ideas integration from data/business_ideas.json
  2. Idea feasibility evaluation with RTX 4050 allocation and 105-agent workforce mapping
  3. GrokBot Playbook Workflow 01: Lead Follow-Up (draft review-ready, human-in-the-loop)
  4. GrokBot Playbook Workflow 02: Ad Pulse (CTR, CPC, CPA, ROAS, flag alerts)
  5. GrokBot Playbook Workflow 03: The Weekly Ops Sweep (overdue tasks, stalled leads, top 3 actions)
"""

import pytest
from jarvis.business.playbook_engine import (
    playbook_engine,
    PlaybookEngine,
    GrokbotLeadFollowup,
    GrokbotAdPulse,
    GrokbotWeeklyOpsSweep,
)


def test_playbook_loads_200_ideas():
    assert playbook_engine.total_ideas == 200
    ideas = playbook_engine.list_ideas(limit=5)
    assert len(ideas) == 5
    assert ideas[0].idea_id == "IDEA-001"


def test_evaluate_idea_execution():
    eval_result = playbook_engine.evaluate_idea_execution("IDEA-001")
    assert eval_result["idea_id"] == "IDEA-001"
    assert "hardware_feasibility" in eval_result
    assert "RTX 4050" in eval_result["hardware_feasibility"]["target_device"]
    assert "assigned_workforce_pod" in eval_result
    assert len(eval_result["assigned_workforce_pod"]) >= 3
    assert "seven_day_plan" in eval_result


def test_workflow_01_lead_followup():
    leads = [
        {"lead_id": "L1", "name": "Rahul Sharma", "company": "NexTech India", "days_stalled": 4, "status": "waiting"},
        {"lead_id": "L2", "name": "Priya Patel", "company": "RetailMart", "days_stalled": 0, "status": "new"},
    ]
    drafts = playbook_engine.run_lead_followup_workflow(leads=leads)
    assert len(drafts) == 2
    assert isinstance(drafts[0], GrokbotLeadFollowup)
    assert drafts[0].approval_required is True
    assert "Rahul" in drafts[0].draft_message
    assert drafts[1].status == "draft_ready"


def test_workflow_02_ad_pulse():
    campaigns = [
        {
            "campaign_name": "Google Search - AI Agents",
            "channel": "google",
            "spend_usd": 450.0,
            "impressions": 12000,
            "clicks": 450,
            "conversions": 18,
            "revenue_usd": 1800.0,
        },
        {
            "campaign_name": "LinkedIn - B2B Founders",
            "channel": "linkedin",
            "spend_usd": 800.0,
            "impressions": 5000,
            "clicks": 30,
            "conversions": 1,
            "revenue_usd": 200.0,
        },
    ]
    pulse = playbook_engine.run_ad_pulse_workflow(metrics=campaigns)
    assert isinstance(pulse, GrokbotAdPulse)
    assert pulse.total_spend_usd == 1250.0
    assert pulse.total_clicks == 480
    assert len(pulse.flagged_campaigns) >= 1
    assert "DAILY AD PULSE REPORT" in pulse.summary_report


def test_workflow_03_weekly_ops_sweep():
    task_board = [
        {
            "task_id": "T1",
            "name": "Deploy landing page",
            "status": "overdue",
            "owner": "scaffold_01",
            "due_date": "yesterday",
        },
        {"task_id": "T2", "name": "Run unit tests", "status": "completed", "owner": "devops_01", "due_date": "today"},
    ]
    crm_leads = [
        {"lead_id": "L10", "name": "Amit Verma", "company": "CloudMatrix", "days_stalled": 6, "status": "waiting"},
    ]
    ad_reports = [
        {
            "campaign_name": "Meta Ads Retargeting",
            "channel": "meta",
            "spend_usd": 300.0,
            "impressions": 2000,
            "clicks": 10,
            "conversions": 0,
            "revenue_usd": 0.0,
        },
    ]
    sweep = playbook_engine.run_weekly_ops_sweep(task_board=task_board, crm_leads=crm_leads, ad_reports=ad_reports)
    assert isinstance(sweep, GrokbotWeeklyOpsSweep)
    assert len(sweep.overdue_tasks) == 1
    assert len(sweep.stalled_leads) == 1
    assert len(sweep.top_three_priorities) == 3
    assert "WEEKLY OPS SWEEP SUMMARY" in sweep.executive_brief
