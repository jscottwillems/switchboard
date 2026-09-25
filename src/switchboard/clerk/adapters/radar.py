"""In-process report catalog RADAR can call. No UI and no HTTP server."""

from __future__ import annotations

from switchboard.clerk.errors import ClerkError, ReportFormatUnavailable, ReportNotFoundError
from switchboard.clerk.schemas.provenance import AwareDatetime
from switchboard.clerk.schemas.radar import (
    ClerkEvent,
    ClerkEventType,
    OpenReportRequest,
    OpenReportResponse,
    ReportFormat,
    ReportIndexEntry,
    ReportPart,
    primary_filename,
)
from switchboard.clerk.schemas.reports import ReportKind


class RadarReportCatalog:
    """Reference adapter for GET /clerk/reports and POST /clerk/reports/open."""

    def __init__(self) -> None:
        self._index: dict[str, ReportIndexEntry] = {}
        self._parts: dict[tuple[str, ReportFormat], list[ReportPart]] = {}
        self._events: list[ClerkEvent] = []

    def add_report(
        self,
        *,
        report_id: str,
        package_id: str,
        package_ids: list[str],
        kind: ReportKind,
        title: str,
        synthetic: bool,
        occurred_at: AwareDatetime,
        parts_by_format: dict[ReportFormat, list[ReportPart]],
        emit_package_event: bool,
    ) -> None:
        if report_id in self._index:
            raise ClerkError(f"duplicate report id {report_id}")
        if not parts_by_format:
            raise ClerkError("report requires at least one format")
        formats = list(parts_by_format)
        for report_format, parts in parts_by_format.items():
            names = [part.filename for part in parts]
            if primary_filename(report_id, report_format) not in names:
                raise ClerkError(f"{report_id} is missing the primary file for {report_format.value}")
            self._parts[(report_id, report_format)] = list(parts)
        self._index[report_id] = ReportIndexEntry(
            report_id=report_id,
            package_id=package_id,
            package_ids=list(package_ids),
            kind=kind,
            title=title,
            synthetic=synthetic,
            available_formats=formats,
        )
        if emit_package_event:
            self._events.append(
                ClerkEvent(
                    event_type=ClerkEventType.EVIDENCE_PACKAGE_CREATED,
                    occurred_at=occurred_at,
                    synthetic=synthetic,
                    package_id=package_id,
                    package_ids=[package_id],
                )
            )
        self._events.append(
            ClerkEvent(
                event_type=ClerkEventType.REPORT_READY,
                occurred_at=occurred_at,
                synthetic=synthetic,
                package_id=package_id,
                package_ids=list(package_ids),
                report_id=report_id,
                report_kind=kind,
                available_formats=formats,
            )
        )

    def list_reports(self) -> list[ReportIndexEntry]:
        return [self._index[report_id] for report_id in sorted(self._index)]

    def open_report(self, request: OpenReportRequest) -> OpenReportResponse:
        entry = self._index.get(request.report_id)
        if entry is None:
            raise ReportNotFoundError(request.report_id)
        parts = self._parts.get((request.report_id, request.format))
        if parts is None:
            raise ReportFormatUnavailable(request.report_id, request.format.value)
        return OpenReportResponse(
            report_id=entry.report_id,
            package_id=entry.package_id,
            package_ids=list(entry.package_ids),
            kind=entry.kind,
            format=request.format,
            synthetic=entry.synthetic,
            primary_filename=primary_filename(request.report_id, request.format),
            parts=list(parts),
        )

    def events(self) -> tuple[ClerkEvent, ...]:
        return tuple(self._events)
