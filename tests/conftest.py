import os
from collections.abc import Iterator

import pytest

from switchboard_api.memory_tokens import reset_token_store
from switchboard_api.settings import get_settings
from switchboard_api.webhook_edge import reset_webhook_edge
from switchboard_media.budgets import reset_limits
from tests.postgres_support import apply_migrations, truncate_observations

os.environ["SWITCHBOARD_ENV"] = "dev"
os.environ["SWITCHBOARD_DEV_WEBHOOK_BYPASS"] = "0"
os.environ["SWITCHBOARD_INTERNAL_TOKEN"] = "test-internal-token"
os.environ["SWITCHBOARD_CORS_ORIGINS"] = "http://localhost:5173"
os.environ["MEDIA_GATEWAY_PUBLIC_WS"] = "ws://localhost:8001/v1/streams"
os.environ["DATABASE_URL"] = "postgresql://switchboard:switchboard@localhost:5432/switchboard"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ.pop("SWITCHBOARD_HEALTH_PROBES", None)

_DATABASE_URL = os.environ["DATABASE_URL"]
_REDIS_URL = os.environ["REDIS_URL"]


@pytest.fixture(scope="session", autouse=True)
def _postgres_schema() -> None:
    apply_migrations()


@pytest.fixture(autouse=True)
def _reset_runtime() -> Iterator[None]:
    reset_token_store()
    reset_webhook_edge()
    reset_limits()
    get_settings.cache_clear()
    truncate_observations()
    yield
    os.environ["SWITCHBOARD_ENV"] = "dev"
    os.environ["SWITCHBOARD_DEV_WEBHOOK_BYPASS"] = "0"
    os.environ["DATABASE_URL"] = _DATABASE_URL
    os.environ["REDIS_URL"] = _REDIS_URL
    os.environ.pop("SWITCHBOARD_HEALTH_PROBES", None)
    reset_token_store()
    reset_webhook_edge()
    reset_limits()
    get_settings.cache_clear()
    truncate_observations()
