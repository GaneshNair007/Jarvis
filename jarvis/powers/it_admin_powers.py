"""
JARVIS IT Administration Powers (PWR-100 to PWR-126)
Telemetry, resource diagnostics, container inspection, and certificate tracking.
"""

import psutil
import time
import socket
import ssl
import datetime
from typing import Dict, Any, List

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
    def check_ssl_certificate(hostname: str, port: int = 443) -> Dict[str, Any]:
        """PWR-115: Checks SSL/TLS certificate validity and expiration for a domain."""
        context = ssl.create_default_context()
        try:
            with socket.create_connection((hostname, port), timeout=5.0) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    not_after_str = cert['notAfter']
                    # e.g., 'May 15 12:00:00 2027 GMT'
                    expiry = datetime.datetime.strptime(not_after_str, '%b %d %H:%M:%S %Y %Z')
                    days_left = (expiry - datetime.datetime.utcnow()).days

                    return {
                        "power_id": "PWR-115",
                        "hostname": hostname,
                        "status": "valid" if days_left > 14 else "expiring_soon",
                        "expires_at": expiry.strftime("%Y-%m-%d"),
                        "days_remaining": days_left,
                        "issuer": dict(x[0] for x in cert.get('issuer', []))
                    }
        except Exception as e:
            return {
                "power_id": "PWR-115",
                "hostname": hostname,
                "status": "error",
                "message": f"Failed to verify SSL certificate: {str(e)}"
            }

it_admin_powers = ITAdminPowers()
