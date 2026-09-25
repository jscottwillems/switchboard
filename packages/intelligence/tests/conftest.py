"""Shared paths for Sherlock tests."""

import json
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = PACKAGE_ROOT / "fixtures" / "synthetic_transcripts.jsonl"


@pytest.fixture(scope="session")
def fixture_rows() -> list[dict[str, object]]:
    lines = FIXTURE_PATH.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]
