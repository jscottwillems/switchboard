import os

import pytest

from switchboard_api.memory_tokens import reset_token_store
from switchboard_api.settings import get_settings
from tests.postgres_support import apply_migrations, truncate_observations

os.environ["SWITCHBOARD_ENV"] = "dev"
os.environ["SWITCHBOARD_DEV_WEBHOOK_BYPASS"] = "0"
os.environ["SWITCHBOARD_INTERNAL_TOKEN"] = "test-internal-token"
os.environ["SWITCHBOARD_CORS_ORIGINS"] = "http://localhost:5173"
os.environ["MEDIA_GATEWAY_PUBLIC_WS"] = "ws://localhost:8001/v1/streams"
os.environ["DATABASE_URL"] = "postgresql://switchboard:switchboard@localhost:5432/switchboard"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

_DATABASE_URL = os.environ["DATABASE_URL"]
_REDIS_URL = os.environ["REDIS_URL"]


@pytest.fixture(scope="session", autouse=True)
def _postgres_schema() -> None:
    apply_migrations()


@pytest.fixture(autouse=True)
def _reset_runtime() -> None:
    reset_token_store()
    get_settings.cache_clear()
    truncate_observations()
    yield
    os.environ["SWITCHBOARD_ENV"] = "dev"
    os.environ["SWITCHBOARD_DEV_WEBHOOK_BYPASS"] = "0"
    os.environ["DATABASE_URL"] = _DATABASE_URL
    os.environ["REDIS_URL"] = _REDIS_URL
    reset_token_store()
    get_settings.cache_clear()
    truncate_observations()
