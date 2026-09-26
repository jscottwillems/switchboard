"""Campaign correlation port. Owner: WATSON. Proposes attribution, not findings.

SB-011 matches calls that share a `callback_number` E.164. The match lives in
this process. It does not read Redis and it does not write Postgres. SB-012
is the consumer that persists these proposals through `attribution_writer`.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Never, Protocol
from uuid import UUID, uuid5

from pydantic import Field, TypeAdapter, ValidationError

from switchboard_schemas.attribution import Campaign, CampaignAttribution
from switchboard_schemas.common import SWITCHBOARD_ID_NAMESPACE, E164, ContractModel
from switchboard_schemas.enums import CampaignStatus, FindingKind, FindingStatus
from switchboard_schemas.interpretations import IntelligenceFinding

# Contract example string. Names the rule, not a campaign id.
EXACT_CALLBACK_METHOD = "exact_callback_number"
EXACT_CALLBACK_METHOD_VERSION = "0.1.0"
# Certainty the strings were identical. Not a claim the cluster is a real campaign.
EXACT_CALLBACK_CONFIDENCE = 1.0

_E164 = TypeAdapter(E164)


class CorrelationInput(ContractModel):
    call_session_id: UUID
    findings: list[IntelligenceFinding] = Field(default_factory=list)


class CampaignCorrelator(Protocol):
    def propose(self, item: CorrelationInput) -> list[CampaignAttribution]:
        """Propose attributions that cite finding ids."""


class NullCampaignCorrelator:
    def propose(self, item: CorrelationInput) -> list[CampaignAttribution]:
        del item
        return []


@dataclass
class _SessionEvidence:
    call_session_id: UUID
    findings: dict[UUID, IntelligenceFinding] = field(default_factory=dict)


@dataclass
class _Cluster:
    value: str
    sessions: dict[UUID, _SessionEvidence] = field(default_factory=dict)
    campaign: Campaign | None = None
    attributions: dict[UUID, CampaignAttribution] = field(default_factory=dict)


class ExactCallbackCorrelator:
    """Group calls that share one callback_number E.164.

    A value stays unmatched until a second call session carries the same
    E.164. That match opens one `hypothesized` campaign and one attribution
    per session. A later call with that value joins the same campaign.
    Different values never share a campaign.
    """

    def __init__(self) -> None:
        self._clusters: dict[str, _Cluster] = {}

    def propose(self, item: CorrelationInput) -> list[CampaignAttribution]:
        """Return attributions created by this call.

        When this call is the one that opens a campaign, the list includes
        the attribution for each session already waiting on that number.
        A repeated propose for a session that is already attributed returns
        nothing and does not open another campaign.
        """

        grouped: dict[str, list[IntelligenceFinding]] = {}
        for finding in item.findings:
            value = _matching_callback(finding, item.call_session_id)
            if value is None:
                continue
            grouped.setdefault(value, []).append(finding)
        created: list[CampaignAttribution] = []
        for value in sorted(grouped):
            created.extend(self._propose_value(item.call_session_id, value, grouped[value]))
        created.sort(key=_attribution_order)
        return created

    def campaigns(self) -> list[Campaign]:
        opened: list[Campaign] = []
        for cluster in self._clusters.values():
            if cluster.campaign is not None:
                opened.append(cluster.campaign)
        return sorted(opened, key=lambda campaign: (campaign.created_at, str(campaign.id)))

    def attributions(self) -> list[CampaignAttribution]:
        rows = [row for cluster in self._clusters.values() for row in cluster.attributions.values()]
        return sorted(rows, key=_attribution_order)

    def _propose_value(
        self,
        call_session_id: UUID,
        value: str,
        findings: list[IntelligenceFinding],
    ) -> list[CampaignAttribution]:
        cluster = self._clusters.get(value)
        if cluster is not None and call_session_id in cluster.attributions:
            return []
        cluster = self._remember(call_session_id, value, findings)
        if cluster.campaign is None:
            if len(cluster.sessions) < 2:
                return []
            return self._open(cluster)
        evidence = cluster.sessions[call_session_id]
        attribution = _attribution(cluster.campaign, value, evidence)
        cluster.attributions[call_session_id] = attribution
        return [attribution]

    def _remember(
        self,
        call_session_id: UUID,
        value: str,
        findings: list[IntelligenceFinding],
    ) -> _Cluster:
        cluster = self._clusters.get(value)
        if cluster is None:
            cluster = _Cluster(value=value)
            self._clusters[value] = cluster
        evidence = cluster.sessions.get(call_session_id)
        if evidence is None:
            evidence = _SessionEvidence(call_session_id=call_session_id)
            cluster.sessions[call_session_id] = evidence
        for finding in findings:
            evidence.findings.setdefault(finding.id, finding)
        return cluster

    def _open(self, cluster: _Cluster) -> list[CampaignAttribution]:
        moments = [
            finding.created_at
            for evidence in cluster.sessions.values()
            for finding in evidence.findings.values()
        ]
        campaign = Campaign(
            id=_campaign_id(cluster.value),
            label=f"callback {cluster.value}",
            status=CampaignStatus.HYPOTHESIZED,
            summary=_summary(cluster.value),
            created_at=min(moments),
            updated_at=max(moments),
        )
        cluster.campaign = campaign
        created: list[CampaignAttribution] = []
        for evidence in _ordered_sessions(cluster):
            attribution = _attribution(campaign, cluster.value, evidence)
            cluster.attributions[evidence.call_session_id] = attribution
            created.append(attribution)
        return created


def _matching_callback(finding: IntelligenceFinding, call_session_id: UUID) -> str | None:
    if finding.call_session_id != call_session_id:
        return None
    if finding.kind is not FindingKind.CALLBACK_NUMBER:
        return None
    if not _status_counts(finding.status):
        return None
    try:
        return _E164.validate_python(finding.value)
    except ValidationError:
        return None


def _status_counts(status: FindingStatus) -> bool:
    match status:
        case FindingStatus.PROPOSED | FindingStatus.ACCEPTED:
            return True
        case FindingStatus.REJECTED:
            return False
        case _ as unexpected:
            return _unexpected_finding_status(unexpected)


def _unexpected_finding_status(status: Never) -> Never:
    raise RuntimeError(f"unhandled finding status: {status}")


def _campaign_id(value: str) -> UUID:
    return uuid5(SWITCHBOARD_ID_NAMESPACE, f"campaign|{EXACT_CALLBACK_METHOD}|{value}")


def _attribution_id(campaign_id: UUID, call_session_id: UUID) -> UUID:
    return uuid5(
        SWITCHBOARD_ID_NAMESPACE,
        f"campaign_attribution|{campaign_id}|{call_session_id}|{EXACT_CALLBACK_METHOD}",
    )


def _attribution(campaign: Campaign, value: str, evidence: _SessionEvidence) -> CampaignAttribution:
    findings = _ordered_findings(evidence)
    return CampaignAttribution(
        id=_attribution_id(campaign.id, evidence.call_session_id),
        campaign_id=campaign.id,
        call_session_id=evidence.call_session_id,
        supporting_finding_ids=[finding.id for finding in findings],
        method=EXACT_CALLBACK_METHOD,
        method_version=EXACT_CALLBACK_METHOD_VERSION,
        confidence=EXACT_CALLBACK_CONFIDENCE,
        rationale=_rationale(value),
        created_at=findings[0].created_at,
    )


def _ordered_sessions(cluster: _Cluster) -> list[_SessionEvidence]:
    return sorted(cluster.sessions.values(), key=_session_order)


def _session_order(evidence: _SessionEvidence) -> tuple[datetime, str]:
    earliest = _ordered_findings(evidence)[0].created_at
    return (earliest, str(evidence.call_session_id))


def _ordered_findings(evidence: _SessionEvidence) -> list[IntelligenceFinding]:
    return sorted(evidence.findings.values(), key=lambda finding: (finding.created_at, str(finding.id)))


def _attribution_order(attribution: CampaignAttribution) -> tuple[datetime, str]:
    return (attribution.created_at, str(attribution.id))


def _rationale(value: str) -> str:
    kind = FindingKind.CALLBACK_NUMBER.value
    return f"Exact match on {kind} value {value}. Confidence is 1.0 because the values are identical."


def _summary(value: str) -> str:
    kind = FindingKind.CALLBACK_NUMBER.value
    return f"Hypothesized from an exact match on {kind} value {value}."
