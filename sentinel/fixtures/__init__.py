"""Adversarial corpora. Import from here or from tests.fixtures.adversarial.

Secrets in the webhook fixtures are placeholders for tests. Do not reuse them
as production credentials.
"""

from __future__ import annotations

from sentinel.fixtures.database_poisoning import DATABASE_POISONING
from sentinel.fixtures.model_output import MODEL_OUTPUT_FIXTURES
from sentinel.fixtures.prompt_injection import PROMPT_INJECTION_CORPUS
from sentinel.fixtures.provider_events import PROVIDER_EVENT_FIXTURES
from sentinel.fixtures.transcripts import MALICIOUS_TRANSCRIPTS
from sentinel.fixtures.urls import OUTBOUND_URL_FIXTURES
from sentinel.fixtures.webhook_attacks import (
    TEST_WEBHOOK_SECRET,
    WEBHOOK_ATTACK_FIXTURES,
    WEBHOOK_REPLAY_SAMPLE,
)

__all__ = [
    "DATABASE_POISONING",
    "MALICIOUS_TRANSCRIPTS",
    "MODEL_OUTPUT_FIXTURES",
    "OUTBOUND_URL_FIXTURES",
    "PROMPT_INJECTION_CORPUS",
    "PROVIDER_EVENT_FIXTURES",
    "TEST_WEBHOOK_SECRET",
    "WEBHOOK_ATTACK_FIXTURES",
    "WEBHOOK_REPLAY_SAMPLE",
]
