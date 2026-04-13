from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="AnonExplo Orchestrator", validation_alias="APP_NAME")
    api_prefix: str = Field(default="/api/v1", validation_alias="API_PREFIX")
    backend_host: str = Field(default="0.0.0.0", validation_alias="BACKEND_HOST")
    backend_port: int = Field(default=8000, validation_alias="BACKEND_PORT")
    cors_allowed_origins: str = Field(
        default="http://127.0.0.1:3000,http://localhost:3000",
        validation_alias="CORS_ALLOWED_ORIGINS",
    )

    model_provider: Literal["openai_compatible"] = Field(
        default="openai_compatible",
        validation_alias="MODEL_PROVIDER",
    )
    model_base_url: str = Field(
        default="http://model-backend:8080/v1",
        validation_alias="MODEL_BASE_URL",
    )
    model_name: str = Field(default="replace-with-local-model", validation_alias="MODEL_NAME")
    model_request_timeout_seconds: float = Field(
        default=90.0,
        validation_alias="MODEL_REQUEST_TIMEOUT_SECONDS",
    )

    search_provider: Literal["searxng"] = Field(
        default="searxng",
        validation_alias="SEARCH_PROVIDER",
    )
    search_base_url: str = Field(
        default="http://search-provider:8080",
        validation_alias="SEARCH_BASE_URL",
    )
    search_result_limit: int = Field(default=5, validation_alias="SEARCH_RESULT_LIMIT")
    search_request_timeout_seconds: float = Field(
        default=20.0,
        validation_alias="SEARCH_REQUEST_TIMEOUT_SECONDS",
    )

    fetch_base_url: str = Field(default="http://fetcher:8081", validation_alias="FETCH_BASE_URL")
    fetch_request_timeout_seconds: float = Field(
        default=20.0,
        validation_alias="FETCH_REQUEST_TIMEOUT_SECONDS",
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
