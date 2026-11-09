"""
JARVIS IT Administration Powers (PWR-100 to PWR-126)
Telemetry, resource diagnostics, container inspection, process management, and certificate tracking.
"""

import psutil
import time
import socket
import ssl
import shutil
import datetime
import subprocess
from typing import Dict, Any, List, Optional
from jarvis.config import settings

class ITAdminPowers:
    @staticmethod
    def system_health_report() -> Dict[str, Any]:
        """PWR-100: Generates comprehensive host performance telemetry."""
        cpu_pct = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage(settings.disk_mount_path)

        boot_time = datetime.datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S")

        # Top 5 processes by memory
        top_processes = []
        for p in sorted(psutil.process_iter(['pid', 'name', 'memory_percent', 'cpu_percent']),
                        key=lambda x: x.info['memory_percent'] or 0, reverse=True)[:5]:
            top_processes.append(p.info)

        return {
            "power_id": "PWR-100",
            "power_name": "System health report",
            "status": "healthy" if (cpu_pct < 90 and ram.percent < 90) else "warning",
            "cpu": {
                "percent": cpu_pct,
                "cores_logical": psutil.cpu_count(logical=True),
                "cores_physical": psutil.cpu_count(logical=False)
            },
            "memory": {
                "total_gb": round(ram.total / (1024**3), 2),
                "used_gb": round(ram.used / (1024**3), 2),
                "available_gb": round(ram.available / (1024**3), 2),
                "percent": ram.percent
            },
            "disk": {
                "total_gb": round(disk.total / (1024**3), 2),
                "used_gb": round(disk.used / (1024**3), 2),
                "free_gb": round(disk.free / (1024**3), 2),
                "percent": disk.percent
            },
            "system": {
                "boot_time": boot_time,
                "timestamp": time.time()
            },
            "top_processes": top_processes
        }

    @staticmethod
    def cpu_ram_disk_monitoring() -> Dict[str, Any]:
        """PWR-101: Fine-grained CPU, RAM, and Disk telemetry."""
        cpu_times = psutil.cpu_times_percent(interval=0.1)
        ram = psutil.virtual_memory()
        swap = psutil.swap_memory()
        disk = psutil.disk_usage(settings.disk_mount_path)
        io_counters = psutil.disk_io_counters()

        return {
            "power_id": "PWR-101",
            "power_name": "CPU/RAM/disk monitoring",
            "timestamp": time.time(),
            "cpu_user": getattr(cpu_times, 'user', 0.0),
            "cpu_system": getattr(cpu_times, 'system', 0.0),
            "cpu_idle": getattr(cpu_times, 'idle', 0.0),
            "ram_used_percent": ram.percent,
            "swap_used_percent": swap.percent,
            "disk_used_percent": disk.percent,
            "read_bytes": io_counters.read_bytes if io_counters else 0,
            "write_bytes": io_counters.write_bytes if io_counters else 0
        }

    @staticmethod
    def disk_space_analysis(path: str = settings.disk_mount_path) -> Dict[str, Any]:
        """PWR-103: Disk space forecasting and directory usage breakdown."""
        usage = shutil.disk_usage(path)
        free_pct = round((usage.free / usage.total) * 100, 2)
        burn_rate_gb_day = 0.5  # Estimated baseline burn rate
        days_until_exhaustion = round((usage.free / (1024**3)) / max(burn_rate_gb_day, 0.01), 1)

        return {
            "power_id": "PWR-103",
            "power_name": "Disk-space forecast",
            "path": path,
            "total_gb": round(usage.total / (1024**3), 2),
            "used_gb": round(usage.used / (1024**3), 2),
            "free_gb": round(usage.free / (1024**3), 2),
            "free_percent": free_pct,
            "estimated_days_remaining": days_until_exhaustion,
            "status": "critical" if free_pct < 10 else ("warning" if free_pct < 20 else "healthy")
        }

    @staticmethod
    def process_analysis(limit: int = 10) -> Dict[str, Any]:
        """PWR-105: Process analysis and CPU/RAM hog detection."""
        processes = []
        for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status']):
            try:
                processes.append(p.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        top_by_cpu = sorted(processes, key=lambda x: x.get('cpu_percent') or 0, reverse=True)[:limit]
        top_by_ram = sorted(processes, key=lambda x: x.get('memory_percent') or 0, reverse=True)[:limit]

        return {
            "power_id": "PWR-105",
            "power_name": "Process analysis",
            "total_running_processes": len(processes),
            "top_cpu_consumers": top_by_cpu,
            "top_ram_consumers": top_by_ram
        }

    @staticmethod
    def safe_process_termination(pid: int, force: bool = False) -> Dict[str, Any]:
        """PWR-106: Safely terminates a runaway process with safety verification."""
        try:
            p = psutil.Process(pid)
            name = p.name()
            # Protect system and self
            if pid <= 4 or "system" in name.lower() or pid == psutil.Process().pid:
                return {
                    "power_id": "PWR-106",
                    "success": False,
                    "error": f"Cannot terminate protected critical process {name} (PID: {pid})"
                }
            if force:
                p.kill()
            else:
                p.terminate()
            return {
                "power_id": "PWR-106",
                "success": True,
                "pid": pid,
                "name": name,
                "action": "SIGKILL" if force else "SIGTERM"
            }
        except psutil.NoSuchProcess:
            return {"power_id": "PWR-106", "success": False, "error": f"Process {pid} does not exist"}
        except Exception as e:
            return {"power_id": "PWR-106", "success": False, "error": str(e)}

    @staticmethod
    def docker_container_monitoring() -> Dict[str, Any]:
        """PWR-117: Docker container monitoring and health verification."""
        try:
            # Check docker CLI or socket
            res = subprocess.run(["docker", "ps", "--format", "{{.ID}}|{{.Image}}|{{.Status}}|{{.Names}}"],
                                 capture_output=True, text=True, timeout=3.0)
            if res.returncode != 0:
                return {
                    "power_id": "PWR-117",
                    "power_name": "Docker container monitoring",
                    "docker_available": False,
                    "containers": [],
                    "message": "Docker daemon unavailable or not running"
                }

            containers = []
            for line in res.stdout.strip().splitlines():
                if line:
                    parts = line.split("|")
                    if len(parts) >= 4:
                        containers.append({
                            "id": parts[0],
                            "image": parts[1],
                            "status": parts[2],
                            "name": parts[3]
                        })

            return {
                "power_id": "PWR-117",
                "power_name": "Docker container monitoring",
                "docker_available": True,
                "total_containers": len(containers),
                "containers": containers
            }
        except Exception as e:
            return {
                "power_id": "PWR-117",
                "power_name": "Docker container monitoring",
                "docker_available": False,
                "containers": [],
                "message": f"Docker probe failed: {str(e)}"
            }

    @staticmethod
    def server_uptime_monitoring() -> Dict[str, Any]:
        """PWR-120: Server uptime and host availability monitoring."""
        boot_ts = psutil.boot_time()
        uptime_seconds = int(time.time() - boot_ts)
        days = uptime_seconds // 86400
        hours = (uptime_seconds % 86400) // 3600
        minutes = (uptime_seconds % 3600) // 60

        return {
            "power_id": "PWR-120",
            "power_name": "Server uptime monitoring",
            "uptime_seconds": uptime_seconds,
            "uptime_human": f"{days}d {hours}h {minutes}m",
            "boot_timestamp": datetime.datetime.fromtimestamp(boot_ts).isoformat(),
            "status": "online"
        }

    @staticmethod
    def check_ssl_certificate(hostname: str, port: int = 443) -> Dict[str, Any]:
        """PWR-121: Checks SSL/TLS certificate validity and expiration for a domain."""
        context = ssl.create_default_context()
        try:
            with socket.create_connection((hostname, port), timeout=5.0) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    not_after_str = cert['notAfter']
                    expiry = datetime.datetime.strptime(not_after_str, '%b %d %H:%M:%S %Y %Z')
                    days_left = (expiry - datetime.datetime.utcnow()).days

                    return {
                        "power_id": "PWR-121",
                        "power_name": "SSL certificate monitoring",
                        "hostname": hostname,
                        "status": "valid" if days_left > 14 else "expiring_soon",
                        "expires_at": expiry.strftime("%Y-%m-%d"),
                        "days_remaining": days_left,
                        "issuer": dict(x[0] for x in cert.get('issuer', []))
                    }
        except Exception as e:
            return {
                "power_id": "PWR-121",
                "power_name": "SSL certificate monitoring",
                "hostname": hostname,
                "status": "error",
                "message": f"Failed to verify SSL certificate: {str(e)}"
            }

it_admin_powers = ITAdminPowers()
