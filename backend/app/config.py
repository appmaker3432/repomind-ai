from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = ""
    openai_api_key: str = ""
    openai_model: str = ""
    request_timeout_seconds: float = 12.0
    max_analysis_seconds: float = 60.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
