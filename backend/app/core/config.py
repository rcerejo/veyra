from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "VEYRA"
    database_path: Path = Path(__file__).resolve().parents[3] / "datasets" / "veyra.db"
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5-coder:1.5b"
    query_timeout_seconds: float = Field(default=8.0,gt=0,le=60)
    max_result_rows: int = Field(default=5000,ge=1,le=10000)
    environment: Literal['development','production'] = 'development'
    gateway_api_key: SecretStr | None = None
    allowed_hosts: list[str] = ['localhost','127.0.0.1','testserver']
    cors_origins: list[str] = ['http://localhost:5173','http://127.0.0.1:5173']
    max_concurrent_requests: int = Field(default=4,ge=1,le=64)
    enable_admin_jobs: bool = False

    @model_validator(mode='after')
    def production_configuration(self):
        if self.environment == 'production':
            if not self.gateway_api_key or len(self.gateway_api_key.get_secret_value()) < 32:
                raise ValueError('Production requires a gateway API key of at least 32 characters')
            if self.gateway_api_key.get_secret_value().startswith('REPLACE_'):
                raise ValueError('Replace the example gateway secret before starting production')
            if '*' in self.allowed_hosts or 'testserver' in self.allowed_hosts:
                raise ValueError('Production requires explicit allowed hosts without testserver or wildcards')
            if any(not origin.startswith('https://') for origin in self.cors_origins):
                raise ValueError('Production CORS origins must use HTTPS (or set an empty list for same-origin deployment)')
        return self

    model_config = SettingsConfigDict(env_prefix="VEYRA_", env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()

