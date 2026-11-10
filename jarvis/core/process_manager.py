"""
JARVIS Headless Process & Lifecycle Manager (R4)
Provides singleton process management, .jarvis.pid tracking, duplicate instance prevention,
telemetry logging, process status inspection, and clean shutdown signaling.
"""

import os
import json
import time
import signal
from pathlib import Path
from typing import Dict, Any, Optional, List
import psutil
from jarvis.core.logger import logger


class ProcessManager:
    """
    Manages process lifecycles, PID tracking, single-instance enforcement,
    and process telemetry.
    """

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or Path(__file__).resolve().parent.parent.parent
        self.pid_dir = self.base_dir / "data" / "pids"
        self.log_dir = self.base_dir / "data" / "logs"
        self.root_pid_file = self.base_dir / ".jarvis.pid"
        self.jarvis_pid_file = self.base_dir / "jarvis.pid"
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        self.pid_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def _get_pid_path(self, service_name: str) -> Path:
        if service_name == "jarvis":
            return self.root_pid_file
        return self.pid_dir / f"{service_name}.pid"

    @staticmethod
    def _is_pid_alive(pid: int) -> bool:
        """Checks if a process with given PID is genuinely alive and non-zombie."""
        if not isinstance(pid, int) or pid <= 0:
            return False
        try:
            if not psutil.pid_exists(pid):
                return False
            proc = psutil.Process(pid)
            return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        except Exception:
            pass

        # Fallback to os.kill(pid, 0)
        try:
            os.kill(pid, 0)
            return True
        except (OSError, SystemError):
            return False

    def acquire_pid(
        self,
        service_name: str = "jarvis",
        pid: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Acquires single-instance execution lock for a service.
        Returns True if acquired successfully, False if already running.
        """
        self._ensure_dirs()
        pid = pid or os.getpid()

        # Check for existing running instance
        if self.is_running(service_name):
            existing_info = self.read_pid(service_name)
            existing_pid = existing_info.get("pid") if existing_info else None
            if existing_pid != pid:
                logger.warning(
                    f"Service '{service_name}' is already running with PID {existing_pid}. Acquisition rejected."
                )
                self.log_telemetry(
                    "duplicate_instance_blocked",
                    {"service": service_name, "existing_pid": existing_pid, "attempted_pid": pid},
                )
                return False

        record = {
            "service": service_name,
            "pid": pid,
            "started_at": time.time(),
            "metadata": metadata or {},
        }

        # Write to service-specific PID path
        target_path = self._get_pid_path(service_name)
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2)

        # Also write unhidden jarvis.pid and mirror in data/pids if root PID was used
        if service_name == "jarvis":
            with open(self.jarvis_pid_file, "w", encoding="utf-8") as f:
                json.dump(record, f, indent=2)
            with open(self.pid_dir / "jarvis.pid", "w", encoding="utf-8") as f:
                json.dump(record, f, indent=2)

        self.log_telemetry("service_started", {"service": service_name, "pid": pid})
        self.update_health(service_name, "RUNNING", {"pid": pid})
        return True

    def release_pid(self, service_name: str = "jarvis") -> None:
        """Removes PID file for the specified service."""
        target_path = self._get_pid_path(service_name)
        if target_path.exists():
            try:
                target_path.unlink()
            except OSError:
                pass

        if service_name == "jarvis":
            for extra_path in (self.jarvis_pid_file, self.pid_dir / "jarvis.pid"):
                if extra_path.exists():
                    try:
                        extra_path.unlink()
                    except OSError:
                        pass

        self.log_telemetry("service_stopped", {"service": service_name})
        self.update_health(service_name, "STOPPED")

    def read_pid(self, service_name: str = "jarvis") -> Optional[Dict[str, Any]]:
        """Reads PID record for service. Checks root .jarvis.pid, jarvis.pid, or data/pids."""
        candidates = [self._get_pid_path(service_name)]
        if service_name == "jarvis":
            candidates.extend([self.jarvis_pid_file, self.pid_dir / "jarvis.pid"])

        for target_path in candidates:
            if target_path.exists():
                try:
                    with open(target_path, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception:
                    continue
        return None

    def is_running(self, service_name: str = "jarvis") -> bool:
        """
        Checks if the service PID exists and corresponds to an active process.
        Automatically cleans up stale PID files if process is dead.
        """
        info = self.read_pid(service_name)
        if not info or "pid" not in info:
            return False

        pid = info["pid"]
        if not self._is_pid_alive(pid):
            # Stale PID file; clean up
            self.release_pid(service_name)
            return False

        return True

    def stop_service(self, service_name: str = "jarvis", timeout_sec: float = 5.0) -> bool:
        """
        Cleanly stops a running background service:
        1. Sends SIGTERM / terminate signal
        2. Waits up to timeout_sec
        3. Forces kill if still alive
        4. Cleans up PID file
        """
        info = self.read_pid(service_name)
        if not info:
            return True

        pid = info["pid"]
        if not psutil.pid_exists(pid):
            self.release_pid(service_name)
            return True

        stopped = False
        try:
            proc = psutil.Process(pid)
            logger.info(f"Signaling process {pid} ({service_name}) for termination...")
            proc.terminate()
            try:
                proc.wait(timeout=timeout_sec)
                stopped = True
            except psutil.TimeoutExpired:
                logger.warning(f"Process {pid} ({service_name}) did not terminate within {timeout_sec}s; killing...")
                proc.kill()
                proc.wait(timeout=2.0)
                stopped = True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            stopped = True
        except Exception as e:
            logger.error(f"Error stopping process {pid}: {e}")

        self.release_pid(service_name)
        return stopped

    def stop_all(self, timeout_sec: float = 5.0) -> Dict[str, bool]:
        """Stops all tracked services."""
        results = {}
        # Root PID
        if self.root_pid_file.exists():
            results["jarvis"] = self.stop_service("jarvis", timeout_sec)

        # Service PIDs in data/pids
        for pid_file in self.pid_dir.glob("*.pid"):
            svc = pid_file.stem
            results[svc] = self.stop_service(svc, timeout_sec)
        return results

    def get_status(self, service_name: str = "jarvis") -> Dict[str, Any]:
        """Inspects status, metrics, and health of a specific service."""
        info = self.read_pid(service_name)
        if not info or "pid" not in info:
            return {"service": service_name, "running": False, "status": "STOPPED"}

        pid = info["pid"]
        running = False
        cpu_percent = 0.0
        memory_mb = 0.0
        uptime_sec = 0.0

        if psutil.pid_exists(pid):
            try:
                proc = psutil.Process(pid)
                if proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE:
                    running = True
                    uptime_sec = round(time.time() - info.get("started_at", time.time()), 1)
                    cpu_percent = proc.cpu_percent(interval=0.0)
                    memory_mb = round(proc.memory_info().rss / (1024 * 1024), 2)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                running = False

        if not running:
            self.release_pid(service_name)
            return {"service": service_name, "running": False, "status": "STOPPED"}

        return {
            "service": service_name,
            "running": True,
            "pid": pid,
            "status": "RUNNING",
            "uptime_sec": uptime_sec,
            "cpu_percent": cpu_percent,
            "memory_mb": memory_mb,
            "metadata": info.get("metadata", {}),
        }

    def get_all_statuses(self) -> Dict[str, Any]:
        """Gathers statuses of all known services."""
        statuses = {}
        # Check root jarvis service
        statuses["jarvis"] = self.get_status("jarvis")

        # Check all in pid_dir
        for p in self.pid_dir.glob("*.pid"):
            svc = p.stem
            if svc not in statuses:
                statuses[svc] = self.get_status(svc)
        return statuses

    def log_telemetry(self, event: str, data: Optional[Dict[str, Any]] = None) -> None:
        """Appends lifecycle telemetry events to data/logs/daemon_telemetry.jsonl."""
        self._ensure_dirs()
        entry = {
            "event": event,
            "timestamp": time.time(),
            "data": data or {},
        }
        try:
            with open(self.log_dir / "daemon_telemetry.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to log daemon telemetry: {e}")

    def update_health(self, service_name: str, status: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Writes daemon health summary to data/logs/daemon_health.json."""
        self._ensure_dirs()
        health_file = self.log_dir / "daemon_health.json"
        current_data = {}
        if health_file.exists():
            try:
                with open(health_file, "r", encoding="utf-8") as f:
                    current_data = json.load(f)
            except Exception:
                current_data = {}

        current_data[service_name] = {
            "status": status,
            "updated_at": time.time(),
            "details": details or {},
        }

        try:
            with open(health_file, "w", encoding="utf-8") as f:
                json.dump(current_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to write daemon health: {e}")

    def is_audio_daemon_alive(self) -> bool:
        """Checks if the background audio daemon is actively running and responsive."""
        return self.is_running("audio_daemon")

    def get_audio_daemon_status(self) -> Dict[str, Any]:
        """Returns comprehensive status dictionary for the audio daemon."""
        return self.get_status("audio_daemon")

    def track_audio_daemon(
        self,
        pid: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Convenience method to register/acquire the audio daemon PID lock."""
        return self.acquire_pid("audio_daemon", pid=pid, metadata=metadata)

    def clean_shutdown(self, timeout_sec: float = 5.0) -> Dict[str, bool]:
        """
        Gracefully terminates all background services, releases all PID locks,
        and logs shutdown telemetry.
        """
        self.log_telemetry("clean_shutdown_requested")
        results = self.stop_all(timeout_sec=timeout_sec)
        # Final safety cleanup of root jarvis PID files if any exist
        for root_path in (self.root_pid_file, self.jarvis_pid_file, self.pid_dir / "jarvis.pid"):
            if root_path.exists():
                try:
                    root_path.unlink()
                except OSError:
                    pass
        return results

    def inspect_process(self, service_name: str = "jarvis") -> Dict[str, Any]:
        """Inspects status and metrics of a service (alias for get_status)."""
        return self.get_status(service_name)


# Singleton Process Manager
process_manager = ProcessManager()


def print_status_table() -> None:
    """Pretty prints status of all background services."""
    statuses = process_manager.get_all_statuses()
    print("=" * 75)
    print("                   JARVIS BACKGROUND PROCESS STATUS")
    print("=" * 75)
    if not statuses:
        print("  No background services tracked.")
    for svc, st in statuses.items():
        status_str = "RUNNING" if st.get("running") else "STOPPED"
        pid_str = str(st.get("pid", "-"))
        uptime = f"{st.get('uptime_sec', 0)}s" if st.get("running") else "-"
        mem = f"{st.get('memory_mb', 0)} MB" if st.get("running") else "-"
        print(f"Service: {svc:15} | Status: {status_str:8} | PID: {pid_str:7} | Mem: {mem:10} | Uptime: {uptime}")
    print("=" * 75)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "stop":
        res = process_manager.stop_all()
        print("[JARVIS] Shutdown report:", res)
    else:
        print_status_table()

