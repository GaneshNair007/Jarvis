"""
JARVIS Central Constants Module.
Defines immutable technical constants, enums, network security boundaries,
default DLP patterns, and application metadata.
"""

from enum import Enum
import ipaddress
import re
from typing import Dict, List, Tuple


# ─── Application Metadata ───────────────────────────────────────────────────

APP_NAME = "jarvis"
APP_TITLE = "JARVIS Personal AI Operating System"
APP_DESCRIPTION = (
    "Local-first, screen-first, voice-driven personal AI operator with "
    "policy-aware hybrid routing and zero-API local search."
)
APP_VERSION = "1.0.0"
SERVICE_NAME = "jarvis-core"


# ─── Enums ──────────────────────────────────────────────────────────────────

class TaskStatus(str, Enum):
    NEW = "NEW"
    TRIAGED = "TRIAGED"
    PLANNED = "PLANNED"
    POLICY_CHECK = "POLICY_CHECK"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    AWAITING_LOGIN = "AWAITING_LOGIN"
    DEVICE_OFFLINE = "DEVICE_OFFLINE"
    LIMIT_REACHED = "LIMIT_REACHED"
    FAILED_RECOVERABLE = "FAILED_RECOVERABLE"
    FAILED_TERMINAL = "FAILED_TERMINAL"
    CANCELLED = "CANCELLED"


class PolicyTier(int, Enum):
    TIER_0_OBSERVE = 0
    TIER_1_REVERSIBLE = 1
    TIER_2_EXPLICIT_APPROVAL = 2
    TIER_3_STEP_UP_AUTH = 3


class PrivilegeLevel(int, Enum):
    PUBLIC_READ = 0
    LOCAL_READ = 1
    LOCAL_WRITE = 2
    OUTBOUND_COMM = 3
    SYSTEM_MODIFY = 4
    IRREVERSIBLE_OP = 5


class ModelTier(str, Enum):
    BYPASS = "BYPASS"
    TIER_1_LOCAL = "TIER_1_LOCAL"
    TIER_2_PRIVATE = "TIER_2_PRIVATE"
    TIER_3_CLOUD = "TIER_3_CLOUD"


class SearchMode(str, Enum):
    KEYWORD = "keyword"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"
    RESEARCH = "research"


class DocumentSourceType(str, Enum):
    CODE_REPO = "code_repo"
    MARKDOWN_NOTES = "markdown_notes"
    PDF = "pdf"
    DOCUMENT = "document"
    CHAT_HISTORY = "chat_history"
    BROWSER_PAGE = "browser_page"
    WEB_CACHE = "web_cache"
    NOTES = "notes"


# ─── Network & Browser Security Constants ───────────────────────────────────

BLOCKED_SSRF_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

DEFAULT_DUCKDUCKGO_SEARCH_URL = "https://html.duckduckgo.com/html/"


# ─── Desktop & Policy Defaults ──────────────────────────────────────────────

DEFAULT_APP_COMMANDS = {
    "vscode": "code",
    "chrome": "chrome",
    "terminal": "powershell",
    "notepad": "notepad",
    "calculator": "calc",
}

DEFAULT_POLICY_ALLOWED_APPS = [
    "notepad", "code", "cmd", "powershell", "explorer", "calculator", "terminal"
]

DEFAULT_POLICY_BLOCKED_APPS = [
    "regedit", "format", "crypto_wallet", "metamask"
]

DEFAULT_CRITICAL_KEYWORDS = [
    "drop database", "format disk", "wipe system", "trade crypto", "mint nft"
]

DEFAULT_HIGH_RISK_KEYWORDS = [
    "delete file", "rm -rf", "drop table", "send email", "post tweet", "curl -x post"
]

DEFAULT_MEDIUM_RISK_KEYWORDS = [
    "write file", "create directory", "npm install", "pip install"
]

DEFAULT_TIER2_KEYWORDS = [
    "delete file", "rm -rf", "send email", "post to", "purchase", "buy", "book flight",
    "push to main", "deploy to prod", "click on", "type password"
]

