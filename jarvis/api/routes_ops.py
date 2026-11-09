"""JARVIS Operational Workflows REST API Routes.

Exposes the 3 core Grok-style / 200-Ideas lifesaver workflows:
1. Opportunity & Career Radar
2. Daily System & Business Pulse
3. Weekly Ops Sweep
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from jarvis.routines.ops_workflows import (
    opportunity_radar,
    daily_system_pulse,
    weekly_ops_sweep,
)

router = APIRouter(prefix="/api/v1/ops", tags=["Operational Workflows"])


@router.get("/opportunity-radar")
async def get_opportunity_radar(days_threshold: int = Query(default=5, ge=1)):
    """Runs read-only Opportunity Radar scan across career pipeline."""
    return opportunity_radar.run(days_threshold=days_threshold)


@router.get("/daily-pulse")
async def get_daily_system_pulse():
    """Returns single-pulse hardware, memory, disk, and model telemetry."""
    return daily_system_pulse.run()


@router.get("/weekly-sweep")
async def get_weekly_ops_sweep():
    """Reviews overdue tasks, stalled leads, and sets top 3 weekly priorities."""
    return weekly_ops_sweep.run()
