from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings loaded from environment or .env file."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    APP_NAME: str = "GitGauge"
    DEBUG: bool = False
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # GitHub integration
    GITHUB_TOKEN: Optional[str] = None
    GITHUB_API_BASE_URL: str = "https://api.github.com"
    CACHE_TTL_SECONDS: int = 600  # 10 minutes cache for demo stability

    # Gemini AI integration
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.5-flash"


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
