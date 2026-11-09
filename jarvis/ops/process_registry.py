"""Validated JARVIS process registry and lifecycle control.

The registry is the single source of truth for JARVIS-owned background
processes.  Every record carries enough identity material to prove that a PID
still belongs to the process JARVIS started:

    pid, role, executable, command line, creation timestamp, instance id

A PID alone is never trusted.  Before a process is signalled, the registry
re-validates the live creation timestamp and command line, which prevents
killing an unrelated process after Windows reuses a PID.

Roles managed here are the three processes launched by
``scripts/start_jarvis_background.vbs``:

    api_server   -> uvicorn jarvis.api.server:app
    voice_daemon -> pythonw -m jarvis.voice.daemon
    hud_overlay  -> pythonw -m jarvis.hud.overlay

CLI (used by the PowerShell stop scripts):

    python -m jarvis.ops.process_registry health
    python -m jarvis.ops.process_registry list
    python -m jarvis.ops.process_registry stop --role voice_daemon
    python -m jarvis.ops.process_registry stop --all
    python -m jarvis.ops.process_registry prune

The CLI never falls back to killing every ``python.exe``/``pythonw.exe``
process.  Unmatched processes are reported and left alone.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import psutil

from jarvis.config import PROJECT_ROOT, settings
from jarvis.core.logger import get_logger

logger = get_logger("ops.process_registry")

# Command-line signatures for the three startup-contract processes.  These are
# deliberately narrow: a match requires the exact module/entrypoint, not just
# the word "jarvis".
ROLE_PATTERNS: Dict[str, str] = {
    "api_server": r"uvicorn\s+jarvis\.api\.server:app\b",
    "voice_daemon": r"-m\s+jarvis\.voice\.daemon\b",
    "hud_overlay": r"-m\s+jarvis\.hud\.overlay\b",
}

ROLE_DESCRIPTIONS: Dict[str, str] = {
    "api_server": "FastAPI server + dashboard on 127.0.0.1:8000",
    "voice_daemon": "Always-on wake-word / voice command daemon",
    "hud_overlay": "Iron Man HUD overlay process",
}

REQUIRED_ROLES: Tuple[str, ...] = ("api_server", "voice_daemon", "hud_overlay")

_PYTHON_EXE_RE = re.compile(r"^python(?:w)?(?:\d+(?:\.\d+)*)?(?:\.exe)?$", re.IGNORECASE)


@dataclass
class ProcessRecord:
    """Identity record for one JARVIS-owned process instance."""

    instance_id: str
    pid: int
    role: str
    executable: str
    cmdline: str
    create_time: float
    repo_root: str
    registered_at: float = field(default_factory=time.time)
    source: str = "registered"  # registered | discovered | adopted

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProcessRecord":
        return cls(
            instance_id=str(data.get("instance_id") or f"legacy-{data.get('pid')}"),
            pid=int(data["pid"]),
            role=str(data["role"]),
            executable=str(data.get("executable", "")),
            cmdline=str(data.get("cmdline", "")),
            create_time=float(data.get("create_time", 0.0)),
            repo_root=str(data.get("repo_root", "")),
            registered_at=float(data.get("registered_at", 0.0)),
            source=str(data.get("source", "registered")),
        )


class RegistryLock:
    """Small cross-platform advisory lock around registry reads/writes."""

    def __init__(self, path: Path, timeout: float = 5.0):
        self.path = path
        self.timeout = timeout
        self._fh = None

    def __enter__(self) -> "RegistryLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "a+b")
        # Windows byte-range locks need at least one byte in the file.
        self._fh.seek(0, os.SEEK_END)
        if self._fh.tell() == 0:
            self._fh.write(b"\0")
            self._fh.flush()

        deadline = time.monotonic() + self.timeout
        while True:
            try:
                if os.name == "nt":
                    import msvcrt

                    self._fh.seek(0)
                    msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except OSError:
                if time.monotonic() >= deadline:
                    self._fh.close()
                    self._fh = None
                    raise TimeoutError(f"Timed out waiting for process registry lock: {self.path}")
                time.sleep(0.05)

    def __exit__(self, exc_type, exc, tb) -> None:
        if not self._fh:
            return
        try:
            if os.name == "nt":
                import msvcrt

                self._fh.seek(0)
                msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        finally:
            self._fh.close()
            self._fh = None


class ProcessRegistry:
    """Validated registry for JARVIS background processes."""

    def __init__(
        self,
        registry_path: Optional[Path] = None,
        repo_root: Optional[Path] = None,
        role_patterns: Optional[Dict[str, str]] = None,
        process_factory: Any = psutil.Process,
    ):
        self.registry_path = (
            Path(registry_path) if registry_path else (settings.data_dir / "runtime" / "process_registry.json")
        )
        self.lock_path = self.registry_path.with_suffix(".lock")
        self.repo_root = Path(repo_root) if repo_root else PROJECT_ROOT
        self.role_patterns = dict(role_patterns or ROLE_PATTERNS)
        self._process_factory = process_factory

    # ── Persistence ──────────────────────────────────────────────────────────

    def _load_unlocked(self) -> List[ProcessRecord]:
        if not self.registry_path.exists():
            return []
        try:
            raw = json.loads(self.registry_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            logger.warning("Process registry unreadable (%s); treating as empty.", exc)
            return []

        entries: Iterable[Any]
        if isinstance(raw, dict):
            entries = raw.get("records", [])
        elif isinstance(raw, list):
            entries = raw
        else:
            entries = []

        records: List[ProcessRecord] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            try:
                record = ProcessRecord.from_dict(entry)
            except (KeyError, TypeError, ValueError):
                continue
            if record.role in self.role_patterns:
                records.append(record)
        return records

    def _save_unlocked(self, records: Sequence[ProcessRecord]) -> None:
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "updated_at": time.time(),
            "records": [r.to_dict() for r in records],
        }
        tmp = self.registry_path.with_name(f"{self.registry_path.name}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, sort_keys=True)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self.registry_path)
        finally:
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass

    def load(self) -> List[ProcessRecord]:
        """Return raw registry records (may include stale entries)."""
        with RegistryLock(self.lock_path):
            return self._load_unlocked()

    def prune(self) -> List[Dict[str, Any]]:
        """Remove records that no longer describe a live JARVIS process."""
        removed: List[Dict[str, Any]] = []
        with RegistryLock(self.lock_path):
            records = self._load_unlocked()
            kept: List[ProcessRecord] = []
            for record in records:
                ok, reason = self._validate_record(record)
                if ok:
                    kept.append(record)
                else:
                    removed.append({**record.to_dict(), "reason": reason})
            if removed:
                self._save_unlocked(kept)
        return removed

    # ── Process identity helpers ─────────────────────────────────────────────

    def _normalized_repo(self) -> str:
        return os.path.normcase(os.path.abspath(str(self.repo_root)))

    def _is_python_executable(self, name: str) -> bool:
        return bool(_PYTHON_EXE_RE.match(Path(name or "").name))

    def _matches_role(
        self,
        role: str,
        cmdline: str,
        process_name: str = "",
        cwd: Optional[str] = None,
    ) -> bool:
        pattern = self.role_patterns.get(role)
        if not pattern or not cmdline:
            return False
        if not re.search(pattern, cmdline, re.IGNORECASE):
            return False
        if process_name and not self._is_python_executable(process_name):
            return False
        repo = self._normalized_repo()
        cwd_ok = bool(cwd) and os.path.normcase(os.path.abspath(cwd)) == repo
        cmdline_ok = repo in os.path.normcase(cmdline)
        return cwd_ok or cmdline_ok

    def _process_details(self, pid: int) -> Optional[Dict[str, Any]]:
        try:
            proc = self._process_factory(pid)
            return {
                "pid": pid,
                "name": proc.name(),
                "exe": proc.exe() if hasattr(proc, "exe") else "",
                "cmdline": " ".join(proc.cmdline()),
                "create_time": float(proc.create_time()),
                "cwd": proc.cwd() if hasattr(proc, "cwd") else None,
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError):
            return None

    def _record_for_pid(self, pid: int, role: str, source: str = "registered") -> Optional[ProcessRecord]:
        details = self._process_details(pid)
        if not details:
            return None
        if not self._matches_role(role, details["cmdline"], details["name"], details.get("cwd")):
            return None
        return ProcessRecord(
            instance_id=uuid.uuid4().hex,
            pid=pid,
            role=role,
            executable=details.get("exe") or details.get("name") or "",
            cmdline=details["cmdline"],
            create_time=details["create_time"],
            repo_root=str(self.repo_root),
            registered_at=time.time(),
            source=source,
        )

    def _validate_record(self, record: ProcessRecord) -> Tuple[bool, str]:
        """Prove that ``record.pid`` is still the exact process we registered."""
        try:
            proc = self._process_factory(record.pid)
        except (psutil.NoSuchProcess, psutil.ZombieProcess):
            return False, "process no longer exists"
        except (psutil.AccessDenied, OSError) as exc:
            return False, f"process not inspectable: {exc}"

        try:
            create_time = float(proc.create_time())
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError) as exc:
            return False, f"creation time unavailable: {exc}"

        # PID reuse guard.  Windows creation timestamps are high resolution;
        # one second of tolerance covers filesystem/JSON float rounding.
        if abs(create_time - record.create_time) > 1.0:
            return False, "creation time mismatch (PID likely reused)"

        try:
            cmdline = " ".join(proc.cmdline())
            name = proc.name()
            cwd = proc.cwd() if hasattr(proc, "cwd") else None
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError) as exc:
            return False, f"process details unavailable: {exc}"

        if not self._matches_role(record.role, cmdline, name, cwd):
            return False, "command line no longer matches registered role"
        return True, ""

    # ── Discovery ────────────────────────────────────────────────────────────

    def discover(self, role: Optional[str] = None) -> List[ProcessRecord]:
        """Find live JARVIS processes by validated command line.

        This is the safety net for processes started before the registry
        existed (or if the registry file was removed).  Discovery still
        requires a matching role signature, a Python executable, and a working
        directory inside this repository.
        """
        wanted = {role} if role else set(self.role_patterns)
        found: List[ProcessRecord] = []
        own_pid = os.getpid()

        for proc in psutil.process_iter(["pid", "name", "exe", "cmdline", "create_time"]):
            try:
                pid = int(proc.info["pid"])
                if pid == own_pid:
                    continue
                name = proc.info.get("name") or ""
                if not self._is_python_executable(name):
                    continue
                cmdline = " ".join(proc.info.get("cmdline") or [])
                if not cmdline:
                    continue
                try:
                    cwd = proc.cwd()
                except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
                    cwd = None
                for candidate in wanted:
                    if self._matches_role(candidate, cmdline, name, cwd):
                        found.append(
                            ProcessRecord(
                                instance_id=f"discovered-{pid}",
                                pid=pid,
                                role=candidate,
                                executable=proc.info.get("exe") or name,
                                cmdline=cmdline,
                                create_time=float(proc.info.get("create_time") or proc.create_time()),
                                repo_root=str(self.repo_root),
                                registered_at=time.time(),
                                source="discovered",
                            )
                        )
                        break
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError):
                continue
        return found

    # ── Registration / claim ─────────────────────────────────────────────────

    def register_current(self, role: str) -> Optional[ProcessRecord]:
        """Register the calling process under ``role``.

        Returns ``None`` when the calling process does not actually match the
        role signature (for example, a pytest process importing the API app).
        That keeps test runs from polluting the production registry.
        """
        if role not in self.role_patterns:
            raise ValueError(f"Unknown JARVIS role: {role}")
        record = self._record_for_pid(os.getpid(), role)
        if not record:
            logger.debug("Current process does not match role signature '%s'; not registered.", role)
            return None
        with RegistryLock(self.lock_path):
            records = [r for r in self._load_unlocked() if self._validate_record(r)[0]]
            records = [r for r in records if r.pid != record.pid]
            records.append(record)
            self._save_unlocked(records)
        return record

    def adopt(self, role: str, pid: int) -> Optional[ProcessRecord]:
        """Adopt an already-running, validated process into the registry.

        Used for processes started before the registry existed and by
        lifecycle tests.  The process must still match the role signature.
        """
        if role not in self.role_patterns:
            raise ValueError(f"Unknown JARVIS role: {role}")
        record = self._record_for_pid(pid, role, source="adopted")
        if not record:
            return None
        with RegistryLock(self.lock_path):
            records = [r for r in self._load_unlocked() if self._validate_record(r)[0]]
            for existing in records:
                if existing.pid == pid:
                    return existing
            records.append(record)
            self._save_unlocked(records)
        return record

    def claim_role(self, role: str) -> Tuple[str, Optional[ProcessRecord]]:
        """Atomically claim a singleton role for the calling process.

        Returns ``("REGISTERED", record)`` when this process now owns the role,
        or ``("EXISTING", record)`` when another live instance (registered or
        discovered) already owns it.  Callers should exit cleanly on EXISTING,
        which makes repeated launcher invocations idempotent.
        """
        if role not in self.role_patterns:
            raise ValueError(f"Unknown JARVIS role: {role}")

        record = self._record_for_pid(os.getpid(), role)
        if not record:
            logger.debug("Current process does not match role signature '%s'; cannot claim.", role)
            return "NO_MATCH", None

        with RegistryLock(self.lock_path):
            records = self._load_unlocked()
            live: List[ProcessRecord] = []
            for existing in records:
                ok, _reason = self._validate_record(existing)
                if ok:
                    live.append(existing)
            records = live

            for existing in records:
                if existing.role == role and existing.pid != record.pid:
                    self._save_unlocked(records)
                    return "EXISTING", existing

            # Adopt a legacy/unregistered process before spawning a duplicate.
            for discovered in self.discover(role):
                if discovered.pid == record.pid:
                    continue
                discovered.source = "adopted"
                records.append(discovered)
                self._save_unlocked(records)
                return "EXISTING", discovered

            records = [r for r in records if r.pid != record.pid]
            records.append(record)
            self._save_unlocked(records)
            return "REGISTERED", record

    def release(self, role: Optional[str] = None) -> bool:
        """Remove the calling process's record (used on clean shutdown)."""
        pid = os.getpid()
        removed = False
        with RegistryLock(self.lock_path):
            records = self._load_unlocked()
            kept = []
            for record in records:
                if record.pid == pid and (role is None or record.role == role):
                    removed = True
                    continue
                kept.append(record)
            if removed:
                self._save_unlocked(kept)
        return removed

    # ── Health ───────────────────────────────────────────────────────────────

    def health(self) -> Dict[str, Any]:
        """Return honest, per-role process health.

        Status values:
          RUNNING              registered record validated against the live OS
          RUNNING_UNREGISTERED discovered live process with no registry record
          STOPPED              no validated live process
        """
        records = self.load()
        live: Dict[int, ProcessRecord] = {}
        stale: List[Dict[str, Any]] = []

        for record in records:
            ok, reason = self._validate_record(record)
            if ok:
                live[record.pid] = record
            else:
                stale.append({**record.to_dict(), "reason": reason})

        for discovered in self.discover():
            if discovered.pid not in live:
                live[discovered.pid] = discovered

        roles: Dict[str, Any] = {}
        for role in self.role_patterns:
            instances = [r for r in live.values() if r.role == role]
            unregistered = any(r.source == "discovered" for r in instances)
            if not instances:
                status = "STOPPED"
            elif unregistered:
                status = "RUNNING_UNREGISTERED"
            else:
                status = "RUNNING"
            roles[role] = {
                "role": role,
                "description": ROLE_DESCRIPTIONS.get(role, ""),
                "status": status,
                "running": bool(instances),
                "instances": [r.to_dict() for r in instances],
            }

        return {
            "registry_path": str(self.registry_path),
            "repo_root": str(self.repo_root),
            "roles": roles,
            "stale_records": stale,
            "all_required_running": all(roles[r]["running"] for r in REQUIRED_ROLES),
            "checked_at": time.time(),
        }

    def summary(self) -> Dict[str, Any]:
        """Compact status map suitable for embedding in /health responses."""
        report = self.health()
        return {
            role: {
                "status": info["status"],
                "pids": [i["pid"] for i in info["instances"]],
            }
            for role, info in report["roles"].items()
        }

    # ── Stop ─────────────────────────────────────────────────────────────────

    def stop(
        self,
        role: Optional[str] = None,
        stop_all: bool = False,
        timeout: float = 5.0,
    ) -> Dict[str, Any]:
        """Stop validated JARVIS processes for one role or all roles.

        Every target is re-validated (PID + creation time + command line)
        immediately before it is signalled.  Invalid records are reported as
        skipped, never killed.
        """
        if not stop_all and role not in self.role_patterns:
            raise ValueError(f"Specify a valid role or stop_all=True (got {role!r})")

        wanted = set(self.role_patterns) if stop_all else {role}
        stopped: List[Dict[str, Any]] = []
        already: List[Dict[str, Any]] = []
        skipped: List[Dict[str, Any]] = []
        failed: List[Dict[str, Any]] = []
        targets: Dict[int, ProcessRecord] = {}

        with RegistryLock(self.lock_path):
            records = self._load_unlocked()
            kept: List[ProcessRecord] = []
            for record in records:
                if record.role not in wanted:
                    kept.append(record)
                    continue
                ok, reason = self._validate_record(record)
                if ok:
                    targets[record.pid] = record
                else:
                    skipped.append({**record.to_dict(), "reason": f"refused: {reason}"})

            for discovered in self.discover():
                if discovered.role in wanted and discovered.pid not in targets:
                    if discovered.pid == os.getpid():
                        continue
                    targets[discovered.pid] = discovered

            for pid, record in targets.items():
                outcome, detail = self._terminate_validated(record, timeout)
                if outcome == "STOPPED":
                    stopped.append(detail)
                elif outcome == "ALREADY_STOPPED":
                    already.append(detail)
                elif outcome == "SKIPPED":
                    skipped.append(detail)
                    kept.append(record)
                else:
                    failed.append(detail)
                    kept.append(record)

            self._save_unlocked(kept)

        return {
            "requested": "all" if stop_all else role,
            "stopped": stopped,
            "already_stopped": already,
            "skipped": skipped,
            "failed": failed,
            "success": not failed and not any(s.get("reason", "").startswith("refused") for s in skipped),
            "checked_at": time.time(),
        }

    def _terminate_validated(self, record: ProcessRecord, timeout: float) -> Tuple[str, Dict[str, Any]]:
        ok, reason = self._validate_record(record)
        if not ok:
            return "SKIPPED", {**record.to_dict(), "reason": f"refused: {reason}"}

        try:
            proc = self._process_factory(record.pid)
        except psutil.NoSuchProcess:
            return "ALREADY_STOPPED", {**record.to_dict(), "reason": "already exited"}

        detail = {
            "pid": record.pid,
            "role": record.role,
            "executable": record.executable,
            "instance_id": record.instance_id,
        }
        try:
            proc.terminate()
            _gone, alive = psutil.wait_procs([proc], timeout=timeout)
            if alive:
                # Last resort for a hung daemon.  It is still the validated
                # process identity, never an arbitrary PID.
                proc.kill()
                psutil.wait_procs([proc], timeout=2.0)
            if proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE:
                return "FAILED", {**detail, "reason": "process survived terminate/kill"}
            return "STOPPED", detail
        except psutil.NoSuchProcess:
            return "ALREADY_STOPPED", {**detail, "reason": "exited during stop"}
        except (psutil.AccessDenied, OSError) as exc:
            return "FAILED", {**detail, "reason": str(exc)}


