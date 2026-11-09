"""JARVIS app connectors — launch/focus local apps and delegate to coding agents.

Two tiers, honestly separated:

1. Native launch: detached process starts (Antigravity, IDE form, opencode,
   browsers, terminals) — fully deterministic, testable via injected spawn.
2. Delegated tasking: "tell opencode to fix the tests" → headless
   `opencode run --auto "<task>"` (logs to data/logs/opencode_<ts>.log,
   detached, First-Law evidence record). For Antigravity there is no stable
   public task API, so the honest route is: launch + copy the task to the
   clipboard for the agent panel (Ctrl+V). Never pretend a typed-out task
   was consumed by the app.

Voice grammar (checked in this order, before the orchestrator):
  "open antigravity" / "launch opencode"   → launch
  "ask opencode to fix x"                  → opencode delegate
  "tell antigravity to plan x"             → antigravity open + clipboard
"""
import os
import re
import shutil
import subprocess
import time
from typing import Any, Callable, Dict, List, Optional

from jarvis.core.logger import get_logger
from jarvis.hud.state import REPO_ROOT

logger = get_logger("app_connector")

LOCALAPPDATA = os.environ.get("LOCALAPPDATA", "")
APPDATA = os.environ.get("APPDATA", "")

# Alias table measured on this host (First Law: real paths, real checks).
APP_TABLE: Dict[str, Dict[str, Any]] = {
    "antigravity": {
        "exe": os.path.join(LOCALAPPDATA, r"Programs\Antigravity\Antigravity.exe"),
        "title_hint": "Antigravity",
    },
    "antigravity_ide": {
        "exe": os.path.join(LOCALAPPDATA, r"Programs\Antigravity IDE\Antigravity IDE.exe"),
        "cmd": os.path.join(LOCALAPPDATA, r"Programs\Antigravity IDE\bin\antigravity-ide.cmd"),
        "title_hint": "Antigravity",
    },
    "opencode": {
        "exe": os.path.join(APPDATA, r"npm\opencode.cmd"),
        "exe_fallbacks": [os.path.join(APPDATA, r"npm\opencode")],
        "title_hint": "opencode",
    },
    "chrome":   {"exe_fallbacks": [os.path.join(LOCALAPPDATA, r"Google\Chrome\Application\chrome.exe")], "which": "chrome", "title_hint": "chrome"},
    "spotify":  {"exe_fallbacks": [os.path.join(LOCALAPPDATA, r"Microsoft\WindowsApps\Spotify.exe")], "title_hint": "spotify"},
    "vscode":   {"which": "code", "title_hint": "Visual Studio Code"},
    "code":     {"which": "code", "title_hint": "Visual Studio Code"},
    "notepad":  {"which": "notepad", "title_hint": "Notepad"},
    "explorer": {"which": "explorer", "title_hint": "Explorer"},
    "terminal": {"which": "wt", "title_hint": "Terminal"},
}

_ALIAS_PHRASES = {
    "antigravity": "antigravity",
    "antigravity ide": "antigravity_ide",
    "antigravity-ide": "antigravity_ide",
    "antigravity code": "antigravity_ide",
    "opencode": "opencode",
    "open code": "opencode",
    "open-code": "opencode",
    "chrome": "chrome",
    "spotify": "spotify",
    "vs code": "vscode",
    "vscode": "vscode",
    "code": "code",
    "notepad": "notepad",
    "explorer": "explorer",
    "file explorer": "explorer",
    "terminal": "terminal",
}


def _resolve_alias(name: str) -> Optional[str]:
    return _ALIAS_PHRASES.get(name.lower().strip())


def _resolve_executable(alias_id: str) -> Optional[str]:
    spec = APP_TABLE.get(alias_id) or {}
    for key in ("exe", "cmd"):
        p = spec.get(key)
        if p and os.path.isfile(p):
            return p
    for p in spec.get("exe_fallbacks", []):
        if p and os.path.isfile(p):
            return p
    which = spec.get("which")
    if which:
        found = shutil.which(which)
        if found:
            return found
    return None


# --------------------------------------------------------------------- #
#  Voice-intent fast path (pure matchers — tested without side effects)  #
# --------------------------------------------------------------------- #

_OPEN_RE = re.compile(
    r"^\s*(?:open|launch|start|fire up|pull up)\s+(?:the\s+|my\s+|up\s+)?([a-z0-9 \-]+?)\s*$",
    re.IGNORECASE,
)
_ASK_RE = re.compile(
    r"^\s*(?:ask|tell|command|send)\s+(?:my\s+)?(?P<agent>open ?code|opencode|antigravity(?:[ -]ide)?)\s+(?:to\s+|that\s+|and\s+|:\s*)?(?P<task>.+?)\s*$",
    re.IGNORECASE | re.DOTALL,
)
_OPENCODE_IN_RE = re.compile(
    r"^\s*(?:run|use)\s+(?:open ?code|opencode)\s+(?:in|on|at)\s+(?P<path>.+?)\s*$",
    re.IGNORECASE,
)
_WAKE_STRIP = " ,.!?;:"


