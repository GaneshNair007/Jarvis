"""
JARVIS Integrations REST API Routes
Exposes management, power execution, dry-runs, and audit trails for all integrations.
Endpoints:
  GET /integrations
  GET /integrations/{integration_id}
  POST /integrations/{integration_id}/connect
  POST /integrations/{integration_id}/disconnect
  POST /integrations/{integration_id}/enable
  POST /integrations/{integration_id}/disable
  GET /integrations/{integration_id}/health
  GET /integrations/{integration_id}/powers
  POST /integrations/{integration_id}/powers/{power_id}/execute
  POST /integrations/{integration_id}/powers/{power_id}/dry-run
  GET /integrations/{integration_id}/audit
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field

from integrations import integration_registry

router = APIRouter(tags=["Integrations"])

class ConnectRequest(BaseModel):
    credentials: Optional[Dict[str, str]] = Field(default=None, description="Optional runtime credentials")

class ExecutePowerRequest(BaseModel):
    params: Dict[str, Any] = Field(default_factory=dict, description="Parameters to pass to the power")
    approval_token: Optional[str] = Field(default=None, description="Cryptographic approval token for Tier 2/3 actions")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Optional task execution context")

class DryRunRequest(BaseModel):
    params: Dict[str, Any] = Field(default_factory=dict, description="Parameters to simulate")

@router.get("/integrations")
def list_integrations(category: Optional[str] = None) -> Dict[str, Any]:
    """Lists all registered integrations with connection and safety status."""
    if category:
        items = integration_registry.list_by_category(category)
    else:
        items = integration_registry.list_integrations()
    return {
        "total": len(items),
        "integrations": items
    }

@router.get("/integrations/{integration_id}")
def get_integration(integration_id: str) -> Dict[str, Any]:
    """Retrieves full metadata for a specific integration."""
    integ = integration_registry.get(integration_id)
    if not integ:
        raise HTTPException(status_code=404, detail=f"Integration '{integration_id}' not found")
    return {
        "integration_id": integ.integration_id,
        "display_name": integ.display_name,
        "category": integ.category,
        "description": integ.description,
        "enabled": integ.enabled,
        "connected": integ.connected,
        "kill_switched": integ.kill_switched,
        "danger_level": integ.danger_level,
        "default_approval_tier": integ.default_approval_tier,
        "rate_limit_rpm": integ.rate_limit_rpm,
        "cost_model": integ.cost_model,
        "data_sensitivity": integ.data_sensitivity,
        "required_credentials": integ.required_credentials,
        "required_scopes": integ.required_scopes,
        "powers": integ.list_powers(),
        "documentation_url": integ.documentation_url
    }

@router.post("/integrations/{integration_id}/connect")
def connect_integration(integration_id: str, req: Optional[ConnectRequest] = None) -> Dict[str, Any]:
    """Connects or authenticates to the integration."""
    integ = integration_registry.get(integration_id)
    if not integ:
        raise HTTPException(status_code=404, detail=f"Integration '{integration_id}' not found")
    creds = req.credentials if req else None
    connected = integ.connect(creds)
    return {
        "integration_id": integration_id,
        "connected": connected,
        "status": "CONNECTED" if connected else "CONNECTION_FAILED"
    }

@router.post("/integrations/{integration_id}/disconnect")
def disconnect_integration(integration_id: str) -> Dict[str, Any]:
    """Disconnects and tears down active sessions."""
    integ = integration_registry.get(integration_id)
    if not integ:
        raise HTTPException(status_code=404, detail=f"Integration '{integration_id}' not found")
    integ.disconnect()
    return {
        "integration_id": integration_id,
        "connected": False,
        "status": "DISCONNECTED"
    }

@router.post("/integrations/{integration_id}/enable")
def enable_integration(integration_id: str) -> Dict[str, Any]:
    """Enables integration for automated power execution."""
    success = integration_registry.enable(integration_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Integration '{integration_id}' not found")
    return {"integration_id": integration_id, "enabled": True}

@router.post("/integrations/{integration_id}/disable")
def disable_integration(integration_id: str) -> Dict[str, Any]:
    """Disables integration and all associated powers."""
    success = integration_registry.disable(integration_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Integration '{integration_id}' not found")
    return {"integration_id": integration_id, "enabled": False}

@router.get("/integrations/{integration_id}/health")
def integration_health(integration_id: str) -> Dict[str, Any]:
    """Returns live diagnostic health probe for the integration."""
    integ = integration_registry.get(integration_id)
    if not integ:
        raise HTTPException(status_code=404, detail=f"Integration '{integration_id}' not found")
    report = integ.health_check()
    return report.model_dump()

@router.get("/integrations/{integration_id}/powers")
def list_integration_powers(integration_id: str) -> Dict[str, Any]:
    """Lists all powers exposed by this integration."""
    integ = integration_registry.get(integration_id)
    if not integ:
        raise HTTPException(status_code=404, detail=f"Integration '{integration_id}' not found")
    powers = integ.list_powers()
    return {
        "integration_id": integration_id,
        "total_powers": len(powers),
        "powers": powers
    }

@router.post("/integrations/{integration_id}/powers/{power_id}/execute")
def execute_integration_power(
    integration_id: str,
    power_id: str,
    req: ExecutePowerRequest
) -> Dict[str, Any]:
    """Executes an integration power behind rate limits, kill-switches, and approval gates."""
    integ = integration_registry.get(integration_id)
    if not integ:
        raise HTTPException(status_code=404, detail=f"Integration '{integration_id}' not found")

    result = integ.execute_power(
        power_id=power_id,
        params=req.params,
        approval_token=req.approval_token,
        context=req.context
    )
    return result

@router.post("/integrations/{integration_id}/powers/{power_id}/dry-run")
def dry_run_integration_power(
    integration_id: str,
    power_id: str,
    req: DryRunRequest
) -> Dict[str, Any]:
    """Previews action plan, content hash, and approval requirements without mutating state."""
    integ = integration_registry.get(integration_id)
    if not integ:
        raise HTTPException(status_code=404, detail=f"Integration '{integration_id}' not found")

    plan = integ.dry_run(power_id=power_id, params=req.params)
    return plan

@router.get("/integrations/{integration_id}/audit")
def integration_audit(
    integration_id: str,
    limit: int = Query(20, ge=1, le=100)
) -> Dict[str, Any]:
    """Retrieves immutable audit trail for actions dispatched through this integration."""
    integ = integration_registry.get(integration_id)
    if not integ:
        raise HTTPException(status_code=404, detail=f"Integration '{integration_id}' not found")

    entries = integ.audit(limit=limit)
    return {
        "integration_id": integration_id,
        "total_events": len(entries),
        "events": entries
    }
