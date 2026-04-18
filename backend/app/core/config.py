"""Runtime configuration — tuned for the Supabase + Fireworks + Fly.io worker.

No AWS, no Cognito, no RDS, no Redis. This worker only needs:
- Supabase URL + service-role key (DB, Auth JWKS, Storage)
- Fireworks / Anthropic API keys for LLM calls
- Deepgram + Recall for transcription/bots
- OAuth client secrets for Zoom/Teams/Slack/Outlook
- Inngest keys for async dispatch
- Fernet key for encrypting stored OAuth refresh tokens
"""

from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_env: Literal["development", "staging", "production"] = "development"
    app_name: str = "Deal Companion"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000"

    # Supabase
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    supabase_jwt_jwks_url: str = ""   # usually {SUPABASE_URL}/auth/v1/.well-known/jwks.json

    # LLM — Fireworks (default)
    fireworks_api_key: str = ""

    # LLM — Anthropic (opt-in, gated by PREMIUM_LLM_ENABLED)
    premium_llm_enabled: bool = False
    anthropic_api_key: str = ""

    # Transcription & bots
    deepgram_api_key: str = ""
    recall_api_key: str = ""
    recall_webhook_secret: str = ""

    # Async jobs
    inngest_event_key: str = ""
    inngest_signing_key: str = ""

    # OAuth clients
    zoom_client_id: str = ""
    zoom_client_secret: str = ""
    zoom_webhook_secret_token: str = ""

    teams_client_id: str = ""
    teams_client_secret: str = ""
    teams_webhook_secret: str = ""

    slack_client_id: str = ""
    slack_client_secret: str = ""
    slack_signing_secret: str = ""

    outlook_client_id: str = ""
    outlook_client_secret: str = ""

    # Fernet key for integration_credentials.access_token_encrypted
    token_encryption_key: str = ""

    # Shared secret between Inngest functions (on Vercel) and the worker.
    # Every /api/v1/internal/* request must include this in X-Internal-Token.
    worker_internal_token: str = ""

    # Observability
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.1

    # ------------------------------------------------------------------
    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def jwks_url(self) -> str:
        if self.supabase_jwt_jwks_url:
            return self.supabase_jwt_jwks_url
        if self.supabase_url:
            return f"{self.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
        return ""

    # ------------------------------------------------------------------
    @model_validator(mode="after")
    def _require_prod_secrets(self) -> "Settings":
        """Fail fast in production if required runtime secrets are missing."""
        if not self.is_production:
            return self

        missing: list[str] = []
        if not self.supabase_url:
            missing.append("SUPABASE_URL")
        if not self.supabase_service_role_key:
            missing.append("SUPABASE_SERVICE_ROLE_KEY")
        if not self.token_encryption_key:
            missing.append("TOKEN_ENCRYPTION_KEY")
        if not self.fireworks_api_key:
            missing.append("FIREWORKS_API_KEY")

        if missing:
            raise ValueError(
                "Missing required production env vars: " + ", ".join(missing)
            )

        if self.token_encryption_key:
            try:
                from cryptography.fernet import Fernet

                Fernet(self.token_encryption_key.encode())
            except Exception as exc:  # noqa: BLE001
                raise ValueError(
                    f"token_encryption_key is not a valid Fernet key: {exc}"
                ) from exc

        if self.premium_llm_enabled and not self.anthropic_api_key:
            raise ValueError(
                "PREMIUM_LLM_ENABLED=true but ANTHROPIC_API_KEY is empty"
            )

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
