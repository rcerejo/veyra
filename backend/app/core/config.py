from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "VEYRA"
    database_path: Path = Path(__file__).resolve().parents[3] / "datasets" / "veyra.db"
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5-coder:1.5b"
    query_timeout_seconds: float = 8.0
    max_result_rows: int = 5000

    model_config = SettingsConfigDict(env_prefix="VEYRA_", env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()

