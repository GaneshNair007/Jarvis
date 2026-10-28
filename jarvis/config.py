"""
JARVIS Centralized Configuration Module.
Typed configuration using Pydantic Settings. Manages all environment variables,
endpoints, secrets, timeouts, storage paths, limits, and runtime validation.
"""

import os
from pathlib import Path
from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base Directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Centralized, typed application settings."""

    # ─── Core Application Settings ──────────────────────────────────────────
    jarvis_env: str = Field(
        default="development",
        description="Environment: development, test, production",
    )
    jarvis_host: str = Field(default="127.0.0.1", description="Binding host")
    jarvis_port: int = Field(default=8000, description="Binding port")
    jarvis_debug: bool = Field(default=True, description="Debug mode")
    jarvis_secret_key: str = Field(
        default="dev_secret_key_change_in_production_32b",
        description="Secret key for HMAC signing and token auth",
    )
    jarvis_user_name: str = Field(default="Ganesh Nair", description="Primary authorized user name")
    jarvis_user_id: str = Field(default="ganesh", description="Primary user ID")
    cors_allow_origins: List[str] = Field(
        default_factory=lambda: ["*"],
        description="Allowed CORS origin domains",
    )
    disk_mount_path: str = Field(
        default="C:\\" if os.name == "nt" else "/",
        description="Root mount path for disk health inspection",
    )

    # ─── Tier 1: Local Reflex (Ollama) ──────────────────────────────────────
    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_default_model: str = Field(default="llama3.1")
    ollama_embed_model: str = Field(default="nomic-embed-text")
    ollama_timeout_sec: float = Field(default=30.0)

    # ─── Tier 2: Private GPU Reasoning (vLLM OpenAI-Compatible Server) ─────
    vllm_base_url: str = Field(default="http://localhost:8001/v1")
    vllm_api_key: Optional[str] = Field(default=None)
    vllm_default_model: str = Field(default="Qwen/Qwen2.5-32B-Instruct")
    vllm_timeout_sec: float = Field(default=60.0)

    # ─── LiteLLM Gateway & Local Model Alias ────────────────────────────────
    litellm_base_url: str = Field(default="http://localhost:4000")
    litellm_master_key: Optional[str] = Field(default=None)
    local_model: str = Field(default="ollama/llama3.1")

    # ─── Tier 3: Frontier Cloud Gateway & OpenRouter Free Tier ──────────────
    claude_api_key: Optional[str] = Field(default=None)
    openai_api_key: Optional[str] = Field(default=None)
    gemini_api_key: Optional[str] = Field(default=None)
    openrouter_api_key: Optional[str] = Field(default=None)
    openrouter_base_url: str = Field(default="https://openrouter.ai/api/v1")
    openrouter_default_model: str = Field(default="openrouter/free")
    cloud_gateway_timeout_sec: float = Field(default=45.0)

    # ─── Mem0 Long-Term Memory ──────────────────────────────────────────────
    mem0_api_key: Optional[str] = Field(default=None)
    mem0_user_id: Optional[str] = Field(default=None)

    # ─── Cost Governor Limits (USD) ─────────────────────────────────────────
    daily_budget_limit: float = Field(default=5.00)
    monthly_budget_limit: float = Field(default=50.00)
    max_per_task_budget: float = Field(default=0.50)

    # ─── Security & Policy Settings ─────────────────────────────────────────
    policy_strict_mode: bool = Field(default=True)
    allow_unapproved_reads: bool = Field(default=True)
    approval_token_expiry_minutes: int = Field(default=15)
    kill_switch_hotkey: str = Field(default="ctrl+alt+shift+k")
    allowed_domains: List[str] = Field(
        default_factory=lambda: [
            "github.com",
            "arxiv.org",
            "wikipedia.org",
            "python.org",
            "pypi.org",
            "huggingface.co",
        ]
    )
    allowed_directories: List[str] = Field(
        default_factory=lambda: [
            str(PROJECT_ROOT / "data"),
            str(PROJECT_ROOT / "scratch"),
        ]
    )

    # ─── Storage & Database Paths ───────────────────────────────────────────
    database_url: Optional[str] = Field(
        default=None,
        description="Optional PostgreSQL connection URL (defaults to local SQLite)",
    )
    db_path: Path = Field(default=PROJECT_ROOT / "data" / "jarvis.db")
    search_db_path: Path = Field(default=PROJECT_ROOT / "data" / "jarvis_search.db")
    audit_log_path: Path = Field(default=PROJECT_ROOT / "data" / "logs" / "audit.jsonl")
    screenshot_dir: Path = Field(default=PROJECT_ROOT / "data" / "screenshots")
    catalog_path: Path = Field(default=PROJECT_ROOT / "data" / "powers_catalog.json")
    jarvis_artifact_dir: Path = Field(default=PROJECT_ROOT / "data" / "artifacts")
    config_dir: Path = Field(default=PROJECT_ROOT / "config")

    # ─── Local Search Engine Settings ───────────────────────────────────────
    redis_url: str = Field(default="redis://localhost:6379/0")
    redis_socket_timeout_sec: float = Field(default=1.0)
    meilisearch_url: str = Field(default="http://localhost:7700")
    meilisearch_master_key: str = Field(default="masterKey123")
    qdrant_url: str = Field(default="http://localhost:6333")
    qdrant_collection: str = Field(default="jarvis_docs")
    searxng_url: str = Field(default="http://localhost:8888")
    search_cache_ttl_sec: int = Field(default=3600)

    # ─── Search Ranker & Ingestion Config ───────────────────────────────────
    rrf_k: int = Field(default=60)
    rrf_keyword_weight: float = Field(default=0.40)
    rrf_semantic_weight: float = Field(default=0.35)
    rrf_instant_weight: float = Field(default=0.25)
    ingest_chunk_size: int = Field(default=1200)
    ingest_chunk_overlap: int = Field(default=200)

    # ─── Browser & Desktop Worker Settings ──────────────────────────────────
    browser_headless: bool = Field(default=True)
    browser_timeout_ms: int = Field(default=15000)
    browser_search_timeout_sec: float = Field(default=10.0)
    desktop_action_pause_sec: float = Field(default=0.1)
    desktop_allowed_apps: List[str] = Field(
        default_factory=lambda: [
            "notepad",
            "code",
            "cmd",
            "powershell",
            "explorer",
            "calculator",
            "terminal",
        ]
    )

    # ─── Voice Engine Settings ──────────────────────────────────────────────
    voice_wake_phrases: List[str] = Field(
        default_factory=lambda: ["hey jarvis", "jarvis", "ok jarvis"]
    )
    voice_sensitivity: float = Field(default=0.5)
    voice_energy_threshold: float = Field(default=85.0)
    tts_speed: int = Field(default=1)
    tts_volume: int = Field(default=100)

    # ─── Pydantic Configuration ─────────────────────────────────────────────
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("jarvis_env")
    @classmethod
    def validate_env_mode(cls, v: str) -> str:
        valid_modes = {"development", "test", "production", "staging"}
        v_clean = v.strip().lower()
        if v_clean not in valid_modes:
            raise ValueError(
                f"Invalid JARVIS_ENV '{v}'. Must be one of: {', '.join(sorted(valid_modes))}"
            )
        return v_clean

    def ensure_directories(self) -> None:
        """Create required runtime directories if they do not exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.search_db_path.parent.mkdir(parents=True, exist_ok=True)
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self.jarvis_artifact_dir.mkdir(parents=True, exist_ok=True)

    def validate_startup(self) -> None:
        """
        Actionable startup verification for critical configuration keys.
        Ensures unsafe development secrets are not used in production.
        """
        self.ensure_directories()

        if self.jarvis_env == "production":
            insecure_secret = "dev_secret_key_change_in_production_32b"
            if self.jarvis_secret_key == insecure_secret or len(self.jarvis_secret_key) < 32:
                raise ValueError(
                    "STARTUP ERROR: Insecure or default JARVIS_SECRET_KEY detected in production. "
                    "Generate a cryptographically secure 32+ character key and set it in your environment."
                )

            if self.meilisearch_master_key == "masterKey123":
                raise ValueError(
                    "STARTUP ERROR: Default MEILISEARCH_MASTER_KEY ('masterKey123') detected in production. "
                    "Rotate MEILISEARCH_MASTER_KEY to a secure token in .env or your secret manager."
                )


# Global Settings Instance
settings = Settings()
settings.validate_startup()
