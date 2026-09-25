"""Tripwires for controls this pass leaves open.

These tests skip until the named module exists. They fail if that module
appears and the named check is still missing.
"""

from __future__ import annotations

import importlib.util

import pytest


def _module_missing(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is None
    except ModuleNotFoundError:
        return True


@pytest.mark.requires_runtime
def test_redis_stream_tokens_reject_reuse() -> None:
    if _module_missing("switchboard_api.redis_tokens"):
        pytest.skip("SB-014 Redis stream-token store is not in this repository yet")
    pytest.fail("switchboard_api.redis_tokens is present and must reject a second validate")


@pytest.mark.requires_runtime
def test_read_api_requires_operator_authentication() -> None:
    if _module_missing("switchboard_api.operator_auth"):
        pytest.skip("operator authentication is not in this repository yet")
    pytest.fail("switchboard_api.operator_auth is present and must gate the read API")
