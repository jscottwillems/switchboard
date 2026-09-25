"""Re-export of the adversarial corpora for agents that import the tests path.

The bytes and rows are the same objects as `sentinel.fixtures`.
"""

from __future__ import annotations

from sentinel.fixtures import (
    DATABASE_POISONING,
    MALICIOUS_TRANSCRIPTS,
    MODEL_OUTPUT_FIXTURES,
    OUTBOUND_URL_FIXTURES,
    PROMPT_INJECTION_CORPUS,
    PROVIDER_EVENT_FIXTURES,
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
