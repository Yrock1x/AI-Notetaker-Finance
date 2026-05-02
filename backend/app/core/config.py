"""Runtime configuration — tuned for the Supabase + Fireworks + Railway worker.

No AWS, no Cognito, no RDS, no Redis. This worker only needs:
- Supabase URL + service-role key (DB, Auth JWKS, Storage)
- Fireworks / Anthropic API keys for LLM calls
- Deepgram + Recall for transcription/bots
- OAuth client secrets for Zoom, Microsoft (Teams + Outlook + Calendar), Google
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
    app_name: str = "CogniSuite"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000"
    # Regex applied to the Origin header in addition to ``cors_origins``.
    # Lets us cover Vercel preview deployments (each push gets a unique URL
    # like ``https://app-git-feature-team.vercel.app``) without enumerating
    # every one. Empty = no regex matching, only the explicit list applies.
    cors_origin_regex: str = ""

    # Supabase
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    supabase_jwt_jwks_url: str = ""   # usually {SUPABASE_URL}/auth/v1/.well-known/jwks.json
    # HS256 signing secret. Set in local dev (Supabase CLI issues HS256 tokens
    # by default) and as a fallback in prod if JWKS is unavailable. Hosted
    # Supabase exposes this as the "JWT Secret" in API settings.
    supabase_jwt_secret: str = ""

    # LLM — Fireworks (default)
    fireworks_api_key: str = ""

    # LLM — Anthropic (opt-in, gated by PREMIUM_LLM_ENABLED)
    premium_llm_enabled: bool = False
    anthropic_api_key: str = ""

    # Transcription & bots
    deepgram_api_key: str = ""
    recall_api_key: str = ""
    recall_webhook_secret: str = ""
    # Recall tokens are region-scoped — a key issued in us-east-1 gets 401 on
    # us-west-2 and vice versa. Default to us-west-2 for continuity; override
    # via env when the account lives elsewhere.
    recall_region: str = "us-west-2"

    # Async jobs
    inngest_event_key: str = ""
    inngest_signing_key: str = ""

    # OAuth clients
    zoom_client_id: str = ""
    zoom_client_secret: str = ""
    zoom_webhook_secret_token: str = ""

    # Microsoft (Teams + Outlook + Calendar — one OAuth app covers all three).
    # TEAMS_* aliases are accepted for backwards compatibility.
    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""
    microsoft_webhook_secret: str = ""  # clientState for Graph change notifications
    teams_client_id: str = ""
    teams_client_secret: str = ""
    teams_webhook_secret: str = ""

    # Google (Calendar + Meet).
    google_client_id: str = ""
    google_client_secret: str = ""

    slack_client_id: str = ""
    slack_client_secret: str = ""
    slack_signing_secret: str = ""

    # Public URL of the Next.js frontend — where we bounce users back after
    # the OAuth consent screen (e.g. https://app.example.com).
    frontend_url: str = "http://localhost:3000"

    # Public URL of THIS worker — used to build OAuth redirect_uri values the
    # provider will call after consent. On Railway this is the app's public
    # domain (https://<svc>.up.railway.app). Locally it's http://localhost:8000.
    public_api_url: str = "http://localhost:8000"

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
    def _alias_microsoft_from_teams(self) -> "Settings":
        """Backwards-compat: honour TEAMS_CLIENT_ID/_SECRET/_WEBHOOK_SECRET if
        the new MICROSOFT_* vars aren't populated. The single Microsoft OAuth
        app backs Teams, Outlook, and Calendar.
        """
        if not self.microsoft_client_id and self.teams_client_id:
            self.microsoft_client_id = self.teams_client_id
        if not self.microsoft_client_secret and self.teams_client_secret:
            self.microsoft_client_secret = self.teams_client_secret
        if not self.microsoft_webhook_secret and self.teams_webhook_secret:
            self.microsoft_webhook_secret = self.teams_webhook_secret
        return self

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
