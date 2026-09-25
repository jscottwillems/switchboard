"""RADAR open-report adapter."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from switchboard.clerk.errors import ReportFormatUnavailable, ReportNotFoundError
from switchboard.clerk.fixtures.synthetic_calls import EXPORT_ID, PACKAGE_CAMPAIGN
from switchboard.clerk.pipeline import build_synthetic_catalog
from switchboard.clerk.schemas.radar import (
    HUMAN_REPORT_FORMATS,
    ClerkEventType,
    OpenReportRequest,
    ReportFormat,
)
from switchboard.clerk.schemas.reports import ReportKind


def test_catalog_lists_four_reports() -> None:
    catalog = build_synthetic_catalog()
    reports = catalog.list_reports()
    assert len(reports) == 4
    kinds = {entry.kind for entry in reports}
    assert kinds == {
        ReportKind.SINGLE_CALL,
        ReportKind.MULTI_CALL_CAMPAIGN,
        ReportKind.TECHNICAL_INCIDENT,
        ReportKind.MACHINE_READABLE_JSON,
    }
    for entry in reports:
        assert entry.synthetic is True
        if entry.kind is ReportKind.MACHINE_READABLE_JSON:
            assert entry.available_formats == [ReportFormat.JSON]
            assert entry.package_id == EXPORT_ID
            assert PACKAGE_CAMPAIGN in entry.package_ids
        else:
            assert tuple(entry.available_formats) == HUMAN_REPORT_FORMATS


def test_open_report_returns_markdown_and_csv_parts() -> None:
    catalog = build_synthetic_catalog()
    campaign = next(entry for entry in catalog.list_reports() if entry.kind is ReportKind.MULTI_CALL_CAMPAIGN)
    opened = catalog.open_report(
        OpenReportRequest(report_id=campaign.report_id, format=ReportFormat.MARKDOWN)
    )
    assert opened.synthetic is True
    assert opened.parts[0].content_type.startswith("text/markdown")
    assert "SYNTHETIC FIXTURE" in opened.parts[0].body
    assert campaign.package_id in opened.parts[0].body
    csv_open = catalog.open_report(
        OpenReportRequest(report_id=campaign.report_id, format=ReportFormat.CSV)
    )
    assert csv_open.primary_filename == "calls.csv"
    bodies = {part.filename: part.body for part in csv_open.parts}
    assert "syn-call-001" in bodies["calls.csv"]
    assert "spoken_identifier" in bodies["spoken_identifiers.csv"]


def test_machine_readable_export_opens_as_json_only() -> None:
    catalog = build_synthetic_catalog()
    export = next(
        entry for entry in catalog.list_reports() if entry.kind is ReportKind.MACHINE_READABLE_JSON
    )
    opened = catalog.open_report(OpenReportRequest(report_id=export.report_id, format=ReportFormat.JSON))
    assert '"export_type": "clerk.evidence_export"' in opened.parts[0].body
    assert "syn-pkg-call-001" in opened.parts[0].body
    with pytest.raises(ReportFormatUnavailable):
        catalog.open_report(
            OpenReportRequest(report_id=export.report_id, format=ReportFormat.MARKDOWN)
        )


def test_missing_report_and_extra_request_fields() -> None:
    catalog = build_synthetic_catalog()
    with pytest.raises(ReportNotFoundError):
        catalog.open_report(OpenReportRequest(report_id="missing", format=ReportFormat.JSON))
    with pytest.raises(ValidationError):
        OpenReportRequest.model_validate(
            {"report_id": "syn-pkg-call-001__single_call", "format": "markdown", "ui": "vue"}
        )


def test_events_carry_ids_only() -> None:
    catalog = build_synthetic_catalog()
    events = catalog.events()
    created = [event for event in events if event.event_type is ClerkEventType.EVIDENCE_PACKAGE_CREATED]
    ready = [event for event in events if event.event_type is ClerkEventType.REPORT_READY]
    assert len(created) == 3
    assert len(ready) == 4
    blob = "\n".join(event.model_dump_json() for event in events)
    assert "Visa" not in blob
    assert "+1-" not in blob
    assert "1-800" not in blob
    assert "CARD SERVICES" not in blob
    assert all(event.synthetic is True for event in events)
