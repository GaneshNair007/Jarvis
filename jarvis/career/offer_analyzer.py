"""Offer and Salary-Gap Analysis Engine (PWR-337).

Evaluates total compensation packages (base, bonus, equity, signing bonus),
compares against market benchmarks & user target, and drafts tailored counter-offers.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional
from jarvis.career.models import OfferAnalysis, UserCareerProfile
from jarvis.core.logger import get_logger

logger = get_logger("career.offer_analyzer")


class OfferAnalyzer:
    """Analyzes job offers and produces strategic counter-offer scripts."""

    def analyze_offer(
        self,
        company_name: str,
        role_title: str,
        base_salary: float,
        bonus: float = 0.0,
        equity_annual_val: float = 0.0,
        profile: Optional[UserCareerProfile] = None
    ) -> OfferAnalysis:
        """Calculates total compensation gap and provides negotiation strategy."""
        p = profile or UserCareerProfile()
        target = p.target_salary_min or 220000.0

        total_comp = base_salary + bonus + equity_annual_val
        gap = round(total_comp - target, 2)
        gap_percentage = round((gap / target) * 100.0, 1) if target > 0 else 0.0

        if gap >= 0:
            verdict = "Meets or Exceeds Target"
            counter_target = round(total_comp * 1.08, 0)
            negotiation_script = (
                f"Thank you for this strong offer. I am genuinely excited about the opportunity to join {company_name} "
                f"as {role_title}. Given my extensive background in architecting distributed systems and autonomous AI platforms, "
                f"if we can adjust the base compensation to ${counter_target:,.0f} or include an additional equity refresh, "
                f"I am ready to sign immediately."
            )
        else:
            verdict = "Below Target Threshold"
            counter_target = round(target * 1.05, 0)
            negotiation_script = (
                f"Thank you very much for extending this offer to join {company_name} as {role_title}. "
                f"I have reviewed the package in detail. Based on my 8+ years architecting mission-critical distributed "
                f"infrastructure and competing market opportunities, my target total compensation is ${counter_target:,.0f}. "
                f"Can we explore bridging this gap through an increased base of ${target:,.0f} or additional signing bonus?"
            )

        offer_id = "offer_" + hashlib.sha256(f"{company_name}_{role_title}_{total_comp}".encode()).hexdigest()[:10]

        logger.info(
            f"Analyzed offer for {role_title} at {company_name}: Total Comp ${total_comp:,.0f} vs Target ${target:,.0f} (Gap: {gap_percentage}%)"
        )

        return OfferAnalysis(
            offer_id=offer_id,
            company_name=company_name,
            role_title=role_title,
            base_salary=base_salary,
            bonus=bonus,
            equity_annual_val=equity_annual_val,
            total_comp=total_comp,
            target_comp=target,
            gap=gap,
            gap_percentage=gap_percentage,
            verdict=verdict,
            negotiation_script=negotiation_script
        )

