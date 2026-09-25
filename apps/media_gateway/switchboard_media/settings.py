import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    redis_url: str
    api_base_url: str
    internal_token: str
    stream_token_timeout_s: float


@lru_cache
def get_settings() -> Settings:
    return Settings(
        redis_url=os.environ.get("REDIS_URL", ""),
        api_base_url=os.environ.get("API_BASE_URL", "http://localhost:8000"),
        internal_token=os.environ.get("SWITCHBOARD_INTERNAL_TOKEN", ""),
        stream_token_timeout_s=float(os.environ.get("STREAM_TOKEN_VALIDATE_TIMEOUT_S", "2")),
    )
