"""Browser and Research API Routes.

Exposes REST endpoints for search, reading DOM content, capturing screenshots,
and triggering autonomous deep research.
"""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from jarvis.powers.browser_powers import browser_powers
from jarvis.core.policy_gate import policy_gate

router = APIRouter(prefix="/api/v1/browser", tags=["browser"])


class SearchRequest(BaseModel):
    query: str
    max_results: int = 5


class ReadURLRequest(BaseModel):
    url: str
    allow_private: bool = False


class ScreenshotRequest(BaseModel):
    url: str
    full_page: bool = False
    task_id: str = "api_screenshot"


class ResearchRequest(BaseModel):
    topic: str
    max_docs: int = Field(default=3, ge=1, le=10)
    task_id: str = "api_research"


@router.post("/search")
def search_web(request: SearchRequest):
    """Executes a privacy-first web search."""
    try:
        return browser_powers.search_web(query=request.query, max_results=request.max_results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/read")
def read_page(request: ReadURLRequest):
    """Fetches DOM content, headings, and links from a URL with injection detection."""
    try:
        return browser_powers.read_url(url=request.url, allow_private=request.allow_private)
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/screenshot")
def capture_screenshot(request: ScreenshotRequest):
    """Captures a screenshot of the target URL and returns file path and SHA-256 hash."""
    try:
        return browser_powers.capture_screenshot(
            url=request.url,
            full_page=request.full_page,
            task_id=request.task_id,
        )
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/research")
def trigger_deep_research(request: ResearchRequest):
    """Performs multi-doc deep research with verifiable screenshots and citations."""
    try:
        return browser_powers.deep_research(
            topic=request.topic,
            max_docs=request.max_docs,
            task_id=request.task_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
