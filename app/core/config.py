from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""
    app_name: str = "AI SAT Math Coach"
    environment: str = "development"
    log_level: str = "INFO"
    database_url: str = "sqlite:///./sat_coach.db"
    diagnostic_provider: str = "rule_based"
    human_review_threshold: float = Field(0.60, ge=0, le=1)
    max_image_bytes: int = Field(5_242_880, ge=1)
    require_api_key: bool = False
    api_key: str | None = None
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

@lru_cache
def get_settings() -> Settings:
    return Settings()