def match_app_intent(command: str) -> Optional[Dict[str, Any]]:
    """Parses a stripped voice command into an app-connection intent, or None."""
    if not command:
        return None
    text = command.strip(_WAKE_STRIP).strip()
    if not text:
        return None

    m = _OPENCODE_IN_RE.match(text)
    if m:
        path = m.group("path").strip().strip("\"'")
        return {"kind": "opencode_in", "path": path}

    m = _ASK_RE.match(text)
    if m:
        agent = m.group("agent").lower().replace(" ", "").replace("-", "")
        agent_id = "antigravity" if agent.startswith("antigravity") else "opencode"
        # "antigravity ide" specifically routes to the classic IDE window
        if agent.endswith("ide"):
            agent_id = "antigravity_ide"
        return {"kind": "delegate", "agent": agent_id, "task": m.group("task").strip()}

    m = _OPEN_RE.match(text)
    if m:
        spoken = m.group(1).strip().lower()
        alias = _resolve_alias(spoken)
        if alias:
            return {"kind": "launch", "app": alias}
    return None


# --------------------------------------------------------------------- #
#  Executors (side effects; injectable spawn for tests)                   #
# --------------------------------------------------------------------- #

def _silent_spawn(argv: List[str]) -> int:
    """Detached, window-hidden launch; returns pid (0 on failure)."""
    try:
        CREATE_NO_WINDOW = 0x08000000
        DETACHED = 0x00000008
        proc = subprocess.Popen(
            argv,
            creationflags=CREATE_NO_WINDOW | DETACHED,
            close_fds=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return proc.pid
    except Exception as exc:
        logger.warning(f"spawn failed for {argv!r}: {exc}")
        return 0


def launch_in_console(alias_id: str, args: Optional[List[str]] = None,
                      spawner: Callable[[List[str]], int] = None) -> Dict[str, Any]:
    """Interactive session in a VISIBLE console (for TUIs the user drives)."""
    exe = _resolve_executable(alias_id)
    if not exe:
        return {"ok": False, "error": f"app '{alias_id}' not found on this host"}
    quoted = " ".join([f'"{exe}"'] + [f'"{a}"' for a in (args or [])])
    argv = ["cmd", "/c", "start", "", "cmd", "/k", quoted]
    spawn = spawner or _silent_spawn
    pid = spawn(argv)
    return {"ok": bool(pid), "app": alias_id, "argv": argv, "pid": pid}


def launch_app(alias_id: str, args: Optional[List[str]] = None,
               spawner: Callable[[List[str]], int] = _silent_spawn) -> Dict[str, Any]:
    exe = _resolve_executable(alias_id)
    if not exe:
        return {"ok": False, "error": f"app '{alias_id}' not found on this host", "app": alias_id}
    argv = [exe] + list(args or [])
    pid = spawner(argv)
    if not pid:
        return {"ok": False, "error": f"could not launch '{alias_id}'", "app": alias_id}
    logger.info(f"launched {alias_id} via {exe} (pid {pid})")
    return {"ok": True, "app": alias_id, "exe": exe, "argv": argv, "pid": pid}


def set_clipboard(text: str) -> bool:
    """Windows clipboard via PowerShell -EncodedCommand (quoting-safe)."""
    import base64

    encoded = base64.b64encode(
        f"Set-Clipboard -Value @'\n{text}\n'@".encode("utf-16le")
    ).decode("ascii")
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-EncodedCommand", encoded],
            timeout=15, check=False, capture_output=True,
        )
        return True
    except Exception:
        return False


def opencode_delegate(task: str, workdir: Optional[str] = None,
                      auto_approve: bool = True,
                      spawner: Callable[[List[str]], int] = _silent_spawn) -> Dict[str, Any]:
    """Headless delegate: runs `opencode run [--auto] "<task>"` detached, logged."""
    exe = _resolve_executable("opencode")
    if not exe:
        return {"ok": False, "error": "opencode CLI not found on this host"}
    cwd = workdir if (workdir and os.path.isdir(workdir)) else str(REPO_ROOT)
    argv = [exe, "run"]
    if auto_approve:
        argv.append("--auto")
    argv += ["--title", f"jarvis-wake-{int(time.time())}", task]
    log_dir = REPO_ROOT / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    # spawn via cmd to redirect into a per-task log while remaining detached
    log_path = log_dir / f"opencode_{int(time.time())}.log"
    cmdline = " ".join(f'"{a}"' for a in argv)
    argv2 = ["cmd", "/c", f'cd /d "{cwd}" && {cmdline} > "{log_path}" 2>&1']
    pid = spawner(argv2)
    if not pid:
        return {"ok": False, "error": "opencode delegate failed to launch", "argv": argv2}
    logger.info(f"opencode delegate started (pid {pid}) log={log_path}")
    return {
        "ok": True, "agent": "opencode", "task": task, "workdir": cwd,
        "auto_approve": auto_approve, "log": str(log_path), "pid": pid,
    }


def antigravity_delegate(task: str, project: Optional[str] = None,
                         agent: str = "antigravity",
                         spawner: Callable[[List[str]], int] = _silent_spawn) -> Dict[str, Any]:
    """Launches Antigravity + puts the task on the clipboard (no public API).

    Honest contract: we OPEN the app and PRE-LOAD the clipboard; the user
    pastes (Ctrl+V) into the agent panel. We do not claim the app consumed
    or executed the task.
    """
    args: List[str] = []
    if project:
        cleaned = project.strip().strip("\"'")
        if os.path.isdir(cleaned):
            args = [cleaned]
    launched = launch_app(agent, args, spawner=spawner)
    clipped = set_clipboard(task)
    launched.update({
        "agent": agent,
        "task": task,
        "clipboard": clipped,
        "task_preloaded": clipped,
        "handoff": "task on clipboard - Ctrl+V in the Antigravity agent panel" if clipped
                   else "app launched - copy the task manually",
    })
    launched["ok"] = bool(launched.get("ok"))
    return launched
