"""Shared operator credential for tests that call read routes."""

from switchboard_api.operator_auth import OPERATOR_TOKEN_HEADER

OPERATOR_TOKEN = "test-operator-token"
OPERATOR_HEADERS = {OPERATOR_TOKEN_HEADER: OPERATOR_TOKEN}
