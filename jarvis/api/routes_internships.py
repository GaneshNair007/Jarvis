"""API routes for JARVIS internship discovery and human-approved application preparation."""
from __future__ import annotations

from typing import Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from jarvis.career.internship_automation import internship_automation

router = APIRouter(prefix="/api/v1/internships", tags=["internship-automation"])


class DiscoverRequest(BaseModel):
    boards: list[dict[str, str]] = Field(default_factory=list)


class ManualOpportunityRequest(BaseModel):
    source: str
    company: str
    title: str
    url: str
    location: str = ""
    description: str = ""
    employment_type: str = ""


class PrepareRequest(BaseModel):
    opportunity_id: str


class ApprovalRequest(BaseModel):
    reviewed_hash: str
    confirm: bool = False


@router.get("/status")
def status():
    return internship_automation.status()


@router.post("/discover")
async def discover(request: DiscoverRequest):
    try:
        return await internship_automation.discover(request.boards)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Discovery failed: {type(exc).__name__}: {exc}")


@router.post("/opportunities/manual")
def add_manual_opportunity(request: ManualOpportunityRequest):
    try:
        return internship_automation.add_manual_opportunity(request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/opportunities")
def list_opportunities(limit: int = 100, query: Optional[str] = None):
    return {"opportunities": internship_automation.list_opportunities(limit=limit, query=query)}


@router.post("/applications/prepare")
def prepare_application(request: PrepareRequest):
    try:
        return internship_automation.prepare_application(request.opportunity_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.get("/applications")
def list_applications(status: Optional[str] = None):
    items = internship_automation.list_applications()
    if status:
        items = [item for item in items if item["status"] == status]
    return {"applications": items}


@router.post("/applications/{application_id}/approve")
def approve_application(application_id: str, request: ApprovalRequest):
    try:
        return internship_automation.approve_application(
            application_id=application_id,
            reviewed_hash=request.reviewed_hash,
            confirm=request.confirm,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc))


class ManualSubmissionRequest(BaseModel):
    one_time_approval_token: str
    confirmation_evidence: str
    confirm: bool = False


@router.post("/applications/{application_id}/mark-submitted")
def mark_manually_submitted(application_id: str, request: ManualSubmissionRequest):
    try:
        return internship_automation.mark_manually_submitted(
            application_id=application_id,
            token=request.one_time_approval_token,
            confirmation_evidence=request.confirmation_evidence,
            confirm=request.confirm,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
