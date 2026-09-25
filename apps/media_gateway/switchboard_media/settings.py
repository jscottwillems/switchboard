import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    redis_url: str


@lru_cache
def get_settings() -> Settings:
    return Settings(redis_url=os.environ.get("REDIS_URL", ""))
