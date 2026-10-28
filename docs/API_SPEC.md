# JARVIS API Specification

## 1. Model Router Endpoints
- `POST /model/route`: Evaluates task parameters and returns tier, selected model, and redaction summary.
- `POST /model/configure`: Dynamically configures provider endpoints and budget caps.
- `GET /model/status`: Returns provider health and circuit breaker status.
- `GET /model/usage`: Returns token usage counts by model.
- `GET /model/costs`: Returns daily and monthly dollar usage.
- `POST /model/approve-expensive-call`: Authorizes calls exceeding task limits.

## 2. Core Operational Endpoints
- `POST /api/v1/chat`: Ingress for text and voice queries.
- `GET /api/v1/powers`: Lists all capabilities in the registry.
- `GET /api/v1/powers/{power_id}`: Retrieves full schema for a power.
- `GET /api/v1/tasks`: Inspects state machine status for recent tasks.
- `POST /api/v1/approvals/{task_id}/resolve`: Approves or rejects a Level 3-5 pending action.
- `GET /api/v1/system/health`: Host telemetry (CPU, RAM, Disk).
- `POST /api/v1/kill-switch`: Toggles emergency halt.
- `GET /api/v1/audit`: Returns audit events and validates SHA-256 chain integrity.
- `WS /ws/stream`: Full-duplex WebSocket feed for the HUD visualizer.
