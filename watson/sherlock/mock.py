"""Fixture-backed findings used by the synthetic dataset and tests."""

from collections.abc import Mapping

from switchboard_schemas.interpretations import IntelligenceFinding

from watson.models import CompletedCall


class FixtureFindingProvider:
    """Return prebuilt findings keyed by call id."""

    def __init__(self, findings_by_call: Mapping[str, list[IntelligenceFinding]]) -> None:
        self._findings = {call_id: list(findings) for call_id, findings in findings_by_call.items()}

    def findings_for(self, call: CompletedCall) -> list[IntelligenceFinding]:
        return list(self._findings.get(call.call_id, []))
