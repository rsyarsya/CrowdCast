from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import json
import os

class Settings(BaseSettings):
    PROJECT_NAME: str = "CrowdCast API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # Security
    SECRET_KEY: str = "crowdcast-secret-key-super-secure-dteti-ugm"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  

    # Database
    DATABASE_URL: str = "sqlite:///./crowdcast.db"

    # Initial Superuser / Admin
    FIRST_SUPERUSER_EMAIL: str = "admin@crowdcast.local"
    FIRST_SUPERUSER_PASSWORD: str = "adminpassword123"

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, str) and v.startswith("["):
            return json.loads(v)
        return v

    # AI & Video Settings
    DEFAULT_YOLO_MODEL: str = "yolov8n.pt"
    DEVICE: str = ""  
    VIDEO_SAMPLE_PATH: str = "backend/data/videos/sample.mp4"

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()
