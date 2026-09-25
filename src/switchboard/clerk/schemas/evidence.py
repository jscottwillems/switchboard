"""Canonical evidence package.

An evidence package is a closed copy of call records, observations, campaign
attribution, and incident records. Validators check internal references and
tag pairings. They do not decide whether an observation is true.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Literal, assert_never

from pydantic import Field, model_validator

from switchboard.clerk.schemas.provenance import (
    SCHEMA_VERSION,
    PROVISIONAL_UPSTREAM_SCHEMA_ID,
    AwareDatetime,
    ClerkModel,
    Confidence,
    EpistemicLayer,
    FactClass,
    NonEmptyStr,
    PackageScope,
    SupportingTimestamp,
    locked_pair,
)

_SHA256 = re.compile(r"[0-9a-f]{64}")


def _unique(values: list[str], label: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"duplicate {label}")


def _duration_matches(started_at: datetime, ended_at: datetime, seconds: int) -> None:
    actual = (ended_at - started_at).total_seconds()
    if actual != seconds:
        raise ValueError("duration_seconds does not match started_at and ended_at")


class ReportedCallerMetadata(ClerkModel):
    """Caller-ID and signaling display fields copied from the call record."""

    fact_class: Literal[FactClass.REPORTED_CALLER_METADATA] = FactClass.REPORTED_CALLER_METADATA
    epistemic: Literal[EpistemicLayer.RAW_OBSERVATION] = EpistemicLayer.RAW_OBSERVATION
    displayed_caller_number: NonEmptyStr | None = None
    displayed_caller_name: NonEmptyStr | None = None
    displayed_callee_number: NonEmptyStr | None = None

    @model_validator(mode="after")
    def _tags(self) -> ReportedCallerMetadata:
        locked_pair(self.fact_class, self.epistemic)
        return self


class TranscriptExcerpt(ClerkModel):
    excerpt_id: NonEmptyStr
    call_id: NonEmptyStr
    speaker: NonEmptyStr
    started_at: AwareDatetime
    ended_at: AwareDatetime | None = None
    text: NonEmptyStr
    fact_class: Literal[FactClass.RAW_OBSERVATION] = FactClass.RAW_OBSERVATION
    epistemic: Literal[EpistemicLayer.RAW_OBSERVATION] = EpistemicLayer.RAW_OBSERVATION

    @model_validator(mode="after")
    def _tags(self) -> TranscriptExcerpt:
        locked_pair(self.fact_class, self.epistemic)
        if self.ended_at is not None and self.ended_at < self.started_at:
            raise ValueError("excerpt ended_at is before started_at")
        return self


class SpokenIdentifier(ClerkModel):
    """An identifier copied from a transcript excerpt, separate from caller-ID."""

    identifier_id: NonEmptyStr
    call_id: NonEmptyStr
    kind: NonEmptyStr
    value: NonEmptyStr
    excerpt_id: NonEmptyStr
    recorded_at: AwareDatetime
    confidence: Confidence
    fact_class: Literal[FactClass.SPOKEN_IDENTIFIER] = FactClass.SPOKEN_IDENTIFIER
    epistemic: Literal[EpistemicLayer.RAW_OBSERVATION] = EpistemicLayer.RAW_OBSERVATION

    @model_validator(mode="after")
    def _tags(self) -> SpokenIdentifier:
        locked_pair(self.fact_class, self.epistemic)
        return self


class Observation(ClerkModel):
    """A structured observation or derived interpretation supplied with the call.

    `confirmed` is true only for fact class confirmed_observation. Derived
    interpretations stay unconfirmed and stay off the campaign-attribution layer.
    """

    observation_id: NonEmptyStr
    call_id: NonEmptyStr
    category: NonEmptyStr
    statement: NonEmptyStr
    confirmed: bool
    fact_class: FactClass
    epistemic: EpistemicLayer
    confidence: Confidence
    recorded_at: AwareDatetime
    supporting_excerpt_ids: list[NonEmptyStr] = Field(default_factory=list)
    supporting_artifact_ids: list[NonEmptyStr] = Field(default_factory=list)
    supporting_timestamps: list[SupportingTimestamp] = Field(default_factory=list)

    @model_validator(mode="after")
    def _tags(self) -> Observation:
        locked_pair(self.fact_class, self.epistemic)
        allowed = {
            (FactClass.CONFIRMED_OBSERVATION, True),
            (FactClass.RAW_OBSERVATION, False),
            (FactClass.DERIVED_INTERPRETATION, False),
        }
        if (self.fact_class, self.confirmed) not in allowed:
            raise ValueError("observation fact_class does not match confirmed")
        _unique(self.supporting_excerpt_ids, f"excerpt id on {self.observation_id}")
        _unique(self.supporting_artifact_ids, f"artifact id on {self.observation_id}")
        return self


class Artifact(ClerkModel):
    artifact_id: NonEmptyStr
    call_id: NonEmptyStr
    kind: NonEmptyStr
    label: NonEmptyStr
    uri: NonEmptyStr
    media_type: NonEmptyStr
    inline_text: str | None = None
    sha256: NonEmptyStr | None = None
    fact_class: Literal[FactClass.RAW_OBSERVATION] = FactClass.RAW_OBSERVATION
    epistemic: Literal[EpistemicLayer.RAW_OBSERVATION] = EpistemicLayer.RAW_OBSERVATION

    @model_validator(mode="after")
    def _tags(self) -> Artifact:
        locked_pair(self.fact_class, self.epistemic)
        if self.inline_text is not None and self.inline_text.strip() == "":
            raise ValueError("inline_text must not be empty")
        if self.inline_text is not None:
            digest = hashlib.sha256(self.inline_text.encode("utf-8")).hexdigest()
            if self.sha256 != digest:
                raise ValueError("artifact sha256 does not match inline_text")
        elif self.sha256 is not None and _SHA256.fullmatch(self.sha256) is None:
            raise ValueError("artifact sha256 must be 64 lowercase hex characters")
        return self


class AssociationReason(ClerkModel):
    reason_id: NonEmptyStr
    code: NonEmptyStr
    statement: NonEmptyStr
    call_ids: list[NonEmptyStr] = Field(min_length=1)
    supporting_timestamps: list[SupportingTimestamp] = Field(default_factory=list)
    confidence: Confidence
    fact_class: Literal[FactClass.DERIVED_ASSOCIATION] = FactClass.DERIVED_ASSOCIATION
    epistemic: Literal[EpistemicLayer.CAMPAIGN_ATTRIBUTION] = EpistemicLayer.CAMPAIGN_ATTRIBUTION

    @model_validator(mode="after")
    def _tags(self) -> AssociationReason:
        locked_pair(self.fact_class, self.epistemic)
        _unique(self.call_ids, f"call id on {self.reason_id}")
        return self


class CampaignAssociation(ClerkModel):
    """Campaign attribution copied from a campaign record.

    `member_call_ids` is the membership list as supplied. `packaged_call_ids`
    is that list filtered to calls that are actually in this package, in
    membership order. Absence of a call from this package is not a finding
    that the call is outside the campaign.
    """

    campaign_id: NonEmptyStr
    label: NonEmptyStr
    member_call_ids: list[NonEmptyStr] = Field(min_length=1)
    packaged_call_ids: list[NonEmptyStr] = Field(min_length=1)
    reasons: list[AssociationReason] = Field(default_factory=list)
    confidence: Confidence
    fact_class: Literal[FactClass.DERIVED_ASSOCIATION] = FactClass.DERIVED_ASSOCIATION
    epistemic: Literal[EpistemicLayer.CAMPAIGN_ATTRIBUTION] = EpistemicLayer.CAMPAIGN_ATTRIBUTION

    @model_validator(mode="after")
    def _tags(self) -> CampaignAssociation:
        locked_pair(self.fact_class, self.epistemic)
        _unique(self.member_call_ids, "campaign member call id")
        _unique(self.packaged_call_ids, "packaged campaign call id")
        _unique([reason.reason_id for reason in self.reasons], "association reason id")
        members = set(self.member_call_ids)
        if any(call_id not in members for call_id in self.packaged_call_ids):
            raise ValueError("packaged_call_ids must be a subset of member_call_ids")
        for reason in self.reasons:
            if any(call_id not in members for call_id in reason.call_ids):
                raise ValueError("association reason cites a call outside campaign membership")
        return self


class IncidentRecord(ClerkModel):
    """Technical incident record supplied with the package.

    The record is a derived interpretation. Raw signaling lines stay on
    artifacts and observations.
    """

    incident_id: NonEmptyStr
    title: NonEmptyStr
    summary: NonEmptyStr
    call_ids: list[NonEmptyStr] = Field(min_length=1)
    technical_notes: list[NonEmptyStr] = Field(default_factory=list)
    fact_class: Literal[FactClass.DERIVED_INTERPRETATION] = FactClass.DERIVED_INTERPRETATION
    epistemic: Literal[EpistemicLayer.DERIVED_INTERPRETATION] = (
        EpistemicLayer.DERIVED_INTERPRETATION
    )

    @model_validator(mode="after")
    def _tags(self) -> IncidentRecord:
        locked_pair(self.fact_class, self.epistemic)
        _unique(self.call_ids, "incident call id")
        return self


class CallIdentity(ClerkModel):
    call_id: NonEmptyStr
    session_id: NonEmptyStr | None = None


class CallEvidence(ClerkModel):
    identity: CallIdentity
    started_at: AwareDatetime
    ended_at: AwareDatetime
    duration_seconds: int = Field(ge=0)
    reported_caller_metadata: ReportedCallerMetadata
    transcript_excerpts: list[TranscriptExcerpt] = Field(default_factory=list)
    spoken_identifiers: list[SpokenIdentifier] = Field(default_factory=list)
    observations: list[Observation] = Field(default_factory=list)

    @model_validator(mode="after")
    def _duration(self) -> CallEvidence:
        if self.ended_at < self.started_at:
            raise ValueError("call ended_at is before started_at")
        _duration_matches(self.started_at, self.ended_at, self.duration_seconds)
        return self


class EvidencePackage(ClerkModel):
    """Portable evidence package produced by CLERK."""

    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    package_id: NonEmptyStr
    synthetic: bool
    generated_at: AwareDatetime
    generator: Literal["clerk"] = "clerk"
    upstream_input_schema: Literal["clerk.provisional_upstream.v0"] = (
        PROVISIONAL_UPSTREAM_SCHEMA_ID
    )
    scope: PackageScope
    calls: list[CallEvidence] = Field(min_length=1)
    artifacts: list[Artifact] = Field(default_factory=list)
    campaign: CampaignAssociation | None = None
    incident: IncidentRecord | None = None

    @model_validator(mode="after")
    def _package(self) -> EvidencePackage:
        call_ids = [call.identity.call_id for call in self.calls]
        _unique(call_ids, "call id")
        call_id_set = set(call_ids)
        self._check_scope(call_id_set)
        excerpt_owner = self._check_calls()
        artifact_owner = self._check_artifacts(call_id_set)
        self._check_observation_refs(excerpt_owner, artifact_owner)
        self._check_campaign(call_ids)
        self._check_incident(call_id_set)
        self._check_timestamp_refs(excerpt_owner)
        return self

    def _check_scope(self, call_id_set: set[str]) -> None:
        match self.scope:
            case PackageScope.SINGLE_CALL:
                if len(self.calls) != 1 or self.incident is not None:
                    raise ValueError("single_call scope requires one call and no incident record")
            case PackageScope.CAMPAIGN:
                if len(self.calls) < 2 or self.campaign is None or self.incident is not None:
                    raise ValueError(
                        "campaign scope requires two or more calls, a campaign, and no incident"
                    )
            case PackageScope.TECHNICAL_INCIDENT:
                if self.incident is None or self.campaign is not None:
                    raise ValueError(
                        "technical_incident scope requires an incident record and no campaign"
                    )
            case _ as unreachable:
                assert_never(unreachable)
        if self.campaign is not None and not call_id_set.intersection(self.campaign.member_call_ids):
            raise ValueError("campaign membership does not include a packaged call")

    def _check_calls(self) -> dict[str, str]:
        excerpt_owner: dict[str, str] = {}
        spoken_ids: list[str] = []
        observation_ids: list[str] = []
        for call in self.calls:
            call_id = call.identity.call_id
            excerpt_ids = [excerpt.excerpt_id for excerpt in call.transcript_excerpts]
            _unique(excerpt_ids, f"excerpt id on {call_id}")
            for excerpt in call.transcript_excerpts:
                if excerpt.call_id != call_id:
                    raise ValueError("excerpt call_id does not match the parent call")
                excerpt_owner[excerpt.excerpt_id] = call_id
            for spoken in call.spoken_identifiers:
                spoken_ids.append(spoken.identifier_id)
                if spoken.call_id != call_id:
                    raise ValueError("spoken identifier call_id does not match the parent call")
                if excerpt_owner.get(spoken.excerpt_id) != call_id:
                    raise ValueError("spoken identifier excerpt is not on the same call")
            for observation in call.observations:
                observation_ids.append(observation.observation_id)
                if observation.call_id != call_id:
                    raise ValueError("observation call_id does not match the parent call")
        if len(excerpt_owner) != sum(len(call.transcript_excerpts) for call in self.calls):
            raise ValueError("duplicate excerpt id")
        _unique(spoken_ids, "spoken identifier id")
        _unique(observation_ids, "observation id")
        return excerpt_owner

    def _check_artifacts(self, call_id_set: set[str]) -> dict[str, str]:
        _unique([artifact.artifact_id for artifact in self.artifacts], "artifact id")
        owner: dict[str, str] = {}
        for artifact in self.artifacts:
            if artifact.call_id not in call_id_set:
                raise ValueError("artifact call_id is not in the package")
            owner[artifact.artifact_id] = artifact.call_id
        return owner

    def _check_observation_refs(
        self,
        excerpt_owner: dict[str, str],
        artifact_owner: dict[str, str],
    ) -> None:
        for call in self.calls:
            call_id = call.identity.call_id
            for observation in call.observations:
                for excerpt_id in observation.supporting_excerpt_ids:
                    if excerpt_owner.get(excerpt_id) != call_id:
                        raise ValueError("observation excerpt is not on the same call")
                for artifact_id in observation.supporting_artifact_ids:
                    if artifact_owner.get(artifact_id) != call_id:
                        raise ValueError("observation artifact is not on the same call")
                for stamp in observation.supporting_timestamps:
                    if stamp.source_id != observation.observation_id:
                        raise ValueError("observation timestamp source_id must be the observation id")
                    if stamp.call_id not in (None, call_id):
                        raise ValueError("observation timestamp call_id does not match")

    def _check_campaign(self, call_ids: list[str]) -> None:
        campaign = self.campaign
        if campaign is None:
            return
        expected = [call_id for call_id in campaign.member_call_ids if call_id in set(call_ids)]
        if campaign.packaged_call_ids != expected:
            raise ValueError("packaged_call_ids must list packaged members in membership order")
        members = set(campaign.member_call_ids)
        if self.scope == PackageScope.CAMPAIGN and any(call_id not in members for call_id in call_ids):
            raise ValueError("campaign package contains a call outside campaign membership")
        if self.scope == PackageScope.SINGLE_CALL and call_ids[0] not in campaign.member_call_ids:
            raise ValueError("single-call campaign association must include that call")

    def _check_incident(self, call_id_set: set[str]) -> None:
        incident = self.incident
        if incident is None:
            return
        if any(call_id not in set(incident.call_ids) for call_id in call_id_set):
            raise ValueError("incident package contains a call outside the incident call list")

    def _check_timestamp_refs(self, excerpt_owner: dict[str, str]) -> None:
        campaign = self.campaign
        if campaign is None:
            return
        for reason in campaign.reasons:
            allowed = set(reason.call_ids)
            for stamp in reason.supporting_timestamps:
                if stamp.source_id != reason.reason_id:
                    raise ValueError("reason timestamp source_id must be the reason id")
                if stamp.call_id is not None and stamp.call_id not in allowed:
                    raise ValueError("reason timestamp call_id is outside the reason")
                owner = excerpt_owner.get(stamp.excerpt_id or "")
                if stamp.excerpt_id is not None and owner is not None and stamp.call_id not in (None, owner):
                    raise ValueError("reason timestamp excerpt belongs to a different call")
