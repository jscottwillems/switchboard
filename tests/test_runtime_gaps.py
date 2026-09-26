"""Tripwires for controls this pass leaves open.

The Redis stream-token check skips until that module exists, and fails if
the module appears without the named check. Operator authentication is
implemented: the read-route check asserts the gate.
"""

from __future__ import annotations

import importlib.util
import os

import pytest
from fastapi.testclient import TestClient

from switchboard_api.main import app
from switchboard_api.operator_auth import OPERATOR_TOKEN_HEADER, require_operator
from switchboard_api.routes import calls, campaigns
from switchboard_api.settings import get_settings

from tests.operator_support import OPERATOR_TOKEN


def _module_missing(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is None
    except ModuleNotFoundError:
        return True


def _gated_by_operator(router: object) -> bool:
    dependencies = getattr(router, "dependencies", ())
    return any(getattr(item, "dependency", None) is require_operator for item in dependencies)


@pytest.mark.requires_runtime
def test_redis_stream_tokens_reject_reuse() -> None:
    if _module_missing("switchboard_api.redis_tokens"):
        pytest.skip("SB-014 Redis stream-token store is not in this repository yet")
    pytest.fail("switchboard_api.redis_tokens is present and must reject a second validate")


def test_read_api_requires_operator_authentication() -> None:
    """Missing and wrong tokens are 401. A matching token can read. Bypass does not open non-dev."""

    os.environ["SWITCHBOARD_ENV"] = "production"
    os.environ["SWITCHBOARD_OPERATOR_TOKEN"] = OPERATOR_TOKEN
    os.environ["SWITCHBOARD_DEV_OPERATOR_BYPASS"] = "1"
    get_settings.cache_clear()

    assert _gated_by_operator(calls.router)
    assert _gated_by_operator(campaigns.router)

    client = TestClient(app)
    for path in ("/v1/calls", "/v1/campaigns"):
        missing = client.get(path)
        assert missing.status_code == 401
        assert missing.json()["error"] == "operator_unauthorized"
        wrong = client.get(path, headers={OPERATOR_TOKEN_HEADER: "not-the-token"})
        assert wrong.status_code == 401
        assert wrong.json()["error"] == "operator_unauthorized"
        allowed = client.get(path, headers={OPERATOR_TOKEN_HEADER: OPERATOR_TOKEN})
        assert allowed.status_code == 200
