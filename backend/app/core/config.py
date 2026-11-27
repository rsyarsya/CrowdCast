import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Application settings read from environment variables and backend/.env.

    Fields without a default are required: the app refuses to start when they
    are missing instead of silently running with insecure placeholder values.
    """

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    PROJECT_NAME: str = "CrowdCast API"
    API_V1_STR: str = "/api/v1"

    # Database
    DATABASE_URL: str
    DATABASE_ECHO: bool = False

    # Security
    SECRET_KEY: SecretStr
    ALGORITHM: str = "HS256"
    # One operator shift; users log in again afterwards (no refresh token).
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8

    # Initial administrator; only required by the seed script.
    FIRST_SUPERUSER_EMAIL: str | None = None
    FIRST_SUPERUSER_PASSWORD: SecretStr | None = None

    # CORS
    BACKEND_CORS_ORIGINS: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # Timestamps are stored in UTC and serialized by the API in this zone.
    TIMEZONE: str = "Asia/Jakarta"

    # Vision worker
    # Shared secret the worker sends in the X-Worker-Key header. When unset, the
    # ingest endpoints refuse every request.
    WORKER_API_KEY: SecretStr | None = None
    # Live state older than this is reported as stale (worker stopped or lagging).
    LIVE_STALE_SECONDS: int = 15
    # Lifetime of the ?ticket= used by <img> and EventSource; checked only on connect.
    STREAM_TICKET_SECONDS: int = 60
    # Comment line sent on idle event streams so proxies keep the connection open.
    SSE_HEARTBEAT_SECONDS: float = 15.0
    # Video file used by the seed script for the simulated demo camera.
    VIDEO_SAMPLE_PATH: str = "data/videos/sample.mp4"

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        """Accept a JSON list or a comma-separated string."""
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("["):
                return json.loads(value)
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings instance.

    Tests that change environment variables must call
    ``get_settings.cache_clear()`` afterwards.
    """
    return Settings()
