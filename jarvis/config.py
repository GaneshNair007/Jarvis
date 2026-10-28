"""
JARVIS Configuration Module
Manages all environment variables, provider endpoints, security thresholds,
and path definitions using Pydantic Settings.
"""

from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

# Base Directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    # App Settings
    jarvis_env: str = Field(default="development", description="Environment: development, test, production")
    jarvis_host: str = Field(default="127.0.0.1", description="Binding host")
    jarvis_port: int = Field(default=8000, description="Binding port")
    jarvis_debug: bool = Field(default=True, description="Debug mode")
    jarvis_secret_key: str = Field(default="dev_secret_key_change_in_production_32b", description="Secret key for HMAC and auth")
    jarvis_user_name: str = Field(default="Ganesh Nair", description="Primary authorized user name")
    jarvis_user_id: str = Field(default="ganesh", description="Primary user ID")

    # Tier 1: Local Reflex (Ollama)
    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_default_model: str = Field(default="llama3.2:3b")
    ollama_embed_model: str = Field(default="nomic-embed-text")
    ollama_timeout_sec: float = Field(default=30.0)

    # Tier 2: Private GPU Reasoning (vLLM OpenAI-Compatible Server)
    vllm_base_url: str = Field(default="http://localhost:8001/v1")
    vllm_api_key: str = Field(default="vllm-local-secret")
    vllm_default_model: str = Field(default="Qwen/Qwen2.5-32B-Instruct")
    vllm_timeout_sec: float = Field(default=60.0)

    # Tier 3: Frontier Cloud Gateway
    claude_api_key: Optional[str] = Field(default=None)
    openai_api_key: Optional[str] = Field(default=None)
    gemini_api_key: Optional[str] = Field(default=None)
    cloud_gateway_timeout_sec: float = Field(default=45.0)

    # Cost Governor Limits (USD)
    daily_budget_limit: float = Field(default=5.00)
    monthly_budget_limit: float = Field(default=50.00)
    max_per_task_budget: float = Field(default=0.50)

    # Security & Policy Settings
    policy_strict_mode: bool = Field(default=True)
    allow_unapproved_reads: bool = Field(default=True)
    approval_token_expiry_minutes: int = Field(default=15)
    kill_switch_hotkey: str = Field(default="ctrl+alt+shift+k")
    allowed_domains: List[str] = Field(default_factory=lambda: [
        "github.com", "arxiv.org", "wikipedia.org", "python.org", "pypi.org", "huggingface.co"
    ])
    allowed_directories: List[str] = Field(default_factory=lambda: [
        str(PROJECT_ROOT / "data"),
        str(PROJECT_ROOT / "scratch")
    ])

    # Storage Paths
    db_path: Path = Field(default=PROJECT_ROOT / "data" / "jarvis.db")
    audit_log_path: Path = Field(default=PROJECT_ROOT / "data" / "logs" / "audit.jsonl")
    screenshot_dir: Path = Field(default=PROJECT_ROOT / "data" / "screenshots")
    catalog_path: Path = Field(default=PROJECT_ROOT / "data" / "powers_catalog.json")

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def ensure_directories(self) -> None:
        """Create required runtime directories if they do not exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

# Global Settings Instance
settings = Settings()
settings.ensure_directories()
