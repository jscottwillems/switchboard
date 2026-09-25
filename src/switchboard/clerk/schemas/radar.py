"""RADAR handoff: open a CLERK report without depending on CLERK internals.

The in-process catalog is the reference adapter. HTTP paths below are the
contract a gateway can expose later. This module does not start a server and
does not define RADAR's screens.
"""

from __future__ import annotations

from enum import Enum
from typing import assert_never

from pydantic import Field, model_validator

from switchboard.clerk.schemas.provenance import AwareDatetime, ClerkModel, NonEmptyStr
from switchboard.clerk.schemas.reports import ReportKind


class ReportFormat(str, Enum):
    JSON = "json"
    MARKDOWN = "markdown"
    PDF_READY = "pdf_ready"
    CSV = "csv"
    CAMPAIGN_SUMMARY = "campaign_summary"


HUMAN_REPORT_FORMATS: tuple[ReportFormat, ...] = (
    ReportFormat.JSON,
    ReportFormat.MARKDOWN,
    ReportFormat.PDF_READY,
    ReportFormat.CSV,
    ReportFormat.CAMPAIGN_SUMMARY,
)
EXPORT_REPORT_FORMATS: tuple[ReportFormat, ...] = (ReportFormat.JSON,)


def content_type_for(report_format: ReportFormat) -> str:
    match report_format:
        case ReportFormat.JSON | ReportFormat.CAMPAIGN_SUMMARY:
            return "application/json; charset=utf-8"
        case ReportFormat.MARKDOWN:
            return "text/markdown; charset=utf-8"
        case ReportFormat.PDF_READY:
            return "text/html; charset=utf-8"
        case ReportFormat.CSV:
            return "text/csv; charset=utf-8"
        case _ as unreachable:
            assert_never(unreachable)


def primary_filename(report_id: str, report_format: ReportFormat) -> str:
    match report_format:
        case ReportFormat.JSON:
            return f"{report_id}.json"
        case ReportFormat.MARKDOWN:
            return f"{report_id}.md"
        case ReportFormat.PDF_READY:
            return f"{report_id}.html"
        case ReportFormat.CSV:
            return "calls.csv"
        case ReportFormat.CAMPAIGN_SUMMARY:
            return f"{report_id}.campaign_summary.json"
        case _ as unreachable:
            assert_never(unreachable)


class OpenReportRequest(ClerkModel):
    """Body of POST /clerk/reports/open."""

    report_id: NonEmptyStr = Field(description="Report id returned by GET /clerk/reports.")
    format: ReportFormat = Field(description="Rendering to open.")


class ReportPart(ClerkModel):
    filename: NonEmptyStr
    content_type: NonEmptyStr
    body: NonEmptyStr


class ReportIndexEntry(ClerkModel):
    """One row of GET /clerk/reports."""

    report_id: NonEmptyStr
    package_id: NonEmptyStr = Field(
        description="Evidence package id, or the export id for a machine-readable export."
    )
    package_ids: list[NonEmptyStr] = Field(min_length=1)
    kind: ReportKind
    title: NonEmptyStr
    synthetic: bool
    available_formats: list[ReportFormat] = Field(min_length=1)


class OpenReportResponse(ClerkModel):
    """Response of POST /clerk/reports/open.

    CSV responses contain one part per table. `primary_filename` selects the
    part a single-document client should show. Other formats have one part.
    """

    report_id: NonEmptyStr
    package_id: NonEmptyStr
    package_ids: list[NonEmptyStr] = Field(min_length=1)
    kind: ReportKind
    format: ReportFormat
    synthetic: bool
    primary_filename: NonEmptyStr
    parts: list[ReportPart] = Field(min_length=1)

    @model_validator(mode="after")
    def _primary(self) -> OpenReportResponse:
        names = [part.filename for part in self.parts]
        if len(names) != len(set(names)):
            raise ValueError("duplicate report part filename")
        if self.primary_filename not in names:
            raise ValueError("primary_filename is not a part")
        if self.format != ReportFormat.CSV and len(self.parts) != 1:
            raise ValueError("only csv responses have multiple parts")
        return self


class ClerkEventType(str, Enum):
    EVIDENCE_PACKAGE_CREATED = "clerk.evidence_package.created"
    REPORT_READY = "clerk.report.ready"


class ClerkEvent(ClerkModel):
    """Identifier-only event. Transcripts and caller metadata stay in the package."""

    event_type: ClerkEventType
    occurred_at: AwareDatetime
    synthetic: bool
    package_id: NonEmptyStr
    package_ids: list[NonEmptyStr] = Field(min_length=1)
    report_id: NonEmptyStr | None = None
    report_kind: ReportKind | None = None
    available_formats: list[ReportFormat] = Field(default_factory=list)

    @model_validator(mode="after")
    def _shape(self) -> ClerkEvent:
        match self.event_type:
            case ClerkEventType.EVIDENCE_PACKAGE_CREATED:
                if self.report_id is not None or self.report_kind is not None or self.available_formats:
                    raise ValueError("package event carries package ids only")
                if self.package_ids != [self.package_id]:
                    raise ValueError("package event lists that package")
            case ClerkEventType.REPORT_READY:
                if self.report_id is None or self.report_kind is None or not self.available_formats:
                    raise ValueError("report event requires report id, kind, and formats")
            case _ as unreachable:
                assert_never(unreachable)
        return self
