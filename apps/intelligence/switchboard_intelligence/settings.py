import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    internal_token: str
    database_url: str
    redis_url: str


@lru_cache
def get_settings() -> Settings:
    return Settings(
        internal_token=os.environ.get("SWITCHBOARD_INTERNAL_TOKEN", ""),
        database_url=os.environ.get("DATABASE_URL", ""),
        redis_url=os.environ.get("REDIS_URL", ""),
    )
