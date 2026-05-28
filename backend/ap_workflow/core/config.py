"""Configuration management for AP Workflow Agent."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra fields from .env file
    )

    # Application
    app_name: str = "AP Workflow Agent"
    app_version: str = "0.1.0"
    debug: bool = False
    environment: str = "development"

    # Database
    database_url: str = Field(
        default="postgresql://postgres:password@localhost:5432/ap_workflow"
    )
    database_pool_size: int = Field(default=10)
    database_max_overflow: int = Field(default=20)

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0")
    redis_pool_size: int = Field(default=10)

    # Supabase Storage
    supabase_url: str = Field(default="https://example.supabase.co")
    supabase_key: str = Field(default="")

    # Tesseract OCR
    tesseract_path: str = Field(default="tesseract")
    tesseract_timeout: int = Field(default=30)

    # ECB FX Rates
    ecb_api_url: str = Field(default="https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml")
    fx_rate_cache_ttl: int = Field(default=86400)  # 24 hours in seconds

    # LLM (NVIDIA NIM)
    llm_api_url: str = Field(default="https://integrate.api.nvidia.com/v1/chat/completions")
    llm_api_key: str = Field(default="")
    llm_model: str = Field(default="nvidia/nemotron-3-super-120b-a12b")
    llm_fallback_model: str = Field(default="meta/llama-3.3-70b-instruct")
    llm_rate_limit_rpm: int = Field(default=40)
    llm_queue_max_size: int = Field(default=1000)

    # Rate Limiting
    rate_limit_window_seconds: int = Field(default=60)

    # Duplicate Detection
    duplicate_detection_window_hours: int = Field(default=72)

    # Anomaly Detection
    zscore_threshold: float = Field(default=2.5)
    zscore_max_severity: float = Field(default=6.0)
    isolation_forest_n_estimators: int = Field(default=200)
    isolation_forest_contamination: float = Field(default=0.025)
    isolation_forest_retrain_interval_days: int = Field(default=7)

    # Auto-Approval
    default_auto_approve_max_amount: float = Field(default=10000.0)

    # SLA Deadlines
    ap_clerk_sla_hours: int = Field(default=24)
    manager_sla_hours: int = Field(default=8)
    cfo_sla_hours: int = Field(default=2)

    # JWT / Auth
    jwt_secret_key: str = Field(default="change-me-in-production")
    jwt_expire_hours: int = Field(default=24)

    # WebSocket
    websocket_ping_interval: int = Field(default=30)
    websocket_pong_timeout: int = Field(default=5)

    # Audit Logging
    audit_log_retention_days: int = Field(default=365)

    # Email (Gmail IMAP)
    gmail_imap_host: str = Field(default="imap.gmail.com")
    gmail_imap_port: int = Field(default=993)

    # ERP System
    erp_api_url: Optional[str] = Field(default=None)
    erp_api_key: Optional[str] = Field(default=None)

    # Circuit Breaker
    circuit_breaker_failure_threshold: int = Field(default=5)
    circuit_breaker_recovery_timeout_seconds: int = Field(default=60)


settings = Settings()
