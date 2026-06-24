"""Pydantic settings configuration for Pulse."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    pulse_env: str = "development"
    pulse_debug: bool = True
    pulse_secret_key: str = "change-me-in-production"
    pulse_api_host: str = "0.0.0.0"
    pulse_api_port: int = 8000
    pulse_log_level: str = "info"

    # Database
    database_url: str = "postgresql+asyncpg://pulse:pulse@localhost:5432/pulse"
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # JWT / Auth
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30

    # Storage
    storage_endpoint: str | None = None
    storage_access_key: str | None = None
    storage_secret_key: str | None = None
    storage_bucket: str = "pulse"
    storage_region: str = "us-east-1"
    storage_use_ssl: bool = True

    # Vault integration
    vault_api_url: str | None = None
    vault_api_key: str | None = None

    # LLM providers
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    mistral_api_key: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_endpoint: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_region: str | None = None
    ollama_base_url: str | None = None
    vllm_base_url: str | None = None

    # Analytics
    segment_write_key: str | None = None
    ga4_measurement_id: str | None = None
    ga4_api_secret: str | None = None
    mixpanel_project_token: str | None = None

    # Webhooks
    webhook_signing_secret: str = "whsec_change_me"

    @property
    def is_development(self) -> bool:
        return self.pulse_env == "development"

    @property
    def is_production(self) -> bool:
        return self.pulse_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
