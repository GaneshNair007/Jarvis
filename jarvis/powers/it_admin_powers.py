"""
JARVIS IT Administration Powers (PWR-100 to PWR-126)
Telemetry, resource diagnostics, container inspection, and certificate tracking.
"""

from __future__ import annotations

import glob
import os
import psutil
import subprocess
import tempfile
import time
import socket
import ssl
import datetime
import winreg
from typing import Any, Dict, List, Optional

from jarvis.config import settings


class ITAdminPowers:
    @staticmethod
    def system_health_report() -> Dict[str, Any]:
        """PWR-100: Generates comprehensive host performance telemetry."""
        cpu_pct = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage(settings.disk_mount_path)

        boot_time = datetime.datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S")

        # Fast non-blocking top processes (sampled only when requested)
        top_processes = []

        return {
            "power_id": "PWR-100",
            "status": "healthy" if (cpu_pct < 90 and ram.percent < 90) else "warning",
            "cpu": {
                "percent": cpu_pct,
                "cores_logical": psutil.cpu_count(logical=True),
                "cores_physical": psutil.cpu_count(logical=False),
            },
            "memory": {
                "total_gb": round(ram.total / (1024**3), 2),
                "used_gb": round(ram.used / (1024**3), 2),
                "available_gb": round(ram.available / (1024**3), 2),
                "percent": ram.percent,
            },
            "disk": {
                "total_gb": round(disk.total / (1024**3), 2),
                "used_gb": round(disk.used / (1024**3), 2),
                "free_gb": round(disk.free / (1024**3), 2),
                "percent": disk.percent,
            },
            "system": {"boot_time": boot_time, "timestamp": time.time()},
            "top_processes": top_processes,
        }

    @staticmethod
    def check_ssl_certificate(hostname: str, port: int = 443) -> Dict[str, Any]:
        """PWR-115: Checks SSL/TLS certificate validity and expiration for a domain."""
        context = ssl.create_default_context()
        try:
            with socket.create_connection((hostname, port), timeout=5.0) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    not_after_str = cert["notAfter"]
                    # e.g., 'May 15 12:00:00 2027 GMT'
                    expiry = datetime.datetime.strptime(not_after_str, "%b %d %H:%M:%S %Y %Z")
                    days_left = (expiry - datetime.datetime.utcnow()).days

                    return {
                        "power_id": "PWR-115",
                        "hostname": hostname,
                        "status": "valid" if days_left > 14 else "expiring_soon",
                        "expires_at": expiry.strftime("%Y-%m-%d"),
                        "days_remaining": days_left,
                        "issuer": dict(x[0] for x in cert.get("issuer", [])),
                    }
        except Exception as e:
            return {
                "power_id": "PWR-115",
                "hostname": hostname,
                "status": "error",
                "message": f"Failed to verify SSL certificate: {str(e)}",
            }

    # ------------------------------------------------------------------
    # Docker Management (PWR-100 to PWR-102)
    # ------------------------------------------------------------------

    @staticmethod
    def docker_status() -> Dict[str, Any]:
        """PWR-100: Lists Docker containers with status, CPU, and memory usage."""
        try:
            ps_result = subprocess.run(
                ["docker", "ps", "-a", "--format", "{{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Image}}"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if ps_result.returncode != 0:
                return {
                    "power_id": "PWR-100",
                    "status": "error",
                    "message": ps_result.stderr.strip() or "Docker not available",
                }

            containers: List[Dict[str, str]] = []
            for line in ps_result.stdout.strip().splitlines():
                parts = line.split("\t")
                if len(parts) >= 4:
                    containers.append(
                        {
                            "id": parts[0],
                            "name": parts[1],
                            "status": parts[2],
                            "image": parts[3],
                        }
                    )

            # Gather stats for running containers
            stats_result = subprocess.run(
                ["docker", "stats", "--no-stream", "--format", "{{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            stats_map: Dict[str, Dict[str, str]] = {}
            if stats_result.returncode == 0:
                for line in stats_result.stdout.strip().splitlines():
                    parts = line.split("\t")
                    if len(parts) >= 3:
                        stats_map[parts[0]] = {"cpu": parts[1], "memory": parts[2]}

            for c in containers:
                s = stats_map.get(c["id"], stats_map.get(c["name"], {}))
                c["cpu_percent"] = s.get("cpu", "N/A")
                c["memory_usage"] = s.get("memory", "N/A")

            return {
                "power_id": "PWR-100",
                "status": "success",
                "container_count": len(containers),
                "containers": containers,
            }
        except FileNotFoundError:
            return {"power_id": "PWR-100", "status": "error", "message": "Docker CLI not found on PATH"}
        except Exception as e:
            return {"power_id": "PWR-100", "status": "error", "message": str(e)}

    @staticmethod
    def docker_logs(container: str, lines: int = 50) -> Dict[str, Any]:
        """PWR-101: Tail container logs."""
        try:
            res = subprocess.run(
                ["docker", "logs", "--tail", str(lines), container],
                capture_output=True,
                text=True,
                timeout=15,
            )
            output = res.stdout or res.stderr
            return {
                "power_id": "PWR-101",
                "status": "success",
                "container": container,
                "lines_requested": lines,
                "logs": output[-5000:],  # cap to 5 KB
            }
        except FileNotFoundError:
            return {"power_id": "PWR-101", "status": "error", "message": "Docker CLI not found on PATH"}
        except Exception as e:
            return {"power_id": "PWR-101", "status": "error", "message": str(e)}

    @staticmethod
    def docker_restart(container: str) -> Dict[str, Any]:
        """PWR-102: Restart a Docker container. Requires user approval."""
        try:
            res = subprocess.run(
                ["docker", "restart", container],
                capture_output=True,
                text=True,
                timeout=30,
            )
            return {
                "power_id": "PWR-102",
                "status": "success" if res.returncode == 0 else "error",
                "container": container,
                "output": (res.stdout or res.stderr).strip(),
                "approval_required": True,
            }
        except FileNotFoundError:
            return {
                "power_id": "PWR-102",
                "status": "error",
                "message": "Docker CLI not found on PATH",
                "approval_required": True,
            }
        except Exception as e:
            return {"power_id": "PWR-102", "status": "error", "message": str(e), "approval_required": True}

    # ------------------------------------------------------------------
    # Windows Service Management (PWR-105 to PWR-106)
    # ------------------------------------------------------------------

    @staticmethod
    def service_status(service_name: Optional[str] = None) -> Dict[str, Any]:
        """PWR-105: Query Windows service status via sc query."""
        try:
            cmd = ["sc", "query"]
            if service_name:
                cmd.append(service_name)
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if res.returncode != 0:
                return {"power_id": "PWR-105", "status": "error", "message": res.stderr.strip() or res.stdout.strip()}

            services: List[Dict[str, str]] = []
            current: Dict[str, str] = {}
            for line in res.stdout.splitlines():
                line = line.strip()
                if line.startswith("SERVICE_NAME:"):
                    if current:
                        services.append(current)
                    current = {"service_name": line.split(":", 1)[1].strip()}
                elif line.startswith("DISPLAY_NAME:"):
                    current["display_name"] = line.split(":", 1)[1].strip()
                elif line.startswith("STATE"):
                    # e.g. STATE              : 4  RUNNING
                    state_part = line.split(":", 1)[1].strip()
                    current["state"] = state_part
            if current:
                services.append(current)

            return {
                "power_id": "PWR-105",
                "status": "success",
                "service_count": len(services),
                "services": services[:100],  # cap output
            }
        except Exception as e:
            return {"power_id": "PWR-105", "status": "error", "message": str(e)}

    @staticmethod
    def service_restart(service_name: str) -> Dict[str, Any]:
        """PWR-106: Restart a Windows service. Requires user approval."""
        try:
            stop = subprocess.run(
                ["sc", "stop", service_name],
                capture_output=True,
                text=True,
                timeout=30,
            )
            time.sleep(2)
            start = subprocess.run(
                ["sc", "start", service_name],
                capture_output=True,
                text=True,
                timeout=30,
            )
            return {
                "power_id": "PWR-106",
                "status": "success" if start.returncode == 0 else "error",
                "service_name": service_name,
                "stop_output": stop.stdout.strip(),
                "start_output": start.stdout.strip(),
                "approval_required": True,
            }
        except Exception as e:
            return {"power_id": "PWR-106", "status": "error", "message": str(e), "approval_required": True}

    # ------------------------------------------------------------------
    # Disk Management (PWR-110, PWR-112)
    # ------------------------------------------------------------------

    @staticmethod
    def disk_usage() -> Dict[str, Any]:
        """PWR-110: Disk usage per drive using psutil."""
        try:
            partitions = psutil.disk_partitions(all=False)
            drives: List[Dict[str, Any]] = []
            for p in partitions:
                try:
                    usage = psutil.disk_usage(p.mountpoint)
                    drives.append(
                        {
                            "device": p.device,
                            "mountpoint": p.mountpoint,
                            "fstype": p.fstype,
                            "total_gb": round(usage.total / (1024**3), 2),
                            "used_gb": round(usage.used / (1024**3), 2),
                            "free_gb": round(usage.free / (1024**3), 2),
                            "percent": usage.percent,
                        }
                    )
                except PermissionError:
                    drives.append({"device": p.device, "mountpoint": p.mountpoint, "error": "Permission denied"})
            return {
                "power_id": "PWR-110",
                "status": "success",
                "drive_count": len(drives),
                "drives": drives,
            }
        except Exception as e:
            return {"power_id": "PWR-110", "status": "error", "message": str(e)}

    @staticmethod
    def disk_cleanup_preview() -> Dict[str, Any]:
        """PWR-112: Preview temp/cache files that could be cleaned."""
        try:
            targets = [
                tempfile.gettempdir(),
                os.path.join(os.environ.get("LOCALAPPDATA", ""), "Temp"),
                os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Temp"),
            ]
            cleanup_items: List[Dict[str, Any]] = []
            total_size = 0

            for target_dir in targets:
                if not os.path.isdir(target_dir):
                    continue
                dir_size = 0
                file_count = 0
                try:
                    for root, dirs, files in os.walk(target_dir):
                        for f in files:
                            try:
                                fp = os.path.join(root, f)
                                dir_size += os.path.getsize(fp)
                                file_count += 1
                            except (OSError, PermissionError):
                                pass
                except (OSError, PermissionError):
                    pass
                total_size += dir_size
                cleanup_items.append(
                    {
                        "directory": target_dir,
                        "file_count": file_count,
                        "size_mb": round(dir_size / (1024**2), 2),
                    }
                )

            return {
                "power_id": "PWR-112",
                "status": "success",
                "total_reclaimable_mb": round(total_size / (1024**2), 2),
                "locations": cleanup_items,
            }
        except Exception as e:
            return {"power_id": "PWR-112", "status": "error", "message": str(e)}

    # ------------------------------------------------------------------
    # Process Management (PWR-115, PWR-116)
    # ------------------------------------------------------------------

    @staticmethod
    def process_list(top_n: int = 20) -> Dict[str, Any]:
        """PWR-115: Top processes by CPU and memory usage."""
        try:
            procs: List[Dict[str, Any]] = []
            for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status"]):
                try:
                    info = p.info
                    procs.append(
                        {
                            "pid": info["pid"],
                            "name": info["name"],
                            "cpu_percent": info.get("cpu_percent", 0.0) or 0.0,
                            "memory_percent": round(info.get("memory_percent", 0.0) or 0.0, 2),
                            "status": info.get("status", "unknown"),
                        }
                    )
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            procs.sort(key=lambda x: x["cpu_percent"] + x["memory_percent"], reverse=True)
            return {
                "power_id": "PWR-115",
                "status": "success",
                "total_processes": len(procs),
                "top_processes": procs[:top_n],
            }
        except Exception as e:
            return {"power_id": "PWR-115", "status": "error", "message": str(e)}

    @staticmethod
    def kill_process(pid: int) -> Dict[str, Any]:
        """PWR-116: Kill a process by PID. Requires user approval."""
        try:
            proc = psutil.Process(pid)
            proc_name = proc.name()
            proc.terminate()
            gone, alive = psutil.wait_procs([proc], timeout=5)
            if alive:
                for p in alive:
                    p.kill()
            return {
                "power_id": "PWR-116",
                "status": "success",
                "pid": pid,
                "name": proc_name,
                "message": f"Process {proc_name} (PID {pid}) terminated",
                "approval_required": True,
            }
        except psutil.NoSuchProcess:
            return {
                "power_id": "PWR-116",
                "status": "error",
                "message": f"No process with PID {pid}",
                "approval_required": True,
            }
        except psutil.AccessDenied:
            return {
                "power_id": "PWR-116",
                "status": "error",
                "message": f"Access denied for PID {pid}",
                "approval_required": True,
            }
        except Exception as e:
            return {"power_id": "PWR-116", "status": "error", "message": str(e), "approval_required": True}

    # ------------------------------------------------------------------
    # Event Logs & System Info (PWR-118 to PWR-126)
    # ------------------------------------------------------------------

    @staticmethod
    def event_log_search(keyword: str, source: str = "System", count: int = 20) -> Dict[str, Any]:
        """PWR-118: Search Windows Event Log entries matching a keyword."""
        try:
            ps_script = (
                f"Get-EventLog -LogName {source} -Newest 200 -ErrorAction Stop | "
                f"Where-Object {{ $_.Message -match '{keyword}' }} | "
                f"Select-Object -First {count} TimeGenerated, EntryType, Source, Message | "
                f"ConvertTo-Json -Depth 3"
            )
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=30,
            )
            import json

            try:
                events = json.loads(res.stdout) if res.stdout.strip() else []
                if isinstance(events, dict):
                    events = [events]
            except json.JSONDecodeError:
                events = [{"raw": res.stdout[:3000]}]

            return {
                "power_id": "PWR-118",
                "status": "success",
                "keyword": keyword,
                "source": source,
                "event_count": len(events),
                "events": events[:count],
            }
        except Exception as e:
            return {"power_id": "PWR-118", "status": "error", "message": str(e)}

    @staticmethod
    def startup_programs() -> Dict[str, Any]:
        """PWR-119: List startup programs from common registry locations."""
        try:
            programs: List[Dict[str, str]] = []
            reg_paths = [
                (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
                (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run"),
            ]
            for hive, path in reg_paths:
                try:
                    key = winreg.OpenKey(hive, path)
                    i = 0
                    while True:
                        try:
                            name, value, _ = winreg.EnumValue(key, i)
                            programs.append(
                                {
                                    "name": name,
                                    "command": value,
                                    "location": f"{'HKCU' if hive == winreg.HKEY_CURRENT_USER else 'HKLM'}\\{path}",
                                }
                            )
                            i += 1
                        except OSError:
                            break
                    winreg.CloseKey(key)
                except OSError:
                    pass

            # Also check startup folder
            startup_folder = os.path.join(
                os.environ.get("APPDATA", ""),
                r"Microsoft\Windows\Start Menu\Programs\Startup",
            )
            if os.path.isdir(startup_folder):
                for f in os.listdir(startup_folder):
                    programs.append(
                        {"name": f, "command": os.path.join(startup_folder, f), "location": "Startup Folder"}
                    )

            return {
                "power_id": "PWR-119",
                "status": "success",
                "count": len(programs),
                "programs": programs,
            }
        except Exception as e:
            return {"power_id": "PWR-119", "status": "error", "message": str(e)}

    @staticmethod
    def ssl_cert_check(host: str, port: int = 443) -> Dict[str, Any]:
        """PWR-120: Check TLS certificate expiry for a host."""
        try:
            ctx = ssl.create_default_context()
            with socket.create_connection((host, port), timeout=5) as sock:
                with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                    cert = ssock.getpeercert()
                    not_after = cert.get("notAfter", "")
                    expiry = datetime.datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
                    days_left = (expiry - datetime.datetime.utcnow()).days
                    return {
                        "power_id": "PWR-120",
                        "status": "success",
                        "host": host,
                        "port": port,
                        "subject": dict(x[0] for x in cert.get("subject", [])),
                        "issuer": dict(x[0] for x in cert.get("issuer", [])),
                        "expires_at": expiry.strftime("%Y-%m-%d %H:%M:%S"),
                        "days_remaining": days_left,
                        "warning": days_left < 30,
                    }
        except Exception as e:
            return {"power_id": "PWR-120", "status": "error", "host": host, "message": str(e)}

    @staticmethod
    def system_uptime() -> Dict[str, Any]:
        """PWR-121: System uptime since last boot."""
        try:
            boot_ts = psutil.boot_time()
            boot_dt = datetime.datetime.fromtimestamp(boot_ts)
            now = datetime.datetime.now()
            delta = now - boot_dt
            days = delta.days
            hours, remainder = divmod(delta.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return {
                "power_id": "PWR-121",
                "status": "success",
                "boot_time": boot_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "uptime_str": f"{days}d {hours}h {minutes}m {seconds}s",
                "uptime_seconds": int(delta.total_seconds()),
            }
        except Exception as e:
            return {"power_id": "PWR-121", "status": "error", "message": str(e)}

    @staticmethod
    def installed_software() -> Dict[str, Any]:
        """PWR-122: List installed programs from the registry."""
        try:
            programs: List[Dict[str, str]] = []
            reg_paths = [
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
                (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            ]
            seen = set()
            for hive, path in reg_paths:
                try:
                    key = winreg.OpenKey(hive, path)
                    for i in range(winreg.QueryInfoKey(key)[0]):
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            subkey = winreg.OpenKey(key, subkey_name)
                            try:
                                name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                            except OSError:
                                continue
                            if name in seen:
                                continue
                            seen.add(name)
                            version = ""
                            try:
                                version = winreg.QueryValueEx(subkey, "DisplayVersion")[0]
                            except OSError:
                                pass
                            publisher = ""
                            try:
                                publisher = winreg.QueryValueEx(subkey, "Publisher")[0]
                            except OSError:
                                pass
                            programs.append({"name": name, "version": version, "publisher": publisher})
                            winreg.CloseKey(subkey)
                        except OSError:
                            pass
                    winreg.CloseKey(key)
                except OSError:
                    pass

            programs.sort(key=lambda x: x["name"].lower())
            return {
                "power_id": "PWR-122",
                "status": "success",
                "count": len(programs),
                "programs": programs,
            }
        except Exception as e:
            return {"power_id": "PWR-122", "status": "error", "message": str(e)}

    @staticmethod
    def environment_variables() -> Dict[str, Any]:
        """PWR-123: List environment variables with secrets masked."""
        try:
            secret_keywords = {
                "key",
                "secret",
                "token",
                "password",
                "passwd",
                "credential",
                "auth",
                "api_key",
                "apikey",
                "private",
            }
            env_vars: List[Dict[str, str]] = []
            for k, v in sorted(os.environ.items()):
                is_sensitive = any(s in k.lower() for s in secret_keywords)
                env_vars.append(
                    {
                        "name": k,
                        "value": "****REDACTED****" if is_sensitive else v,
                        "sensitive": is_sensitive,
                    }
                )
            return {
                "power_id": "PWR-123",
                "status": "success",
                "count": len(env_vars),
                "variables": env_vars,
            }
        except Exception as e:
            return {"power_id": "PWR-123", "status": "error", "message": str(e)}

    @staticmethod
    def driver_info() -> Dict[str, Any]:
        """PWR-124: GPU/display driver information via WMIC."""
        try:
            res = subprocess.run(
                ["wmic", "path", "Win32_VideoController", "get", "Name,DriverVersion,AdapterRAM,Status", "/format:csv"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            drivers: List[Dict[str, str]] = []
            lines = [l.strip() for l in res.stdout.strip().splitlines() if l.strip()]
            if len(lines) > 1:
                headers = [h.strip() for h in lines[0].split(",")]
                for line in lines[1:]:
                    values = [v.strip() for v in line.split(",")]
                    if len(values) >= len(headers):
                        entry = dict(zip(headers, values))
                        drivers.append(entry)

            return {
                "power_id": "PWR-124",
                "status": "success",
                "gpu_count": len(drivers),
                "drivers": drivers,
            }
        except Exception as e:
            return {"power_id": "PWR-124", "status": "error", "message": str(e)}

    @staticmethod
    def windows_update_status() -> Dict[str, Any]:
        """PWR-125: Check Windows Update status via PowerShell."""
        try:
            ps_script = (
                "try { "
                "$session = New-Object -ComObject Microsoft.Update.Session; "
                "$searcher = $session.CreateUpdateSearcher(); "
                "$result = $searcher.Search('IsInstalled=0'); "
                "$updates = @(); "
                "foreach ($u in $result.Updates) { "
                "  $updates += @{Title=$u.Title; Severity=$u.MsrcSeverity; "
                "  KB=($u.KBArticleIDs -join ',')}; "
                "}; "
                "$updates | ConvertTo-Json -Depth 2 "
                "} catch { Write-Output (ConvertTo-Json @{error=$_.Exception.Message}) }"
            )
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=60,
            )
            import json

            try:
                updates = json.loads(res.stdout) if res.stdout.strip() else []
                if isinstance(updates, dict):
                    if "error" in updates:
                        return {"power_id": "PWR-125", "status": "error", "message": updates["error"]}
                    updates = [updates]
            except json.JSONDecodeError:
                updates = []

            return {
                "power_id": "PWR-125",
                "status": "success",
                "pending_count": len(updates),
                "pending_updates": updates[:50],
            }
        except Exception as e:
            return {"power_id": "PWR-125", "status": "error", "message": str(e)}

    @staticmethod
    def crash_dump_analysis() -> Dict[str, Any]:
        """PWR-126: Check for recent BSOD/crash dumps."""
        try:
            dump_paths = [
                os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Minidump"),
                os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "MEMORY.DMP"),
            ]
            dumps: List[Dict[str, Any]] = []

            minidump_dir = dump_paths[0]
            if os.path.isdir(minidump_dir):
                for f in sorted(os.listdir(minidump_dir), reverse=True)[:20]:
                    fp = os.path.join(minidump_dir, f)
                    try:
                        stat = os.stat(fp)
                        dumps.append(
                            {
                                "file": f,
                                "path": fp,
                                "size_kb": round(stat.st_size / 1024, 2),
                                "created": datetime.datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S"),
                            }
                        )
                    except OSError:
                        pass

            full_dump = dump_paths[1]
            if os.path.isfile(full_dump):
                try:
                    stat = os.stat(full_dump)
                    dumps.append(
                        {
                            "file": "MEMORY.DMP",
                            "path": full_dump,
                            "size_mb": round(stat.st_size / (1024**2), 2),
                            "created": datetime.datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S"),
                        }
                    )
                except OSError:
                    pass

            return {
                "power_id": "PWR-126",
                "status": "success",
                "dump_count": len(dumps),
                "recent_dumps": dumps,
                "has_recent_crashes": len(dumps) > 0,
            }
        except Exception as e:
            return {"power_id": "PWR-126", "status": "error", "message": str(e)}


it_admin_powers = ITAdminPowers()
