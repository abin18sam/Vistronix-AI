from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "sqlite:///./storage/vistronix.db"
    storage_root: Path = Path("storage")
    redis_url: str = "redis://localhost:6379/0"
    queue_mode: Literal["celery", "eager"] = "celery"
    enable_ocr: bool = True
    enable_table_extraction: bool = False
    enable_multimedia: bool = False
    max_upload_bytes: int = 50 * 1024 * 1024
    log_level: str = "INFO"
    llm_provider: str = "mock"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    llm_timeout_seconds: int = 60
    llm_max_retries: int = 3
    video_download_token: str = "dev-video-token"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    @property
    def documents_root(self) -> Path:
        return self.storage_root / "documents"


settings = Settings()
settings.storage_root.mkdir(parents=True, exist_ok=True)
settings.documents_root.mkdir(parents=True, exist_ok=True)
