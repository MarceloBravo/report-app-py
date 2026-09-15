from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    service_port: int = 8000

    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini-2024-07-18"

    openai_api_key: str = ""
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"

    llm_timeout_seconds: float = 30.0
    llm_max_tokens: int = 2048

    max_schema_tables: int = 50
    max_schema_columns: int = 200
    max_prompt_chars: int = 8000

    cors_allowed_origins: str = "http://localhost:8080"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()