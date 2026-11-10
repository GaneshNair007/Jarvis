"""
JARVIS Cross-Device API Endpoints
=================================
Inbound Webhook and Remote Execution Gateway:
- POST /api/v1/crossdevice/whatsapp/webhook: Ingests phone commands sent via WhatsApp
- POST /api/v1/crossdevice/switch/webhook: Ingests commands from Switch Protocol rooms
- GET  /api/v1/crossdevice/presence: Real-time presence status of laptop & phone
- POST /api/v1/crossdevice/presence/heartbeat: Keepalive ping endpoint
- GET  /api/v1/crossdevice/tasks: Lists queued cross-device tasks
- POST /api/v1/crossdevice/tasks/{task_id}/execute: Executes a queued remote task
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Request, status, Query
from pydantic import BaseModel, Field

from jarvis.core.logger import get_logger
from jarvis.core.cross_device_queue import cross_device_queue, CrossDeviceTask, TaskStatus, TaskPriority
from jarvis.core.presence_manager import presence_manager, DeviceType, PresenceState
from jarvis.core.remote_router import remote_router

logger = get_logger("api.routes_crossdevice")

router = APIRouter(tags=["Cross-Device Remote Queue"])


class WhatsAppWebhookPayload(BaseModel):
    From: Optional[str] = Field(default=None, description="Twilio/Meta webhook sender phone number")
    Body: Optional[str] = Field(default=None, description="Incoming message body")
    sender: Optional[str] = Field(default=None, description="Direct sender phone number")
    message: Optional[str] = Field(default=None, description="Direct message text")
    priority: str = Field(default="HIGH", description="Task priority (CRITICAL, HIGH, MEDIUM, LOW)")
    execute_now: bool = Field(default=True, description="Whether to immediately trigger execution on laptop")


class SwitchWebhookPayload(BaseModel):
    room_id: str = Field(default="general", description="Switch team room ID")
    sender: str = Field(default="ganesh", description="Sender username or agent ID")
    message: Optional[str] = Field(default=None, description="Message content")
    command: Optional[str] = Field(default=None, description="Command prompt to execute")
    priority: str = Field(default="HIGH", description="Task priority")
    execute_now: bool = Field(default=True, description="Trigger local execution immediately")


class HeartbeatPayload(BaseModel):
    device_id: str = Field(..., description="Device identifier: 'laptop', 'phone'")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Device metrics / telemetry")
    status: Optional[str] = Field(default=None, description="Optional manual presence status override")


class EnqueueTaskPayload(BaseModel):
    command: str = Field(..., description="Task command string")
    source_device: str = Field(default="phone", description="Source device: 'phone', 'laptop'")
    transport: str = Field(default="api", description="Transport channel: 'whatsapp', 'switch', 'api'")
    sender_id: str = Field(default="+919324094474", description="Sender phone number or ID")
    priority: str = Field(default="HIGH", description="Priority level")
    payload: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Optional context payload")
    execute_now: bool = Field(default=False, description="Execute immediately")


def _clean_phone(raw: Optional[str]) -> str:
    """Normalizes phone string to numeric format without spaces, hyphens, or prefixes."""
    if not raw:
        return ""
    cleaned = raw.strip().lower()
    if cleaned.startswith("whatsapp:"):
        cleaned = cleaned[len("whatsapp:"):]
    cleaned = cleaned.replace(" ", "").replace("-", "")
    if cleaned.startswith("+"):
        cleaned = cleaned[1:]
    return cleaned


def _verify_authorized_sender(sender_phone: Optional[str]) -> None:
    """
    Enforces security gate: only authorized candidate profile phone
    (+91 9324094474) may execute remote commands on the host laptop.
    """
    if not sender_phone:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authorization failed: Sender phone number is missing.",
        )

    clean_sender = _clean_phone(sender_phone)
    clean_canonical = _clean_phone(presence_manager.canonical_phone)

    if clean_sender != clean_canonical:
        logger.warning(f"Unauthorized cross-device command attempt from '{sender_phone}' (expected '{presence_manager.canonical_phone}')")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Security violation: Phone number '{sender_phone}' is not authorized to execute remote commands.",
        )


async def _run_task_background(task_id: str) -> None:
    """Asynchronously claims and runs a queued task."""
    try:
        await cross_device_queue.execute_task_flow(task_id)
    except Exception as exc:
        logger.error(f"Background task execution failed for '{task_id}': {exc}", exc_info=True)


# ── Webhook: WhatsApp ────────────────────────────────────────────────────────

@router.post("/api/v1/crossdevice/whatsapp/webhook")
@router.post("/crossdevice/whatsapp/webhook")
async def handle_whatsapp_webhook(
    payload: WhatsAppWebhookPayload,
    background_tasks: BackgroundTasks,
):
    """
    Inbound webhook receiver for WhatsApp messages.
    Validates sender authorization (+91 9324094474), updates phone presence,
    queues the command into CrossDeviceTaskQueue, and triggers execution.
    """
    sender = payload.From or payload.sender
    _verify_authorized_sender(sender)

    command = (payload.Body or payload.message or "").strip()
    if not command:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Command text is empty.")

    # Refresh phone presence on active inbound message
    presence_manager.record_heartbeat(
        device_id=DeviceType.PHONE.value,
        metadata={"channel": "whatsapp", "inbound_msg_len": len(command)},
    )

    # Enqueue task
    task = cross_device_queue.enqueue_task(
        command=command,
        source_device="phone",
        transport="whatsapp",
        sender_id=sender or presence_manager.canonical_phone,
        priority=payload.priority,
        target_device="laptop",
    )

    if payload.execute_now:
        background_tasks.add_task(_run_task_background, task.task_id)

    return {
        "status": "QUEUED",
        "task_id": task.task_id,
        "source": "whatsapp",
        "sender": sender,
        "command": command,
        "executing_async": payload.execute_now,
        "message": f"Command received from phone. Enqueued as {task.task_id}.",
    }


# ── Webhook: Switch ──────────────────────────────────────────────────────────

@router.post("/api/v1/crossdevice/switch/webhook")
@router.post("/crossdevice/switch/webhook")
async def handle_switch_webhook(
    payload: SwitchWebhookPayload,
    background_tasks: BackgroundTasks,
):
    """
    Inbound webhook receiver for Switch Protocol collaborative rooms.
    Ingests team room commands and forwards them to the laptop cross-device queue.
    """
    command = (payload.command or payload.message or "").strip()
    if not command:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Command or message is required.")

    # Refresh Switch/Room presence
    presence_manager.record_heartbeat(
        device_id="switch_room",
        metadata={"room_id": payload.room_id, "sender": payload.sender},
    )

    task = cross_device_queue.enqueue_task(
        command=command,
        source_device="switch",
        transport="switch",
        sender_id=payload.sender,
        priority=payload.priority,
        target_device="laptop",
        payload={"room_id": payload.room_id},
    )

    if payload.execute_now:
        background_tasks.add_task(_run_task_background, task.task_id)

    return {
        "status": "QUEUED",
        "task_id": task.task_id,
        "source": "switch",
        "room_id": payload.room_id,
        "command": command,
        "executing_async": payload.execute_now,
        "message": f"Switch task enqueued: {task.task_id}.",
    }


# ── Presence Endpoints ───────────────────────────────────────────────────────

@router.get("/api/v1/crossdevice/presence")
@router.get("/crossdevice/presence")
def get_presence_status():
    """Returns real-time presence and heartbeat telemetry for all monitored devices."""
    return {
        "devices": presence_manager.get_all_presence(),
        "canonical_phone": presence_manager.canonical_phone,
        "timestamp": time.time(),
    }


@router.post("/api/v1/crossdevice/presence/heartbeat")
@router.post("/crossdevice/presence/heartbeat")
def submit_heartbeat(payload: HeartbeatPayload):
    """Submits keepalive heartbeat ping for a device."""
    dev_id = payload.device_id.lower().strip()
    if payload.status:
        presence_manager.set_device_status(dev_id, payload.status)
    else:
        presence_manager.record_heartbeat(dev_id, metadata=payload.metadata)

    return {
        "status": "RECORDED",
        "device_id": dev_id,
        "current_status": presence_manager.get_device_status(dev_id),
    }


# ── Queue Task Management ────────────────────────────────────────────────────

@router.get("/api/v1/crossdevice/tasks")
@router.get("/crossdevice/tasks")
def list_cross_device_tasks(
    status: Optional[str] = Query(None, description="Filter by status (QUEUED, TRANSFERRED, EXECUTING, COMPLETED, FAILED)"),
    target_device: Optional[str] = Query(None, description="Filter by target device"),
    limit: int = Query(50, ge=1, le=200),
):
    """Lists cross-device tasks stored in the SQLite WAL queue."""
    tasks = cross_device_queue.list_tasks(status=status, target_device=target_device, limit=limit)
    return {
        "total": len(tasks),
        "tasks": [t.to_dict() for t in tasks],
    }


@router.get("/api/v1/crossdevice/tasks/{task_id}")
@router.get("/crossdevice/tasks/{task_id}")
def get_cross_device_task(task_id: str):
    """Retrieves single cross-device task by ID."""
    task = cross_device_queue.get_task(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task '{task_id}' not found.")
    return task.to_dict()


@router.post("/api/v1/crossdevice/tasks/{task_id}/execute")
@router.post("/crossdevice/tasks/{task_id}/execute")
async def execute_cross_device_task(task_id: str):
    """Executes a queued cross-device task on the host laptop."""
    task = cross_device_queue.get_task(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task '{task_id}' not found.")

    res = await cross_device_queue.execute_task_flow(task_id)
    return {
        "status": res.status,
        "task_id": res.task_id,
        "result": res.result,
        "error": res.error_message,
        "completed_at": res.completed_at,
    }
