"""Provisional inputs for packaging.

SHERLOCK's observation schema, WATSON's campaign schema, and the platform
CallSession schema are not in this repository. These models are a CLERK-local
mock of the fields packaging needs. They are not those shared schemas.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import Field

from switchboard.clerk.errors import PackagingError
from switchboard.clerk.schemas.provenance import (
    PROVISIONAL_UPSTREAM_SCHEMA_ID,
    AwareDatetime,
    ClerkModel,
    ConfidenceLevel,
    NonEmptyStr,
    PackageScope,
    UnitScore,
)


class ObservationStatus(str, Enum):
    RAW = "raw"
    CONFIRMED = "confirmed"
    DERIVED = "derived"


class ProvisionalExcerpt(ClerkModel):
    excerpt_id: NonEmptyStr
    speaker: NonEmptyStr
    started_at: AwareDatetime
    ended_at: AwareDatetime | None = None
    text: NonEmptyStr


class ProvisionalCallSession(ClerkModel):
    """Mock stand-in for the missing CallSession schema."""

    call_id: NonEmptyStr
    session_id: NonEmptyStr | None = None
    started_at: AwareDatetime
    ended_at: AwareDatetime
    duration_seconds: int = Field(ge=0)
    displayed_caller_number: NonEmptyStr | None = None
    displayed_caller_name: NonEmptyStr | None = None
    displayed_callee_number: NonEmptyStr | None = None
    excerpts: list[ProvisionalExcerpt] = Field(default_factory=list)


class ProvisionalSpokenIdentifier(ClerkModel):
    identifier_id: NonEmptyStr
    call_id: NonEmptyStr
    kind: NonEmptyStr
    value: NonEmptyStr
    excerpt_id: NonEmptyStr
    recorded_at: AwareDatetime
    confidence_level: ConfidenceLevel
    confidence_score: UnitScore
    confidence_basis: NonEmptyStr


class ProvisionalObservation(ClerkModel):
    """Mock stand-in for the missing SHERLOCK observation schema."""

    observation_id: NonEmptyStr
    call_id: NonEmptyStr
    category: NonEmptyStr
    statement: NonEmptyStr
    status: ObservationStatus
    confidence_level: ConfidenceLevel
    confidence_score: UnitScore
    confidence_basis: NonEmptyStr
    recorded_at: AwareDatetime
    supporting_excerpt_ids: list[NonEmptyStr] = Field(default_factory=list)
    supporting_artifact_ids: list[NonEmptyStr] = Field(default_factory=list)


class ProvisionalArtifact(ClerkModel):
    artifact_id: NonEmptyStr
    call_id: NonEmptyStr
    kind: NonEmptyStr
    label: NonEmptyStr
    uri: NonEmptyStr
    media_type: NonEmptyStr
    inline_text: str | None = None
    sha256: NonEmptyStr | None = None


class ProvisionalTimestamp(ClerkModel):
    label: NonEmptyStr
    at: AwareDatetime
    call_id: NonEmptyStr | None = None
    excerpt_id: NonEmptyStr | None = None
    artifact_id: NonEmptyStr | None = None


class ProvisionalAssociationReason(ClerkModel):
    reason_id: NonEmptyStr
    code: NonEmptyStr
    statement: NonEmptyStr
    call_ids: list[NonEmptyStr] = Field(min_length=1)
    timestamps: list[ProvisionalTimestamp] = Field(default_factory=list)
    confidence_level: ConfidenceLevel
    confidence_score: UnitScore
    confidence_basis: NonEmptyStr


class ProvisionalCampaign(ClerkModel):
    """Mock stand-in for the missing WATSON campaign schema."""

    campaign_id: NonEmptyStr
    label: NonEmptyStr
    member_call_ids: list[NonEmptyStr] = Field(min_length=1)
    reasons: list[ProvisionalAssociationReason] = Field(default_factory=list)
    confidence_level: ConfidenceLevel
    confidence_score: UnitScore
    confidence_basis: NonEmptyStr


class ProvisionalIncident(ClerkModel):
    incident_id: NonEmptyStr
    title: NonEmptyStr
    summary: NonEmptyStr
    call_ids: list[NonEmptyStr] = Field(min_length=1)
    technical_notes: list[NonEmptyStr] = Field(default_factory=list)


class ProvisionalBundle(ClerkModel):
    """One packaging request. Scope selects which optional records are included."""

    package_id: NonEmptyStr
    synthetic: bool
    generated_at: AwareDatetime
    scope: PackageScope
    input_schema: Literal["clerk.provisional_upstream.v0"] = PROVISIONAL_UPSTREAM_SCHEMA_ID
    calls: list[ProvisionalCallSession] = Field(min_length=1)
    spoken_identifiers: list[ProvisionalSpokenIdentifier] = Field(default_factory=list)
    observations: list[ProvisionalObservation] = Field(default_factory=list)
    artifacts: list[ProvisionalArtifact] = Field(default_factory=list)
    campaign: ProvisionalCampaign | None = None
    incident: ProvisionalIncident | None = None


class ProvisionalWorld(ClerkModel):
    """Synthetic world the fixture slices into packages. Not a shared schema."""

    synthetic: Literal[True] = True
    generated_at: AwareDatetime
    input_schema: Literal["clerk.provisional_upstream.v0"] = PROVISIONAL_UPSTREAM_SCHEMA_ID
    calls: list[ProvisionalCallSession] = Field(min_length=1)
    spoken_identifiers: list[ProvisionalSpokenIdentifier] = Field(default_factory=list)
    observations: list[ProvisionalObservation] = Field(default_factory=list)
    artifacts: list[ProvisionalArtifact] = Field(default_factory=list)
    campaign: ProvisionalCampaign
    incident: ProvisionalIncident

    def slice(
        self,
        *,
        package_id: str,
        scope: PackageScope,
        call_ids: list[str],
        include_campaign: bool,
        include_incident: bool,
    ) -> ProvisionalBundle:
        by_id = {call.call_id: call for call in self.calls}
        missing = [call_id for call_id in call_ids if call_id not in by_id]
        if missing:
            raise PackagingError(f"Unknown call ids: {', '.join(missing)}")
        selected = set(call_ids)
        campaign = self.campaign if include_campaign else None
        incident = self.incident if include_incident else None
        if campaign is not None and selected.isdisjoint(campaign.member_call_ids):
            raise PackagingError("Selected calls are outside the campaign membership list")
        if incident is not None and selected.isdisjoint(incident.call_ids):
            raise PackagingError("Selected calls are outside the incident call list")
        return ProvisionalBundle(
            package_id=package_id,
            synthetic=self.synthetic,
            generated_at=self.generated_at,
            scope=scope,
            calls=[by_id[call_id] for call_id in call_ids],
            spoken_identifiers=[
                item for item in self.spoken_identifiers if item.call_id in selected
            ],
            observations=[item for item in self.observations if item.call_id in selected],
            artifacts=[item for item in self.artifacts if item.call_id in selected],
            campaign=campaign,
            incident=incident,
        )
