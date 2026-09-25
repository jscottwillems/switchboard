"""Copy provisional inputs into an evidence package.

Packaging checks that every child record belongs to a selected call. It does
not drop unknown records, promote raw observations, or invent campaign links.
"""

from __future__ import annotations

import hashlib
from typing import assert_never

from switchboard.clerk.adapters.upstream import (
    ObservationStatus,
    ProvisionalArtifact,
    ProvisionalBundle,
    ProvisionalCallSession,
    ProvisionalObservation,
    ProvisionalSpokenIdentifier,
)
from switchboard.clerk.errors import PackagingError
from switchboard.clerk.schemas.evidence import (
    Artifact,
    AssociationReason,
    CallEvidence,
    CallIdentity,
    CampaignAssociation,
    EvidencePackage,
    IncidentRecord,
    Observation,
    ReportedCallerMetadata,
    SpokenIdentifier,
    TranscriptExcerpt,
)
from switchboard.clerk.schemas.provenance import (
    PROVISIONAL_UPSTREAM_SCHEMA_ID,
    Confidence,
    ConfidenceLevel,
    EpistemicLayer,
    FactClass,
    SupportingTimestamp,
)


def _confidence(level: ConfidenceLevel, score: float, basis: str) -> Confidence:
    return Confidence(level=level, score=score, basis=basis)


def _classification(status: ObservationStatus) -> tuple[FactClass, EpistemicLayer, bool]:
    match status:
        case ObservationStatus.RAW:
            return (FactClass.RAW_OBSERVATION, EpistemicLayer.RAW_OBSERVATION, False)
        case ObservationStatus.CONFIRMED:
            return (FactClass.CONFIRMED_OBSERVATION, EpistemicLayer.RAW_OBSERVATION, True)
        case ObservationStatus.DERIVED:
            return (
                FactClass.DERIVED_INTERPRETATION,
                EpistemicLayer.DERIVED_INTERPRETATION,
                False,
            )
        case _ as unreachable:
            assert_never(unreachable)


def _require_known(label: str, record_id: str, call_id: str, known: set[str]) -> None:
    if call_id not in known:
        raise PackagingError(f"{label} {record_id} references call {call_id} outside the bundle")


def _artifact(source: ProvisionalArtifact) -> Artifact:
    sha256 = source.sha256
    if source.inline_text is not None:
        digest = hashlib.sha256(source.inline_text.encode("utf-8")).hexdigest()
        if sha256 is not None and sha256 != digest:
            raise PackagingError(f"Artifact {source.artifact_id} sha256 does not match inline_text")
        sha256 = digest
    return Artifact(
        artifact_id=source.artifact_id,
        call_id=source.call_id,
        kind=source.kind,
        label=source.label,
        uri=source.uri,
        media_type=source.media_type,
        inline_text=source.inline_text,
        sha256=sha256,
    )


def _spoken(source: ProvisionalSpokenIdentifier) -> SpokenIdentifier:
    return SpokenIdentifier(
        identifier_id=source.identifier_id,
        call_id=source.call_id,
        kind=source.kind,
        value=source.value,
        excerpt_id=source.excerpt_id,
        recorded_at=source.recorded_at,
        confidence=_confidence(
            source.confidence_level,
            source.confidence_score,
            source.confidence_basis,
        ),
    )


def _observation(source: ProvisionalObservation) -> Observation:
    fact_class, epistemic, confirmed = _classification(source.status)
    return Observation(
        observation_id=source.observation_id,
        call_id=source.call_id,
        category=source.category,
        statement=source.statement,
        confirmed=confirmed,
        fact_class=fact_class,
        epistemic=epistemic,
        confidence=_confidence(
            source.confidence_level,
            source.confidence_score,
            source.confidence_basis,
        ),
        recorded_at=source.recorded_at,
        supporting_excerpt_ids=list(source.supporting_excerpt_ids),
        supporting_artifact_ids=list(source.supporting_artifact_ids),
        supporting_timestamps=[
            SupportingTimestamp(
                source_id=source.observation_id,
                label="observation.recorded_at",
                at=source.recorded_at,
                call_id=source.call_id,
            )
        ],
    )


