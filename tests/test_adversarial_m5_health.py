"""
Adversarial Stress Test Suite for Milestone 5: System Health Telemetry, Host Status & Lifecycle Safety.

This suite challenges:
1. boot_time invariants under diverse mock payloads, missing keys, and psutil exceptions.
2. Disk saturation boundary conditions (94.9% vs 95.0%, 89.9% vs 90.0%, 1.99GB vs 2.01GB, 9.99GB vs 10.01GB).
3. Subsystem priority resolution (critical wins over warning).
4. Logger exception safety during scheduler startup, shutdown, and host metrics gathering.
"""

import datetime
import re
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

import psutil
from jarvis.api.server import app, startup_event, shutdown_event
from jarvis.core.capability_guard import capability_guard, CapabilityStatus
from jarvis.powers.it_admin_powers import it_admin_powers
from jarvis.core.scheduler import proactive_scheduler

client = TestClient(app)

ISO_TIMESTAMP_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}")


@pytest.fixture(autouse=True)
def ensure_deterministic_capability_status(monkeypatch):
    """Ensure capability_guard reports connected internet so baseline is healthy."""
    monkeypatch.setattr(capability_guard, "check_internet", lambda use_cache=True: CapabilityStatus.CONNECTED)
    monkeypatch.setattr(capability_guard, "check_ollama", lambda use_cache=True: CapabilityStatus.DISCONNECTED)


# ==============================================================================
# SECTION 1: Adversarial Boot Time Invariance Tests
# ==============================================================================