# Global registry singleton
process_registry = ProcessRegistry()


# ── CLI ──────────────────────────────────────────────────────────────────────


def _print_health(report: Dict[str, Any]) -> None:
    print("JARVIS process health")
    print(f"  registry: {report['registry_path']}")
    for role, info in report["roles"].items():
        pids = ", ".join(str(i["pid"]) for i in info["instances"]) or "-"
        print(f"  {role:<13} {info['status']:<20} pids: {pids}")
        for instance in info["instances"]:
            print(f"      {instance['executable']}  cmd: {instance['cmdline']}")
    if report["stale_records"]:
        print(f"  stale records: {len(report['stale_records'])}")
        for stale in report["stale_records"]:
            print(f"      pid {stale['pid']} ({stale['role']}): {stale['reason']}")
    print(f"  all required running: {report['all_required_running']}")


def _print_stop(report: Dict[str, Any]) -> None:
    requested = report["requested"]
    print(f"JARVIS stop requested: {requested}")
    for item in report["stopped"]:
        print(f"  stopped  {item['pid']} ({item['role']}) {item['executable']}")
    for item in report["already_stopped"]:
        print(f"  already stopped  {item['pid']} ({item['role']})")
    for item in report["skipped"]:
        print(f"  skipped  {item['pid']} ({item['role']}): {item['reason']}")
    for item in report["failed"]:
        print(f"  FAILED  {item['pid']} ({item['role']}): {item['reason']}")
    if not report["stopped"] and not report["already_stopped"]:
        print("  No running JARVIS process matched the requested role (idempotent no-op).")
    print("  result:", "SUCCESS" if report["success"] else "INCOMPLETE")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="JARVIS validated process registry")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("health", help="show validated per-role process health")
    sub.add_parser("list", help="list raw registry records")
    sub.add_parser("prune", help="remove stale registry records")

    stop_parser = sub.add_parser("stop", help="stop validated JARVIS processes")
    group = stop_parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--role", choices=sorted(ROLE_PATTERNS))
    group.add_argument("--all", action="store_true", dest="stop_all")

    args = parser.parse_args(argv)

    try:
        if args.command == "health":
            report = process_registry.health()
            if args.json:
                print(json.dumps(report, indent=2, sort_keys=True))
            else:
                _print_health(report)
            return 0
        if args.command == "list":
            records = [record.to_dict() for record in process_registry.load()]
            if args.json:
                print(json.dumps(records, indent=2, sort_keys=True))
            else:
                for record in records:
                    print(
                        f"{record['pid']}\t{record['role']}\t{record['instance_id']}\t"
                        f"{record['create_time']:.3f}\t{record['cmdline']}"
                    )
            return 0
        if args.command == "prune":
            removed = process_registry.prune()
            if args.json:
                print(json.dumps(removed, indent=2, sort_keys=True))
            elif not removed:
                print("No stale JARVIS process records.")
            else:
                for item in removed:
                    print(f"pruned  {item['pid']} ({item['role']}): {item['reason']}")
            return 0
        if args.command == "stop":
            report = process_registry.stop(role=args.role, stop_all=args.stop_all)
            if args.json:
                print(json.dumps(report, indent=2, sort_keys=True))
            else:
                _print_stop(report)
            return 0 if report["success"] else 1
    except (ValueError, TimeoutError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
