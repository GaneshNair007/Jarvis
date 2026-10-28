"""
JARVIS System Diagnostics Integration
Local-first integration providing host diagnostics, memory pressure metrics, and temp cleanup.
Demonstrates Tier 0 read-only observation and Tier 2 human approval gates.
"""

import time
import os
import psutil
from typing import Dict, Any, List, Optional

from integrations.base.base_integration import BaseIntegration
from integrations.base.integration_health import IntegrationStatus, HealthReport

class SystemDiagnosticsIntegration(BaseIntegration):
    """Local host telemetry and diagnostics integration."""

    def __init__(self):
        super().__init__(
            integration_id="system_diagnostics",
            display_name="System Diagnostics & Telemetry",
            category="IT Administration",
            description="Local host performance telemetry, resource tracking, and temp buffer maintenance.",
            required_credentials=[], # Local-first zero credential requirement
            required_scopes=["system:read", "system:write"],
            danger_level="medium",
            default_approval_tier=0,
            rate_limit_rpm=120,
            cost_model="free",
            data_sensitivity="low",
            documentation_url="https://docs.jarvis.internal/integrations/system"
        )
        self.connected = True # Always connected locally

    def connect(self, credentials: Optional[Dict[str, str]] = None) -> bool:
        self.connected = True
        self._record_audit("CONNECT", {}, "SUCCESS")
        return True

    def disconnect(self) -> bool:
        self.connected = False
        self._record_audit("DISCONNECT", {}, "SUCCESS")
        return True

    def health_check(self) -> HealthReport:
        errors = []
        if self.kill_switched:
            return HealthReport(
                integration_id=self.integration_id,
                status=IntegrationStatus.KILL_SWITCHED,
                connected=self.connected,
                enabled=self.enabled,
                kill_switched=True,
                errors=["Kill switch active for system diagnostics."]
            )

        try:
            cpu = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory().percent
            return HealthReport(
                integration_id=self.integration_id,
                status=IntegrationStatus.HEALTHY,
                connected=self.connected,
                enabled=self.enabled,
                kill_switched=False,
                latency_ms=1.2,
                details={"cpu_percent": cpu, "memory_percent": mem}
            )
        except Exception as e:
            return HealthReport(
                integration_id=self.integration_id,
                status=IntegrationStatus.DEGRADED,
                connected=self.connected,
                enabled=self.enabled,
                kill_switched=False,
                errors=[str(e)]
            )

    def list_powers(self) -> List[Dict[str, Any]]:
        return [
            {
                "power_id": "system.health_probe",
                "name": "Host Health Probe",
                "description": "Observes live CPU, RAM, and Disk telemetry",
                "triggers": ["system health", "cpu usage", "ram telemetry"],
                "tier": 0,
                "approval_required": False,
                "danger_level": "none"
            },
            {
                "power_id": "system.disk_diagnostics",
                "name": "Disk Diagnostics",
                "description": "Inspects storage mounts and partition free space",
                "triggers": ["disk space", "storage status"],
                "tier": 0,
                "approval_required": False,
                "danger_level": "none"
            },
            {
                "power_id": "system.clear_temp_cache",
                "name": "Purge Temporary Cache",
                "description": "Cleans ephemeral test and scratch artifacts",
                "triggers": ["clean temp", "purge scratch", "clear cache"],
                "tier": 2,
                "approval_required": True,
                "danger_level": "medium"
            }
        ]

    def _execute_power_impl(self, power_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if power_id == "system.health_probe":
            return {
                "cpu_percent": psutil.cpu_percent(interval=None),
                "ram_percent": psutil.virtual_memory().percent,
                "boot_time": psutil.boot_time(),
                "timestamp": time.time()
            }
        elif power_id == "system.disk_diagnostics":
            partitions = []
            for p in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(p.mountpoint)
                    partitions.append({
                        "device": p.device,
                        "mountpoint": p.mountpoint,
                        "total_gb": round(usage.total / (1024 ** 3), 2),
                        "used_gb": round(usage.used / (1024 ** 3), 2),
                        "free_gb": round(usage.free / (1024 ** 3), 2),
                        "percent": usage.percent
                    })
                except Exception:
                    pass
            return {"partitions": partitions}
        elif power_id == "system.clear_temp_cache":
            # Tier 2 action - simulated safe cleanup
            target_dir = params.get("target_dir", "scratch")
            return {
                "action": "purged_scratch_cache",
                "target": target_dir,
                "cleared_files": 0,
                "bytes_reclaimed": 0,
                "status": "COMPLETED"
            }
        else:
            raise ValueError(f"Unsupported power '{power_id}' on {self.display_name}")
