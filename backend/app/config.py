from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    gemini_api_key: str = ""
    replicate_api_token: str = ""
    mock_mode: bool | None = None
    default_pipeline: str = "edit"

    gemini_text_model: str = "gemini-2.5-flash"
    gemini_stylist_model: str = "gemini-2.5-pro"
    gemini_image_model: str = "gemini-2.5-flash-image"
    replicate_garment_model: str = "black-forest-labs/flux-schnell"
    replicate_vton_model: str = "cuuupid/idm-vton"
    replicate_restore_model: str = "sczhou/codeformer"

    retention_days: int = 30
    storage_dir: Path = BACKEND_DIR / "storage"
    cors_origins: str = "http://localhost:3000"

    @field_validator("mock_mode", mode="before")
    @classmethod
    def _blank_is_auto(cls, v):
        return None if v == "" else v

    @property
    def use_mock(self) -> bool:
        if self.mock_mode is not None:
            return self.mock_mode
        return not self.gemini_api_key

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
