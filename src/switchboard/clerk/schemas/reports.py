"""Report documents projected from an evidence package."""

from __future__ import annotations

from enum import Enum
from typing import Literal, assert_never

from pydantic import Field, model_validator

from switchboard.clerk.schemas.evidence import EvidencePackage
from switchboard.clerk.schemas.provenance import (
    SCHEMA_VERSION,
    SYNTHETIC_BANNER,
    UNMARKED_BANNER,
    AwareDatetime,
    ClerkModel,
    ConfidenceLevel,
    EpistemicLayer,
    FactClass,
    NonEmptyStr,
    PackageScope,
    UnitScore,
    locked_pair,
)


class ReportKind(str, Enum):
    SINGLE_CALL = "single_call"
    MULTI_CALL_CAMPAIGN = "multi_call_campaign"
    TECHNICAL_INCIDENT = "technical_incident"
    MACHINE_READABLE_JSON = "machine_readable_json"


class ReportSectionId(str, Enum):
    PROVENANCE_LEGEND = "provenance_legend"
    INCIDENT_RECORD = "incident_record"
    CALL_IDENTITY = "call_identity"
    TIMESTAMP = "timestamp"
    DISPLAYED_CALLER_METADATA = "displayed_caller_metadata"
    CALL_DURATION = "call_duration"
    TRANSCRIPT_EXCERPTS = "transcript_excerpts"
    SPOKEN_IDENTIFIERS = "spoken_identifiers"
    STRUCTURED_OBSERVATIONS = "structured_observations"
    CAMPAIGN_ASSOCIATION = "campaign_association"
    ASSOCIATION_REASONS = "association_reasons"
    SUPPORTING_TIMESTAMPS = "supporting_timestamps"
    RELEVANT_ARTIFACTS = "relevant_artifacts"
    CONFIDENCE_LEVELS = "confidence_levels"


REQUIRED_SECTION_IDS: tuple[ReportSectionId, ...] = (
    ReportSectionId.PROVENANCE_LEGEND,
    ReportSectionId.CALL_IDENTITY,
    ReportSectionId.TIMESTAMP,
    ReportSectionId.DISPLAYED_CALLER_METADATA,
    ReportSectionId.CALL_DURATION,
    ReportSectionId.TRANSCRIPT_EXCERPTS,
    ReportSectionId.SPOKEN_IDENTIFIERS,
    ReportSectionId.STRUCTURED_OBSERVATIONS,
    ReportSectionId.CAMPAIGN_ASSOCIATION,
    ReportSectionId.ASSOCIATION_REASONS,
    ReportSectionId.SUPPORTING_TIMESTAMPS,
    ReportSectionId.RELEVANT_ARTIFACTS,
    ReportSectionId.CONFIDENCE_LEVELS,
)


def section_title(section_id: ReportSectionId) -> str:
    match section_id:
        case ReportSectionId.PROVENANCE_LEGEND:
            return "Provenance legend"
        case ReportSectionId.INCIDENT_RECORD:
            return "Incident record"
        case ReportSectionId.CALL_IDENTITY:
            return "Call identity"
        case ReportSectionId.TIMESTAMP:
            return "Timestamp"
        case ReportSectionId.DISPLAYED_CALLER_METADATA:
            return "Displayed caller metadata"
        case ReportSectionId.CALL_DURATION:
            return "Call duration"
        case ReportSectionId.TRANSCRIPT_EXCERPTS:
            return "Transcript excerpts"
        case ReportSectionId.SPOKEN_IDENTIFIERS:
            return "Spoken identifiers"
        case ReportSectionId.STRUCTURED_OBSERVATIONS:
            return "Structured observations"
        case ReportSectionId.CAMPAIGN_ASSOCIATION:
            return "Campaign association"
        case ReportSectionId.ASSOCIATION_REASONS:
            return "Association reasons"
        case ReportSectionId.SUPPORTING_TIMESTAMPS:
            return "Supporting timestamps"
        case ReportSectionId.RELEVANT_ARTIFACTS:
            return "Relevant artifacts"
        case ReportSectionId.CONFIDENCE_LEVELS:
            return "Confidence levels"
        case _ as unreachable:
            assert_never(unreachable)


def kind_for_scope(scope: PackageScope) -> ReportKind:
    match scope:
        case PackageScope.SINGLE_CALL:
            return ReportKind.SINGLE_CALL
        case PackageScope.CAMPAIGN:
            return ReportKind.MULTI_CALL_CAMPAIGN
        case PackageScope.TECHNICAL_INCIDENT:
            return ReportKind.TECHNICAL_INCIDENT
        case _ as unreachable:
            assert_never(unreachable)


class ReportField(ClerkModel):
    name: NonEmptyStr
    value: NonEmptyStr


class ReportEntry(ClerkModel):
    entry_id: NonEmptyStr | None = None
    fact_class: FactClass | None = None
    epistemic: EpistemicLayer | None = None
    confirmed: bool | None = None
    fields: list[ReportField] = Field(default_factory=list)

    @model_validator(mode="after")
    def _pair(self) -> ReportEntry:
        if (self.fact_class is None) != (self.epistemic is None):
            raise ValueError("fact_class and epistemic must be set together")
        if self.fact_class is not None and self.epistemic is not None:
            locked_pair(self.fact_class, self.epistemic)
        return self


