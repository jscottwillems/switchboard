"""Process settings. The voice webhook, repositories, and event bus read these URLs."""

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    env: str
    contract_version: str
    internal_token: str
    cors_origins: tuple[str, ...]
    media_gateway_public_ws: str
    dev_webhook_bypass: bool
    health_probes: bool
    database_url: str
    redis_url: str


def _flag(name: str) -> bool:
    return os.environ.get(name, "").strip() == "1"


@lru_cache
def get_settings() -> Settings:
    origins = os.environ.get("SWITCHBOARD_CORS_ORIGINS", "http://localhost:5173")
    return Settings(
        env=os.environ.get("SWITCHBOARD_ENV", "dev"),
        contract_version=os.environ.get("SWITCHBOARD_CONTRACT_VERSION", "0.1.0"),
        internal_token=os.environ.get("SWITCHBOARD_INTERNAL_TOKEN", ""),
        cors_origins=tuple(origin.strip() for origin in origins.split(",") if origin.strip()),
        media_gateway_public_ws=os.environ.get(
            "MEDIA_GATEWAY_PUBLIC_WS",
            "ws://localhost:8001/v1/streams",
        ),
        dev_webhook_bypass=_flag("SWITCHBOARD_DEV_WEBHOOK_BYPASS"),
        health_probes=_flag("SWITCHBOARD_HEALTH_PROBES"),
        database_url=os.environ.get(
            "DATABASE_URL",
            "postgresql://switchboard:switchboard@localhost:5432/switchboard",
        ),
        redis_url=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
    )