class TestBootTimeInvariance:
    """
    Challenge boot_time: Probe /api/v1/system/health under diverse configurations.
    HEALTH_SCHEMA.md and Worker M5 Handoff guarantee boot_time is NEVER null
    and conforms to ISO/timestamp string format.
    """

    def test_boot_time_present_in_root_key_only(self, monkeypatch):
        """Verify extraction when boot_time is provided solely at host_metrics root."""
        mock_metrics = {
            "status": "healthy",
            "boot_time": "2026-11-03 08:15:00",
            "cpu": {"percent": 12.0},
            "memory": {"percent": 45.0},
            "disk": {"percent": 60.0},
        }
        monkeypatch.setattr(it_admin_powers, "system_health_report", lambda: mock_metrics)

        response = client.get("/api/v1/system/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("boot_time") is not None, "boot_time must not be null when provided at root"
        assert data.get("boot_time") == "2026-11-03 08:15:00"
        assert ISO_TIMESTAMP_REGEX.match(data["boot_time"]), "boot_time must conform to ISO/timestamp format"

    def test_boot_time_present_in_nested_system_key_only(self, monkeypatch):
        """Verify backward-compatible extraction when boot_time is only nested under host_metrics['system']."""
        mock_metrics = {
            "status": "healthy",
            "system": {"boot_time": "2026-11-03 08:15:00", "timestamp": 1730616000.0},
            "cpu": {"percent": 12.0},
            "memory": {"percent": 45.0},
            "disk": {"percent": 60.0},
        }
        monkeypatch.setattr(it_admin_powers, "system_health_report", lambda: mock_metrics)

        response = client.get("/api/v1/system/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("boot_time") is not None, "boot_time must not be null when nested under 'system'"
        assert data.get("boot_time") == "2026-11-03 08:15:00"
        assert ISO_TIMESTAMP_REGEX.match(data["boot_time"]), "boot_time must conform to ISO/timestamp format"

    def test_boot_time_present_in_both_root_and_nested(self, monkeypatch):
        """Verify extraction when both root and nested system keys are populated."""
        mock_metrics = {
            "status": "healthy",
            "boot_time": "2026-11-03 08:15:00",
            "system": {"boot_time": "2026-11-03 08:15:00", "timestamp": 1730616000.0},
            "cpu": {"percent": 12.0},
            "memory": {"percent": 45.0},
            "disk": {"percent": 60.0},
        }
        monkeypatch.setattr(it_admin_powers, "system_health_report", lambda: mock_metrics)

        response = client.get("/api/v1/system/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("boot_time") == "2026-11-03 08:15:00"
        assert ISO_TIMESTAMP_REGEX.match(data["boot_time"])

    def test_boot_time_never_null_when_system_key_missing_and_no_root_key(self, monkeypatch):
        """
        Adversarial Probe: host_metrics lacks both root 'boot_time' and 'system' dict.
        Schema invariant: boot_time must NEVER be null in /api/v1/system/health response.
        """
        mock_metrics = {
            "status": "healthy",
            "cpu": {"percent": 15.0},
            "memory": {"percent": 50.0},
            "disk": {"percent": 55.0},
        }
        monkeypatch.setattr(it_admin_powers, "system_health_report", lambda: mock_metrics)

        response = client.get("/api/v1/system/health")
        assert response.status_code == 200
        data = response.json()
        assert "boot_time" in data, "boot_time field must be present in health payload"
        assert data.get("boot_time") is not None, "boot_time must NEVER be null when host_metrics lacks boot_time keys"
        assert isinstance(data["boot_time"], str), "boot_time must be a string"
        assert ISO_TIMESTAMP_REGEX.match(data["boot_time"]), "boot_time must conform to timestamp format"

    def test_boot_time_never_null_when_psutil_boot_time_raises_exception(self, monkeypatch):
        """
        Adversarial Probe: psutil.boot_time() raises OSError (kernel denial/WMI failure).
        Invariant: /api/v1/system/health must gracefully fall back; boot_time must NEVER be null.
        """
        def faulty_boot_time():
            raise OSError("Access denied reading kernel boot time")

        monkeypatch.setattr(psutil, "boot_time", faulty_boot_time)

        response = client.get("/api/v1/system/health")
        assert response.status_code == 200
        data = response.json()
        assert "boot_time" in data, "boot_time key must be present in response"
        assert data.get("boot_time") is not None, "boot_time must NEVER be null even if psutil.boot_time() throws OSError"
        assert isinstance(data["boot_time"], str), "boot_time must be a string timestamp"
        assert ISO_TIMESTAMP_REGEX.match(data["boot_time"]), "boot_time must conform to timestamp format"

    def test_boot_time_never_null_when_host_metrics_raises_exception(self, monkeypatch):
        """
        Adversarial Probe: it_admin_powers.system_health_report() throws unhandled RuntimeError.
        Invariant: /api/v1/system/health must catch exception, return HTTP 200, and boot_time must NOT be null.
        """
        def crashing_report():
            raise RuntimeError("Fatal WMI crash in telemetry collector")

        monkeypatch.setattr(it_admin_powers, "system_health_report", crashing_report)

        response = client.get("/api/v1/system/health")
        assert response.status_code == 200
        data = response.json()
        assert "boot_time" in data, "boot_time key must be present in response"
        assert data.get("boot_time") is not None, "boot_time must NEVER be null when telemetry gathering fails"
        assert isinstance(data["boot_time"], str), "boot_time must be a string"
        assert ISO_TIMESTAMP_REGEX.match(data["boot_time"]), "boot_time must conform to timestamp format"


# ==============================================================================
# SECTION 2: Adversarial Disk Saturation & Boundary Condition Tests
# ==============================================================================

class TestDiskSaturationBoundaries:
    """
    Challenge Disk Saturation Boundary Conditions:
    - Exactly at boundary: 94.9% vs 95.0%; 89.9% vs 90.0%.
    - Low free space boundary: 1.99 GB vs 2.01 GB; 9.99 GB vs 10.01 GB.
    - Subsystem Priority: Critical priority must strictly supersede Warning.
    """

    def _mock_host_hardware(self, monkeypatch, disk_pct: float, free_gb: float, ram_pct: float = 20.0, cpu_pct: float = 20.0):
        total_bytes = 100 * (1024**3)
        free_bytes = int(free_gb * (1024**3))
        used_bytes = total_bytes - free_bytes

        mock_disk = MagicMock(total=total_bytes, used=used_bytes, free=free_bytes, percent=disk_pct)
        mock_ram = MagicMock(total=16 * (1024**3), used=4 * (1024**3), available=12 * (1024**3), percent=ram_pct)

        monkeypatch.setattr(psutil, "disk_usage", lambda path: mock_disk)
        monkeypatch.setattr(psutil, "virtual_memory", lambda: mock_ram)
        monkeypatch.setattr(psutil, "cpu_percent", lambda interval=None: cpu_pct)

    # --- Boundary: 94.9% vs 95.0% disk fullness ---

    def test_boundary_disk_fullness_at_94_9_percent(self, monkeypatch):
        """94.9% disk fullness (with ample free space 15GB) must trigger warning, not critical."""
        self._mock_host_hardware(monkeypatch, disk_pct=94.9, free_gb=15.0)

        report = it_admin_powers.system_health_report()
        assert report["status"] == "warning", f"Expected warning at 94.9% disk, got {report['status']}"

        response = client.get("/api/v1/system/health")
        assert response.status_code == 200
        data = response.json()
        assert data["host_status"] == "warning"
        assert data["status"] == "degraded"

    def test_boundary_disk_fullness_at_95_0_percent(self, monkeypatch):
        """95.0% disk fullness must immediately trigger critical status."""
        self._mock_host_hardware(monkeypatch, disk_pct=95.0, free_gb=15.0)

        report = it_admin_powers.system_health_report()
        assert report["status"] == "critical", f"Expected critical at 95.0% disk, got {report['status']}"

        response = client.get("/api/v1/system/health")
        assert response.status_code == 200
        data = response.json()
        assert data["host_status"] == "critical"
        assert data["status"] == "critical"

    # --- Boundary: 89.9% vs 90.0% disk fullness ---

    def test_boundary_disk_fullness_at_89_9_percent(self, monkeypatch):
        """89.9% disk fullness (with ample free space 15GB) must remain healthy."""
        self._mock_host_hardware(monkeypatch, disk_pct=89.9, free_gb=15.0)

        report = it_admin_powers.system_health_report()
        assert report["status"] == "healthy", f"Expected healthy at 89.9% disk, got {report['status']}"

        response = client.get("/api/v1/system/health")
        assert response.status_code == 200
        data = response.json()
        assert data["host_status"] == "healthy"
        assert data["status"] == "healthy"

    def test_boundary_disk_fullness_at_90_0_percent(self, monkeypatch):
        """90.0% disk fullness must trigger warning status."""
        self._mock_host_hardware(monkeypatch, disk_pct=90.0, free_gb=15.0)

        report = it_admin_powers.system_health_report()
        assert report["status"] == "warning", f"Expected warning at 90.0% disk, got {report['status']}"

        response = client.get("/api/v1/system/health")
        assert response.status_code == 200
        data = response.json()
        assert data["host_status"] == "warning"
        assert data["status"] == "degraded"

    # --- Boundary: Low free space 1.99 GB vs 2.01 GB ---

    def test_boundary_free_space_at_1_99_gb(self, monkeypatch):
        """1.99 GB free space (< 2.0 GB) must trigger critical status regardless of low usage percentage."""
        self._mock_host_hardware(monkeypatch, disk_pct=50.0, free_gb=1.99)

        report = it_admin_powers.system_health_report()
        assert report["status"] == "critical", f"Expected critical at 1.99 GB free, got {report['status']}"

        response = client.get("/api/v1/system/health")
        assert response.status_code == 200
        data = response.json()
        assert data["host_status"] == "critical"
        assert data["status"] == "critical"

    def test_boundary_free_space_at_2_01_gb(self, monkeypatch):
        """2.01 GB free space (>= 2.0 GB and < 10.0 GB) must trigger warning status, not critical."""
        self._mock_host_hardware(monkeypatch, disk_pct=50.0, free_gb=2.01)

        report = it_admin_powers.system_health_report()
        assert report["status"] == "warning", f"Expected warning at 2.01 GB free, got {report['status']}"

        response = client.get("/api/v1/system/health")
        assert response.status_code == 200
        data = response.json()
        assert data["host_status"] == "warning"
        assert data["status"] == "degraded"

    # --- Boundary: Low free space 9.99 GB vs 10.01 GB ---

    def test_boundary_free_space_at_9_99_gb(self, monkeypatch):
        """9.99 GB free space (< 10.0 GB) must trigger warning status."""
        self._mock_host_hardware(monkeypatch, disk_pct=50.0, free_gb=9.99)

        report = it_admin_powers.system_health_report()
        assert report["status"] == "warning", f"Expected warning at 9.99 GB free, got {report['status']}"

        response = client.get("/api/v1/system/health")
        assert response.status_code == 200
        data = response.json()
        assert data["host_status"] == "warning"
        assert data["status"] == "degraded"

    def test_boundary_free_space_at_10_01_gb(self, monkeypatch):
        """10.01 GB free space (>= 10.0 GB and low percentage) must remain healthy."""
        self._mock_host_hardware(monkeypatch, disk_pct=50.0, free_gb=10.01)

        report = it_admin_powers.system_health_report()
        assert report["status"] == "healthy", f"Expected healthy at 10.01 GB free, got {report['status']}"

        response = client.get("/api/v1/system/health")
        assert response.status_code == 200
        data = response.json()
        assert data["host_status"] == "healthy"
        assert data["status"] == "healthy"

    # --- Priority Resolution: Critical must supersede Warning ---

    def test_multiple_subsystems_cpu_warning_disk_critical(self, monkeypatch):
        """Subsystem Priority: CPU at 91.0% (warning) + Disk at 96.0% (critical) -> CRITICAL wins."""
        self._mock_host_hardware(monkeypatch, disk_pct=96.0, free_gb=15.0, cpu_pct=91.0)

        report = it_admin_powers.system_health_report()
        assert report["status"] == "critical"

        response = client.get("/api/v1/system/health")
        assert response.status_code == 200
        data = response.json()
        assert data["host_status"] == "critical"
        assert data["status"] == "critical"

    def test_multiple_subsystems_cpu_critical_disk_warning(self, monkeypatch):
        """Subsystem Priority: CPU at 96.0% (critical) + Disk at 91.0% (warning) -> CRITICAL wins."""
        self._mock_host_hardware(monkeypatch, disk_pct=91.0, free_gb=15.0, cpu_pct=96.0)

        report = it_admin_powers.system_health_report()
        assert report["status"] == "critical"

        response = client.get("/api/v1/system/health")
        assert response.status_code == 200
        data = response.json()
        assert data["host_status"] == "critical"
        assert data["status"] == "critical"

    def test_multiple_subsystems_ram_warning_free_space_critical(self, monkeypatch):
        """Subsystem Priority: RAM at 91.0% (warning) + Disk Free at 1.5 GB (critical) -> CRITICAL wins."""
        self._mock_host_hardware(monkeypatch, disk_pct=60.0, free_gb=1.5, ram_pct=91.0)

        report = it_admin_powers.system_health_report()
        assert report["status"] == "critical"

        response = client.get("/api/v1/system/health")
        assert response.status_code == 200
        data = response.json()
        assert data["host_status"] == "critical"
        assert data["status"] == "critical"

    def test_multiple_subsystems_all_warning_no_false_critical(self, monkeypatch):
        """When multiple subsystems are at warning levels, status remains warning, not falsely promoted to critical."""
        self._mock_host_hardware(monkeypatch, disk_pct=91.0, free_gb=8.0, ram_pct=91.0, cpu_pct=91.0)

        report = it_admin_powers.system_health_report()
        assert report["status"] == "warning"

        response = client.get("/api/v1/system/health")
        assert response.status_code == 200
        data = response.json()
        assert data["host_status"] == "warning"
        assert data["status"] == "degraded"


# ==============================================================================
# SECTION 3: Adversarial Logger Exception Safety Tests
# ==============================================================================

class TestLoggerExceptionSafety:
    """
    Challenge Logger Exception Safety:
    Inject exceptions into proactive scheduler startup, shutdown, and host metrics gathering.
    Verify zero unhandled NameError: name 'logger' is not defined crashes.
    """

    @pytest.mark.asyncio
    async def test_scheduler_startup_exception_safety(self, monkeypatch):
        """Verify startup_event handles scheduler startup exceptions without NameError: logger."""
        def faulty_start():
            raise RuntimeError("Scheduler startup failure simulation")

        monkeypatch.setattr(proactive_scheduler, "start", faulty_start)

        try:
            await startup_event()
        except NameError as ne:
            pytest.fail(f"Unhandled NameError encountered in startup_event: {ne}")
        except Exception as e:
            pytest.fail(f"startup_event allowed unhandled exception to escape: {e}")

    @pytest.mark.asyncio
    async def test_scheduler_shutdown_exception_safety(self, monkeypatch):
        """Verify shutdown_event handles scheduler shutdown exceptions without NameError: logger."""
        def faulty_stop():
            raise RuntimeError("Scheduler shutdown failure simulation")

        monkeypatch.setattr(proactive_scheduler, "stop", faulty_stop)

        try:
            await shutdown_event()
        except NameError as ne:
            pytest.fail(f"Unhandled NameError encountered in shutdown_event: {ne}")
        except Exception as e:
            pytest.fail(f"shutdown_event allowed unhandled exception to escape: {e}")

    def test_host_metrics_telemetry_gathering_exception_safety(self, monkeypatch):
        """Verify /api/v1/system/health handles telemetry exceptions without NameError: logger."""
        def faulty_report():
            raise RuntimeError("Telemetry collector fatal crash")

        monkeypatch.setattr(it_admin_powers, "system_health_report", faulty_report)

        try:
            response = client.get("/api/v1/system/health")
            assert response.status_code == 200
        except NameError as ne:
            pytest.fail(f"Unhandled NameError encountered in system_health: {ne}")

    def test_host_metrics_psutil_permission_error_logger_safety(self, monkeypatch):
        """Verify /api/v1/system/health handles psutil.AccessDenied without crashing."""
        def denied_report():
            raise psutil.AccessDenied(pid=0, name="System")

        monkeypatch.setattr(it_admin_powers, "system_health_report", denied_report)

        try:
            response = client.get("/api/v1/system/health")
            assert response.status_code == 200
        except NameError as ne:
            pytest.fail(f"Unhandled NameError encountered with psutil.AccessDenied: {ne}")
