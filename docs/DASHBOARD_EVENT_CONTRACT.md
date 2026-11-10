# JARVIS Dashboard Real-Time Event Contract & Telemetry Specification

**Date:** 2026-11-10  
**Transport:** Full-Duplex WebSocket (`/ws/stream`)  
**Format:** JSON  

---

## 1. Message Types

All messages emitted over `/ws/stream` contain a `type` discriminator.

### A. Periodic Telemetry Heartbeat (`type: "telemetry_pulse"`)
Emitted periodically every 1.5 seconds.
```json
{
  "type": "telemetry_pulse",
  "cpu_percent": 14.2,
  "ram_percent": 56.8,
  "disk_percent": 68.1,
  "kill_switch_active": false,
  "timestamp": 1794419650.123
}
```

### B. Execution Event (`type: "execution_event"`)
Emitted by the Orchestrator and specialist agents during task execution. Zero simulated client timeouts are allowed.
```json
{
  "type": "execution_event",
  "event_id": "evt_38f9b2a1",
  "execution_id": "tsk_c7c8c3678a",
  "conversation_id": "default_session",
  "task_id": "tsk_c7c8c3678a",
  "agent_id": "CareerAgent",
  "agent_role": "career",
  "event_type": "agent_started",
  "stage": 4,
  "stage_name": "execute",
  "status": "RUNNING",
  "timestamp": 1794419652.456,
  "evidence": {},
  "error": null,
  "payload": {
    "goal": "Identify AI internships matching user profile"
  }
}
```

---

## 2. Event Lifecycle & Stage Mapping

| Stage | Stage Name | Emitted `event_type` | Emitted `status` | Target UI Element |
| :--- | :--- | :--- | :--- | :--- |
| **1** | `understand` | `stage_transition` | `PLANNING` | `#stage-1.active` |
| **2** | `plan` | `stage_transition` | `PLANNING` | `#stage-2.active` |
| **3** | `select` | `stage_transition` | `AVAILABLE` | `#stage-3.active`, `#agent-[role]` card highlight |
| **4** | `execute` | `agent_started` | `RUNNING` | `#stage-4.active`, `#agent-[role]` glow + `RUNNING` badge |
| **4** | `execute` | `agent_completed` | `COMPLETED` | `#agent-[role]` border emerald + `COMPLETED` badge |
| **4** | `execute` | `agent_failed` | `FAILED` | `#agent-[role]` border crimson + `FAILED` badge |
| **5** | `verify` | `stage_transition` | `VERIFYING` | `#stage-5.active`, `#agent-reviewer` glow |
| **6** | `consolidate` | `task_completed` | `COMPLETED` | `#stage-6.completed`, Pipeline resets to `IDLE` |

---

## 3. Truthful State Rules

1. **No Simulated Progression**: Pipeline stages 1 through 6 advance only when corresponding backend events are received.
2. **No Keyword Highlighting**: Agent cards only enter the `RUNNING` state when `agent_started` is received over WebSocket with that agent's exact `agent_role`.
3. **Dynamic Agent Counts**: The agent header counts available specialists dynamically via `GET /api/v1/agents`.
