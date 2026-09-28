"""Application settings, loaded from environment variables (and backend/.env in development).

Production refuses to boot with unsafe settings (see `_production_guards`), so a missing secret
fails loudly at deploy time instead of silently weakening security.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]

TryOnAdapterName = Literal["auto", "mock", "gemini", "replicate", "remote"]
EmbeddingProvider = Literal["auto", "hash", "gemini", "replicate"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"

    # --- URLs -----------------------------------------------------------------
    app_url: str = "http://localhost:3000"  # public frontend origin
    api_url: str = "http://localhost:8000"  # public API origin
    cors_origins: str = ""  # extra comma-separated origins allowed to call the API

    # --- Data stores ----------------------------------------------------------
    # The API and workers connect with a least-privilege role (DML only).
    database_url: str = "postgresql+psycopg://lookbook_app:app_dev_pw@localhost:5432/lookbook"
    # Migrations run as the schema owner. Never give this URL to the running app.
    migration_database_url: str = (
        "postgresql+psycopg://lookbook_owner:owner_dev_pw@localhost:5432/lookbook"
    )
    app_db_role: str = "lookbook_app"
    redis_url: str = "redis://localhost:6379/0"
    celery_eager: bool = False  # run tasks inline (tests)

    # --- Secrets & sessions ---------------------------------------------------
    secret_key: str = "dev-only-insecure-secret-change-me"
    session_cookie_name: str = "lb_session"
    csrf_cookie_name: str = "lb_csrf"
    cookie_domain: str | None = None
    cookie_secure: bool | None = None  # default: True in production
    session_idle_hours: int = 24
    session_absolute_days: int = 7
    password_reset_ttl_minutes: int = 30
    force_https: bool | None = None  # default: True in production
    trust_proxy_headers: bool = False

    # --- Bot protection (Cloudflare Turnstile) ---------------------------------
    turnstile_secret_key: str = ""

    # --- Email ----------------------------------------------------------------
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = "LOOKBOOK <no-reply@lookbook.local>"

    # --- Object storage -------------------------------------------------------
    storage_backend: Literal["s3", "local"] = "local"
    local_storage_dir: Path = BACKEND_DIR / "storage"
    s3_endpoint_url: str | None = None  # e.g. http://localhost:8333 (SeaweedFS in docker compose), an R2 endpoint
    s3_public_endpoint_url: str | None = None  # endpoint browsers use for presigned URLs
    s3_region: str = "us-east-1"
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_bucket: str = "lookbook"
    s3_server_side_encryption: str | None = "AES256"
    max_upload_bytes: int = 10 * 1024 * 1024
    raw_upload_retention_days: int = 14
    result_retention_days: int = 90

    # --- AI providers ---------------------------------------------------------
    mock_mode: bool | None = None  # None = auto (mock when no provider keys)
    gemini_api_key: str = ""
    replicate_api_token: str = ""
    decart_api_key: str = ""
    gpu_worker_url: str = ""  # self-hosted CatVTON/IDM-VTON worker (see docs/gpu-worker.md)
    gpu_worker_token: str = ""
    tryon_adapter: TryOnAdapterName = "auto"
    embedding_provider: EmbeddingProvider = "auto"
    embedding_dim: int = 768

    gemini_text_model: str = "gemini-2.5-flash"
    gemini_stylist_model: str = "gemini-2.5-pro"
    gemini_image_model: str = "gemini-2.5-flash-image"
    gemini_embedding_model: str = "gemini-embedding-001"
    replicate_garment_model: str = "black-forest-labs/flux-schnell"
    replicate_vton_model: str = "cuuupid/idm-vton"
    replicate_restore_model: str = "sczhou/codeformer"
    replicate_clip_model: str = "andreasjansson/clip-features"
    live_model: str = "lucy-vton-latest"

    # --- Abuse & cost controls ------------------------------------------------
    rate_tryon_per_minute: int = 5
    rate_stylist_per_minute: int = 20
    rate_auth_per_15min: int = 10
    rate_live_token_per_minute: int = 3
    daily_tryons_per_user: int = 50
    daily_paid_call_budget: int = 1000  # across all users; new jobs refused beyond this
    alert_webhook_url: str = ""  # Slack/Discord-compatible webhook for spend and error alerts

    # --- Observability --------------------------------------------------------
    log_level: str = "INFO"
    log_json: bool | None = None  # default: True in production

    @field_validator("mock_mode", "cookie_secure", "force_https", "log_json", mode="before")
    @classmethod
    def _blank_is_none(cls, v):
        return None if v == "" else v

    @model_validator(mode="after")
    def _production_guards(self):
        if self.environment != "production":
            return self
        problems = []
        if len(self.secret_key) < 32 or "dev-only" in self.secret_key:
            problems.append("SECRET_KEY must be a random value of at least 32 characters")
        if not self.turnstile_secret_key:
            problems.append("TURNSTILE_SECRET_KEY is required (bot protection)")
        if not self.app_url.startswith("https://") or not self.api_url.startswith("https://"):
            problems.append("APP_URL and API_URL must be https:// in production")
        if self.cookie_secure is False or self.force_https is False:
            problems.append("COOKIE_SECURE and FORCE_HTTPS cannot be disabled in production")
        if "lookbook_owner" in self.database_url:
            problems.append("DATABASE_URL must use the least-privilege app role, not the owner")
        if not self.smtp_host:
            problems.append("SMTP_HOST is required so password reset emails can be delivered")
        if problems:
            raise ValueError("Unsafe production configuration: " + "; ".join(problems))
        return self

    # --- Derived --------------------------------------------------------------

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def secure_cookies(self) -> bool:
        return self.cookie_secure if self.cookie_secure is not None else self.is_production

    @property
    def https_only(self) -> bool:
        return self.force_https if self.force_https is not None else self.is_production

    @property
    def json_logs(self) -> bool:
        return self.log_json if self.log_json is not None else self.is_production

    @property
    def use_mock(self) -> bool:
        if self.mock_mode is not None:
            return self.mock_mode
        return not (self.gemini_api_key or self.replicate_api_token or self.gpu_worker_url)

    @property
    def allowed_origins(self) -> list[str]:
        extra = [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]
        return sorted({self.app_url.rstrip("/"), *extra})


@lru_cache
def get_settings() -> Settings:
    return Settings()

