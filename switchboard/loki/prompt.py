"""Load the honeypot system prompt and check it against the state machine."""

from pathlib import Path

from switchboard.loki.goals import GOAL_ORDER
from switchboard.loki.schema import CANONICAL_TURN_FIELDS
from switchboard.loki.states import ConversationState

_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "system_prompt.md"

REQUIRED_PROMPT_SNIPPETS: tuple[str, ...] = (
    "Do not reveal",
    "honeypot",
    "one question",
    "response_text",
    "personal codes",
    "JSON",
    "verbatim",
    "strategy-decision confidence",
    "gift_card",
    "tech_support",
    "not an Observation",
    *(state.value for state in ConversationState),
    *GOAL_ORDER,
    *CANONICAL_TURN_FIELDS,
)


def load_system_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def prompt_contract_failures(prompt: str | None = None) -> list[str]:
    text = load_system_prompt() if prompt is None else prompt
    failures: list[str] = []
    if not text.strip():
        return ["system prompt is empty"]
    for snippet in REQUIRED_PROMPT_SNIPPETS:
        if snippet not in text:
            failures.append(f"system prompt is missing {snippet!r}")
    if "Ignore previous instructions" not in text and "ignore previous instructions" not in text.lower():
        failures.append("system prompt does not mention ignore-previous-instructions attacks")
    return failures