DEFAULT_TIER1_KEYWORDS = [
    "create draft", "write file", "save note", "test code", "ingest document"
]


# ─── Search Brain Defaults ──────────────────────────────────────────────────

DEFAULT_SOURCE_AUTHORITY: Dict[str, float] = {
    "code_repo": 1.25,
    "markdown_notes": 1.20,
    "pdf": 1.15,
    "document": 1.10,
    "chat_history": 1.05,
    "browser_page": 1.00,
    "web_cache": 0.90,
}

DEFAULT_PRICING_TABLE: Dict[str, Dict[str, float]] = {
    "ollama": {"input": 0.0, "output": 0.0},
    "vllm": {"input": 0.0, "output": 0.0},
    "openrouter/free": {"input": 0.0, "output": 0.0},
    "openrouter-free": {"input": 0.0, "output": 0.0},
    "claude-3-7-sonnet": {"input": 0.003, "output": 0.015},
    "gpt-4o": {"input": 0.0025, "output": 0.010},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gemini-2.0-flash": {"input": 0.0001, "output": 0.0004},
    "gemini-2.0-pro": {"input": 0.00125, "output": 0.005},
    "default_cloud": {"input": 0.003, "output": 0.015},
}


# ─── DLP & Sensitive Data Redaction Patterns ────────────────────────────────

DLP_PATTERNS = {
    "api_key_openai": (r"\bsk-[a-zA-Z0-9]{20,48}\b", "[REDACTED_OPENAI_KEY]"),
    "api_key_anthropic": (r"\bsk-ant-[a-zA-Z0-9_\-]{20,80}\b", "[REDACTED_CLAUDE_KEY]"),
    "api_key_aws": (r"\bAKIA[0-9A-Z]{16}\b", "[REDACTED_AWS_KEY]"),
    "api_key_github": (r"\bgh[pousr]_[a-zA-Z0-9]{36,255}\b", "[REDACTED_GITHUB_TOKEN]"),
    "private_key": (
        r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
        "[REDACTED_PRIVATE_KEY]",
    ),
    "credit_card": (
        r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|3(?:0[0-5]|[68][0-9])[0-9]{11}|6(?:011|5[0-9]{2})[0-9]{12}|(?:[0-9]{4}[ -]){3}[0-9]{4})\b",
        "[REDACTED_CREDIT_CARD]",
    ),
    "otp": (r"(?i)\b(?:otp|code|passcode|pin)[:\s=]+([0-9]{4,8})\b", "[REDACTED_OTP]"),
    "password_assign": (r"(?i)\b(?:password|passwd|pwd|secret)[:\s=]+(['\"][^'\"]+['\"]|\S+)", "[REDACTED_PASSWORD]"),
    "jwt_token": (r"\beyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\b", "[REDACTED_JWT]"),
    "ssn": (r"\b\d{3}-\d{2}-\d{4}\b", "[REDACTED_SSN]"),
}

INGESTION_REDACTION_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"sk-[A-Za-z0-9_-]{20,}", re.IGNORECASE), "[REDACTED_API_KEY]"),
    (re.compile(r"ghp_[A-Za-z0-9]{36}", re.IGNORECASE), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"AKIA[0-9A-Z]{16}", re.IGNORECASE), "[REDACTED_AWS_KEY]"),
    (re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}", re.IGNORECASE), "[REDACTED_JWT]"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]+?-----END [A-Z ]*PRIVATE KEY-----", re.MULTILINE), "[REDACTED_PRIVATE_KEY]"),
    (re.compile(r'(?i)(password|secret|passwd|token)\s*[:=]\s*["\']?([^"\s\',;]{4,})["\']?'), r"\1: [REDACTED_SECRET]"),
    (re.compile(r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12}|(?:[0-9]{4}[ -]){3}[0-9]{4})\b"), "[REDACTED_CARD_NUMBER]"),
]
