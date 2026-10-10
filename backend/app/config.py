from functools import lru_cache
from urllib.parse import urlsplit

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    frontend_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    request_timeout_seconds: float = 12.0
    max_analysis_seconds: float = 60.0


def parse_frontend_origins(value: str) -> list[str]:
    origins: list[str] = []
    for item in value.split(","):
        origin = item.strip().rstrip("/")
        if not origin:
            continue
        try:
            parsed = urlsplit(origin)
            port = parsed.port
        except ValueError as exc:
            raise ValueError("FRONTEND_ORIGINS must contain valid HTTP(S) origins.") from exc
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("FRONTEND_ORIGINS must contain only HTTP(S) origins, without paths or credentials.")
        origins.append(origin)
    if not origins:
        raise ValueError("FRONTEND_ORIGINS must contain at least one HTTP(S) origin.")
    return origins


@lru_cache
def get_settings() -> Settings:
    return Settings()
