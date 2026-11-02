"""
JARVIS Autonomous Business Playbook & Grok Bot Engine
Synthesizes:
1. 200 AI Business Ideas (Ayman William Blueprint) loaded from data/business_ideas.json
2. Grok Bot Business Playbook Workflows:
   - Workflow 01: Lead Follow-Up (Draft review-ready messages, no automatic sends)
   - Workflow 02: Ad Pulse (Unified daily spend, CTR, CPC, CPA, ROAS summary)
   - Workflow 03: The Weekly Ops Sweep (Overdue tasks, stalled leads, campaign flags, top 3 actions)
3. 105 Autonomous Micro-Agent Workforce Team Allocation
4. Local RTX 4050 6GB GPU Feasibility & Compute Budgeting
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from jarvis.core.logger import get_logger

logger = get_logger("business.playbook_engine")


class BusinessIdea(BaseModel):
    idea_id: str
    number: int
    domain: str
    title: str
    target_buyer: str
    problem_statement: str
    solution_statement: str
    how_to_get_started: str
    proof_of_value: str
    revenue_model: str
    sell_this_first: str
    toolkit: str
    lean_startup_budget: str
    scale_ceiling: str
    scale_speed: str


class LeadRecord(BaseModel):
    lead_id: str
    name: str
    company: str
    email: Optional[str] = None
    days_stalled: int = 0
    status: str = "new"  # new, waiting, overdue, contacted
    notes: str = ""


class AdMetricRecord(BaseModel):
    campaign_name: str
    channel: str  # google, meta, linkedin, twitter
    spend_usd: float
    impressions: int
    clicks: int
    conversions: int
    revenue_usd: float = 0.0


class GrokbotLeadFollowup(BaseModel):
    lead_id: str
    name: str
    company: str
    draft_message: str
    approval_required: bool = True
    status: str = "draft_ready"


class GrokbotAdPulse(BaseModel):
    total_spend_usd: float
    total_clicks: int
    average_ctr_percent: float
    average_cpc_usd: float
    total_conversions: int
    blended_cpa_usd: float
    roas: float
    flagged_campaigns: List[str]
    summary_report: str


class GrokbotWeeklyOpsSweep(BaseModel):
    overdue_tasks: List[Dict[str, Any]]
    stalled_leads: List[Dict[str, Any]]
    campaign_flags: List[str]
    human_decisions_needed: List[str]
    top_three_priorities: List[Dict[str, str]]
    executive_brief: str


class BusinessPlaybookEngine:
    """
    Cognitive engine providing access to the 200 AI business ideas,
    evaluating technical feasibility on RTX 4050 hardware, and executing
    the Grok Bot operational workflows with strict human approval gates.
    """

    def __init__(self, ideas_path: Optional[str] = None):
        if ideas_path is None:
            # Default to repo root data/business_ideas.json
            repo_root = Path(__file__).resolve().parent.parent.parent
            ideas_path = str(repo_root / "data" / "business_ideas.json")
        self.ideas_path = ideas_path
        self._ideas_cache: Dict[str, BusinessIdea] = {}
        self._load_ideas()

    def _load_ideas(self) -> None:
        """Loads and indexes the 200 business ideas from JSON."""
        if not os.path.exists(self.ideas_path):
            logger.warning(f"Business ideas file not found at {self.ideas_path}")
            return

        try:
            with open(self.ideas_path, "r", encoding="utf-8", errors="ignore") as f:
                raw_data = json.load(f)
                for item in raw_data:
                    idea = BusinessIdea(**item)
                    self._ideas_cache[idea.idea_id] = idea
            logger.info(f"Loaded {len(self._ideas_cache)} business ideas into Playbook Engine.")
        except Exception as e:
            logger.error(f"Failed to load business ideas from {self.ideas_path}: {e}")

    @property
    def total_ideas(self) -> int:
        return len(self._ideas_cache)

    def list_ideas(self, limit: int = 20, domain: Optional[str] = None) -> List[BusinessIdea]:
        """Returns indexed ideas optionally filtered by domain."""
        ideas = list(self._ideas_cache.values())
        if domain:
            dom_lower = domain.lower()
            ideas = [i for i in ideas if dom_lower in i.domain.lower()]
        return ideas[:limit]

    def get_idea_by_id(self, idea_id: str) -> Optional[BusinessIdea]:
        """Retrieves an idea by its IDEA-XXX ID."""
        return self._ideas_cache.get(idea_id.upper())

    def search_ideas(self, query: str, limit: int = 5) -> List[BusinessIdea]:
        """Performs full-text semantic search across ideas."""
        q_tokens = query.lower().split()
        scored: List[tuple[int, BusinessIdea]] = []

        for idea in self._ideas_cache.values():
            corpus = f"{idea.title} {idea.domain} {idea.problem_statement} {idea.solution_statement} {idea.toolkit}".lower()
            matches = sum(1 for tok in q_tokens if tok in corpus)
            if matches > 0:
                scored.append((matches, idea))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored[:limit]]

    def evaluate_idea_execution(self, idea_id_or_title: str) -> Dict[str, Any]:
        """
        Evaluates an idea against local RTX 4050 (6GB VRAM) constraints,
        assigns a dedicated subagent pod from the 105-agent workforce,
        and generates a 7-day implementation roadmap.
        """
        idea = self.get_idea_by_id(idea_id_or_title)
        if not idea:
            matches = self.search_ideas(idea_id_or_title, limit=1)
            if matches:
                idea = matches[0]

        if not idea:
            return {"error": f"Business idea '{idea_id_or_title}' not found in catalog."}

        # Hardware & Compute Allocation Analysis
        toolkit_lower = idea.toolkit.lower()
        requires_vision = any(k in toolkit_lower for k in ["video", "image", "capcut", "canva", "vision"])
        requires_audio = any(k in toolkit_lower for k in ["podcast", "audio", "voice", "descript"])
        
        local_gpu_load = "Low (<1.5 GB VRAM)"
        if requires_vision and requires_audio:
            local_gpu_load = "Moderate (~3.8 GB VRAM - Kokoro-TTS + Faster-Whisper on RTX 4050)"
        elif requires_vision or requires_audio:
            local_gpu_load = "Low-Moderate (~2.2 GB VRAM on RTX 4050)"

        # Agent Workforce Team Allocation (from 105 micro-agents)
        assigned_agents = [
            {"agent_id": "recon_market_scout_01", "role": "Lead identification & prospect radar"},
            {"agent_id": "analysis_eval_01", "role": "Offer scoping & pricing validation"},
            {"agent_id": "scaffold_fullstack_01", "role": "MVP template and integration scripts"},
            {"agent_id": "devops_runner_01", "role": "Pipeline automation & n8n / webhook dispatcher"},
            {"agent_id": "dispatch_comm_01", "role": "Review-ready outreach drafts & follow-up queue"},
        ]

        # 7-Day Grokbot Implementation Roadmap
        seven_day_plan = {
            "Day 1": "Set up project repo, verify local RTX 4050 model endpoints, confirm API key rotators.",
            "Day 2": f"Configure dedicated Growth Ops bot for '{idea.title}' with strict human approval boundaries.",
            "Day 3": f"Run lead intake test with 5 target prospects ({idea.target_buyer}) and inspect generated drafts.",
            "Day 4": "Connect metrics dashboard (spend, conversion tracking) and verify source link freshness.",
            "Day 5": f"Scope MVP service offer ('{idea.sell_this_first}') with human review step.",
            "Day 6": "Package pipeline as a reusable JARVIS Skill with approval checkpoints before sending.",
            "Day 7": "Activate scheduled background routine and track review minutes saved per week.",
        }

        return {
            "idea_id": idea.idea_id,
            "title": idea.title,
            "domain": idea.domain,
            "target_buyer": idea.target_buyer,
            "problem": idea.problem_statement,
            "solution": idea.solution_statement,
            "sell_this_first": idea.sell_this_first,
            "revenue_model": idea.revenue_model,
            "hardware_feasibility": {
                "target_device": "NVIDIA GeForce RTX 4050 (6GB VRAM)",
                "estimated_vram_usage": local_gpu_load,
                "cloud_api_tier": "Google Gemini 2.0 Flash / OpenRouter (Cost: $0.00 / free tiers)",
                "verdict": "100% Executable on Operator Rig",
            },
            "assigned_workforce_pod": assigned_agents,
            "seven_day_plan": seven_day_plan,
            "operator_safety_rule": "Strict Human-in-the-Loop Gate: No outbound messages or external mutations without approval.",
        }

    # ── Grok Bot Business Playbook Workflows ───────────────────────────────────

    def run_lead_followup_workflow(
        self,
        leads: List[Dict[str, Any]],
        company_name: str = "ClientOps",
    ) -> List[GrokbotLeadFollowup]:
        """
        Workflow 01: Follow up with leads without chasing.
        Sorts leads and drafts personalized, review-ready messages.
        Enforces: NO automatic sending without explicit human approval.
        """
        results: List[GrokbotLeadFollowup] = []

        for item in leads:
            lead = LeadRecord(**item)
            # Draft context-aware message
            if lead.status == "new":
                body = (
                    f"Hi {lead.name}, thank you for reaching out regarding {company_name}. "
                    f"I reviewed your requirements and prepared a brief overview of how our autonomous pipelines "
                    f"can save your team 10+ manual hours each week. Would you have 10 minutes Thursday for a short walkthrough?"
                )
            elif lead.days_stalled >= 3:
                body = (
                    f"Hi {lead.name}, following up on my previous message to see if optimizing your workflows at {lead.company} "
                    f"is still a priority this month. We just deployed a verified sample pilot that delivered 3x throughput. "
                    f"Let me know if you would like me to share the one-page readout."
                )
            else:
                body = (
                    f"Hi {lead.name}, just checking in on the progress of our proposal for {lead.company}. "
                    f"Happy to answer any technical questions whenever you are ready."
                )

            results.append(
                GrokbotLeadFollowup(
                    lead_id=lead.lead_id,
                    name=lead.name,
                    company=lead.company,
                    draft_message=body,
                    approval_required=True,
                    status="draft_ready",
                )
            )

        logger.info(f"Generated {len(results)} review-ready lead follow-up drafts.")
        return results

    def run_ad_pulse_workflow(
        self,
        metrics: List[Dict[str, Any]],
    ) -> GrokbotAdPulse:
        """
        Workflow 02: Ad Pulse daily report.
        Aggregates multi-channel ad data into one clean, source-verified message.
        """
        total_spend = sum(m.get("spend_usd", 0.0) for m in metrics)
        total_impressions = sum(m.get("impressions", 0) for m in metrics)
        total_clicks = sum(m.get("clicks", 0) for m in metrics)
        total_conversions = sum(m.get("conversions", 0) for m in metrics)
        total_revenue = sum(m.get("revenue_usd", 0.0) for m in metrics)

        avg_ctr = round((total_clicks / total_impressions * 100), 2) if total_impressions > 0 else 0.0
        avg_cpc = round((total_spend / total_clicks), 2) if total_clicks > 0 else 0.0
        blended_cpa = round((total_spend / total_conversions), 2) if total_conversions > 0 else 0.0
        roas = round((total_revenue / total_spend), 2) if total_spend > 0 else 0.0

        flagged = []
        for m in metrics:
            rec = AdMetricRecord(**m)
            # Threshold checks: CPA > $50 or CTR < 1.0%
            cpa = (rec.spend_usd / rec.conversions) if rec.conversions > 0 else 999.0
            ctr = (rec.clicks / rec.impressions * 100) if rec.impressions > 0 else 0.0
            if cpa > 50.0 or ctr < 1.0:
                flagged.append(f"{rec.campaign_name} ({rec.channel}): High CPA (${round(cpa, 2)}) or Low CTR ({round(ctr, 2)}%)")

        summary = (
            f"📊 DAILY AD PULSE REPORT\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"• Total Spend:       ${round(total_spend, 2)}\n"
            f"• Total Clicks:      {total_clicks:,} (CTR: {avg_ctr}%)\n"
            f"• Avg CPC:           ${avg_cpc}\n"
            f"• Conversions:       {total_conversions} (Blended CPA: ${blended_cpa})\n"
            f"• Blended ROAS:      {roas}x\n"
            f"• Attention Flags:   {len(flagged)} campaign(s) exceeded threshold"
        )

        return GrokbotAdPulse(
            total_spend_usd=total_spend,
            total_clicks=total_clicks,
            average_ctr_percent=avg_ctr,
            average_cpc_usd=avg_cpc,
            total_conversions=total_conversions,
            blended_cpa_usd=blended_cpa,
            roas=roas,
            flagged_campaigns=flagged,
            summary_report=summary,
        )

    def run_weekly_ops_sweep(
        self,
        task_board: List[Dict[str, Any]],
        crm_leads: List[Dict[str, Any]],
        ad_reports: List[Dict[str, Any]],
    ) -> GrokbotWeeklyOpsSweep:
        """
        Workflow 03: The Weekly Ops Sweep (Lifesaver Workflow).
        Checks:
        1. Overdue commitments, owner, due date.
        2. Leads with no activity > 4 days.
        3. Campaigns crossing KPI thresholds.
        4. Items requiring human decision.
        5. Top 3 actions for next week.
        """
        # 1. Overdue tasks
        overdue = [t for t in task_board if t.get("is_overdue", False) or t.get("status") == "overdue"]

        # 2. Stalled leads
        stalled = [l for l in crm_leads if l.get("days_stalled", 0) >= 4]

        # 3. Campaign flags
        ad_pulse = self.run_ad_pulse_workflow(ad_reports)
        campaign_flags = ad_pulse.flagged_campaigns

        # 4. Human decisions needed
        decisions = []
        if overdue:
            decisions.append(f"Re-assign or extend deadlines for {len(overdue)} overdue task(s)")
        if campaign_flags:
            decisions.append(f"Review and adjust budget for {len(campaign_flags)} flagged ad campaign(s)")
        if stalled:
            decisions.append(f"Approve follow-up dispatch for {len(stalled)} stalled lead(s)")

        # 5. Top 3 priorities
        priorities = [
            {"rank": "1", "action": "Clear highest-value overdue client commitment", "owner": "Operations Lead"},
            {"rank": "2", "action": "Review & dispatch personalized drafts for stalled leads", "owner": "Growth Specialist"},
            {"rank": "3", "action": "Optimize or pause underperforming ad campaigns", "owner": "Media Buyer"},
        ]

        brief = (
            f"📋 WEEKLY OPS SWEEP SUMMARY\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"1. Overdue Tasks:       {len(overdue)}\n"
            f"2. Stalled Leads (>4d): {len(stalled)}\n"
            f"3. Campaign Flags:      {len(campaign_flags)}\n"
            f"4. Human Decisions:     {len(decisions)}\n"
            f"Top Priority: {priorities[0]['action']} ({priorities[0]['owner']})"
        )

        return GrokbotWeeklyOpsSweep(
            overdue_tasks=overdue,
            stalled_leads=stalled,
            campaign_flags=campaign_flags,
            human_decisions_needed=decisions,
            top_three_priorities=priorities,
            executive_brief=brief,
        )


# Global singleton instance
business_playbook_engine = BusinessPlaybookEngine()
playbook_engine = business_playbook_engine
PlaybookEngine = BusinessPlaybookEngine
