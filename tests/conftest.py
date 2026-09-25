"""Shared fixtures for the WATSON scoring tests."""

import pytest

from watson.config import ScoringConfig
from watson.synthetic import build_dataset


@pytest.fixture
def config() -> ScoringConfig:
    return ScoringConfig()


@pytest.fixture
def dataset():
    return build_dataset()