class ReportSection(ClerkModel):
    section_id: ReportSectionId
    title: NonEmptyStr
    empty: bool
    entries: list[ReportEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def _empty(self) -> ReportSection:
        if self.title != section_title(self.section_id):
            raise ValueError("section title does not match section id")
        if self.empty != (len(self.entries) == 0):
            raise ValueError("empty must match whether entries are present")
        return self


class ReportDocument(ClerkModel):
    """Structured report. Renderers copy these fields and do not add call facts."""

    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    report_id: NonEmptyStr
    kind: ReportKind
    scope: PackageScope
    package_id: NonEmptyStr
    synthetic: bool
    title: NonEmptyStr
    banner: NonEmptyStr
    upstream_input_schema: Literal["clerk.provisional_upstream.v0"]
    sections: list[ReportSection] = Field(min_length=1)

    @model_validator(mode="after")
    def _shape(self) -> ReportDocument:
        if self.kind == ReportKind.MACHINE_READABLE_JSON:
            raise ValueError("machine-readable export is not a report document")
        if self.kind != kind_for_scope(self.scope):
            raise ValueError("report kind does not match package scope")
        if self.report_id != f"{self.package_id}__{self.kind.value}":
            raise ValueError("report_id must be package_id__kind")
        expected_banner = SYNTHETIC_BANNER if self.synthetic else UNMARKED_BANNER
        if self.banner != expected_banner:
            raise ValueError("banner does not match the synthetic flag")
        ids = [section.section_id for section in self.sections]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate report section")
        if ids[0] != ReportSectionId.PROVENANCE_LEGEND:
            raise ValueError("provenance legend must be the first section")
        body = [section_id for section_id in ids if section_id != ReportSectionId.INCIDENT_RECORD]
        if tuple(body) != REQUIRED_SECTION_IDS:
            raise ValueError("report sections are missing or out of order")
        incident_count = ids.count(ReportSectionId.INCIDENT_RECORD)
        if self.scope == PackageScope.TECHNICAL_INCIDENT:
            if incident_count != 1 or ids[1] != ReportSectionId.INCIDENT_RECORD:
                raise ValueError("technical incident report must open the incident after the legend")
            if self.sections[1].empty:
                raise ValueError("incident section must contain the incident record")
        elif incident_count != 0:
            raise ValueError("incident section is only part of a technical incident report")
        return self


class CampaignSummary(ClerkModel):
    """Campaign association copied from a package.

    `associated` is false when the package has no campaign association.
    That is package contents, not a finding that no campaign exists.
    """

    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    package_id: NonEmptyStr
    synthetic: bool
    associated: bool
    campaign_id: NonEmptyStr | None = None
    label: NonEmptyStr | None = None
    fact_class: Literal[FactClass.DERIVED_ASSOCIATION] | None = None
    epistemic: Literal[EpistemicLayer.CAMPAIGN_ATTRIBUTION] | None = None
    confidence_level: ConfidenceLevel | None = None
    confidence_score: UnitScore | None = None
    confidence_basis: NonEmptyStr | None = None
    packaged_call_ids: list[NonEmptyStr] = Field(default_factory=list)
    member_call_ids: list[NonEmptyStr] = Field(default_factory=list)
    reason_codes: list[NonEmptyStr] = Field(default_factory=list)

    @model_validator(mode="after")
    def _association(self) -> CampaignSummary:
        populated = (
            self.campaign_id is not None,
            self.label is not None,
            self.fact_class is not None,
            self.epistemic is not None,
            self.confidence_level is not None,
            self.confidence_score is not None,
            self.confidence_basis is not None,
            bool(self.packaged_call_ids),
            bool(self.member_call_ids),
        )
        if self.associated:
            if not all(populated):
                raise ValueError("associated summary is missing campaign fields")
        elif any(populated) or self.reason_codes:
            raise ValueError("unassociated summary must not carry campaign fields")
        return self


class MachineReadableExport(ClerkModel):
    """JSON export of one or more evidence packages."""

    export_type: Literal["clerk.evidence_export"] = "clerk.evidence_export"
    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    synthetic: bool
    generated_at: AwareDatetime
    package_ids: list[NonEmptyStr] = Field(min_length=1)
    packages: list[EvidencePackage] = Field(min_length=1)

    @model_validator(mode="after")
    def _consistent(self) -> MachineReadableExport:
        ids = [package.package_id for package in self.packages]
        if ids != self.package_ids:
            raise ValueError("package_ids must match packages in order")
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate package id in export")
        if any(package.synthetic != self.synthetic for package in self.packages):
            raise ValueError("export synthetic flag must match every package")
        if any(package.generated_at != self.generated_at for package in self.packages):
            raise ValueError("export generated_at must match every package")
        return self


class PdfReadyDocument(ClerkModel):
    """A4 HTML representation of a report document for print or PDF conversion."""

    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    report_id: NonEmptyStr
    title: NonEmptyStr
    synthetic: bool
    page_size: Literal["A4"] = "A4"
    content_type: Literal["text/html; charset=utf-8"] = "text/html; charset=utf-8"
    html: NonEmptyStr


class ConfidenceView(ClerkModel):
    subject_id: NonEmptyStr
    fact_class: FactClass
    epistemic: EpistemicLayer
    level: ConfidenceLevel
    score: UnitScore
    basis: NonEmptyStr


class TimestampView(ClerkModel):
    source_id: NonEmptyStr
    label: NonEmptyStr
    at: NonEmptyStr
    call_id: NonEmptyStr | None = None
    excerpt_id: NonEmptyStr | None = None
    artifact_id: NonEmptyStr | None = None
    fact_class: FactClass | None = None
    epistemic: EpistemicLayer | None = None

    @model_validator(mode="after")
    def _pair(self) -> TimestampView:
        if (self.fact_class is None) != (self.epistemic is None):
            raise ValueError("fact_class and epistemic must be set together")
        if self.fact_class is not None and self.epistemic is not None:
            locked_pair(self.fact_class, self.epistemic)
        return self