def _call(
    source: ProvisionalCallSession,
    spoken: list[SpokenIdentifier],
    observations: list[Observation],
) -> CallEvidence:
    return CallEvidence(
        identity=CallIdentity(call_id=source.call_id, session_id=source.session_id),
        started_at=source.started_at,
        ended_at=source.ended_at,
        duration_seconds=source.duration_seconds,
        reported_caller_metadata=ReportedCallerMetadata(
            displayed_caller_number=source.displayed_caller_number,
            displayed_caller_name=source.displayed_caller_name,
            displayed_callee_number=source.displayed_callee_number,
        ),
        transcript_excerpts=[
            TranscriptExcerpt(
                excerpt_id=excerpt.excerpt_id,
                call_id=source.call_id,
                speaker=excerpt.speaker,
                started_at=excerpt.started_at,
                ended_at=excerpt.ended_at,
                text=excerpt.text,
            )
            for excerpt in source.excerpts
        ],
        spoken_identifiers=spoken,
        observations=observations,
    )


def package_bundle(bundle: ProvisionalBundle) -> EvidencePackage:
    """Build an evidence package. Validation errors propagate from the schema."""

    if bundle.input_schema != PROVISIONAL_UPSTREAM_SCHEMA_ID:
        raise PackagingError("bundle input schema is not the CLERK provisional schema")
    known = {call.call_id for call in bundle.calls}
    if len(known) != len(bundle.calls):
        raise PackagingError("bundle contains a duplicate call id")
    for spoken in bundle.spoken_identifiers:
        _require_known("Spoken identifier", spoken.identifier_id, spoken.call_id, known)
    for observation in bundle.observations:
        _require_known("Observation", observation.observation_id, observation.call_id, known)
    for artifact in bundle.artifacts:
        _require_known("Artifact", artifact.artifact_id, artifact.call_id, known)

    spoken_by_call: dict[str, list[SpokenIdentifier]] = {call_id: [] for call_id in known}
    for spoken in bundle.spoken_identifiers:
        spoken_by_call[spoken.call_id].append(_spoken(spoken))
    observations_by_call: dict[str, list[Observation]] = {call_id: [] for call_id in known}
    for observation in bundle.observations:
        observations_by_call[observation.call_id].append(_observation(observation))

    campaign = None
    if bundle.campaign is not None:
        member_ids = list(bundle.campaign.member_call_ids)
        packaged_ids = [call_id for call_id in member_ids if call_id in known]
        if not packaged_ids:
            raise PackagingError("campaign membership does not include a packaged call")
        campaign = CampaignAssociation(
            campaign_id=bundle.campaign.campaign_id,
            label=bundle.campaign.label,
            member_call_ids=member_ids,
            packaged_call_ids=packaged_ids,
            reasons=[
                AssociationReason(
                    reason_id=reason.reason_id,
                    code=reason.code,
                    statement=reason.statement,
                    call_ids=list(reason.call_ids),
                    supporting_timestamps=[
                        SupportingTimestamp(
                            source_id=reason.reason_id,
                            label=stamp.label,
                            at=stamp.at,
                            call_id=stamp.call_id,
                            excerpt_id=stamp.excerpt_id,
                            artifact_id=stamp.artifact_id,
                        )
                        for stamp in reason.timestamps
                    ],
                    confidence=_confidence(
                        reason.confidence_level,
                        reason.confidence_score,
                        reason.confidence_basis,
                    ),
                )
                for reason in bundle.campaign.reasons
            ],
            confidence=_confidence(
                bundle.campaign.confidence_level,
                bundle.campaign.confidence_score,
                bundle.campaign.confidence_basis,
            ),
        )

    incident = None
    if bundle.incident is not None:
        if known.isdisjoint(bundle.incident.call_ids):
            raise PackagingError("incident call list does not include a packaged call")
        incident = IncidentRecord(
            incident_id=bundle.incident.incident_id,
            title=bundle.incident.title,
            summary=bundle.incident.summary,
            call_ids=list(bundle.incident.call_ids),
            technical_notes=list(bundle.incident.technical_notes),
        )

    return EvidencePackage(
        package_id=bundle.package_id,
        synthetic=bundle.synthetic,
        generated_at=bundle.generated_at,
        scope=bundle.scope,
        calls=[
            _call(call, spoken_by_call[call.call_id], observations_by_call[call.call_id])
            for call in bundle.calls
        ],
        artifacts=[_artifact(artifact) for artifact in bundle.artifacts],
        campaign=campaign,
        incident=incident,
    )
