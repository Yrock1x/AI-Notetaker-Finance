from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    app_env: Literal["development", "staging", "production"] = "development"
    app_name: str = "Deal Companion"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000"

    # Database
    database_url: str = "postgresql+asyncpg://dealwise:localdev@localhost:5432/dealwise"
    db_pool_size: int = 20
    db_max_overflow: int = 10

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # AWS S3
    s3_bucket_name: str = "dealwise-local"
    s3_endpoint_url: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_region: str = "us-east-1"

    # AWS Cognito
    cognito_user_pool_id: str = ""
    cognito_app_client_id: str = ""
    cognito_domain: str = ""

    # Supabase
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_jwt_secret: str = ""

    # LLM Providers
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""

    # Recall.ai
    recall_api_key: str = ""

    # Deepgram
    deepgram_api_key: str = ""

    # Encryption
    token_encryption_key: str = ""

    # Demo mode (bypasses Cognito auth for local/demo deployments)
    demo_mode: bool = False
    demo_jwt_secret: str = "demo-secret-change-in-production"

    # OAuth Client Credentials
    zoom_client_id: str = ""
    zoom_client_secret: str = ""
    teams_client_id: str = ""
    teams_client_secret: str = ""
    slack_client_id: str = ""
    slack_client_secret: str = ""
    outlook_client_id: str = ""
    outlook_client_secret: str = ""

    # Webhook Secrets
    zoom_webhook_secret_token: str = ""
    slack_signing_secret: str = ""
    teams_webhook_secret: str = ""

    @model_validator(mode="after")
    def validate_demo_mode(self) -> "Settings":
        if self.demo_mode:
            if self.demo_jwt_secret == "demo-secret-change-in-production":
                raise ValueError(
                    "demo_jwt_secret must be changed from the default value when demo_mode is enabled"
                )
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def async_database_url(self) -> str:
        url = self.database_url
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
