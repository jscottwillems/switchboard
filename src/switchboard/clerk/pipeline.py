"""Compose packaging, rendering, and the RADAR catalog."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from switchboard.clerk.adapters.radar import RadarReportCatalog
from switchboard.clerk.fixtures.synthetic_calls import EXPORT_ID, synthetic_bundles
from switchboard.clerk.packaging import package_bundle
from switchboard.clerk.render.csv_export import render_csvs
from switchboard.clerk.render.json_export import dump_model, machine_readable_export
from switchboard.clerk.render.markdown import render_markdown
from switchboard.clerk.render.pdf_ready import render_pdf_ready
from switchboard.clerk.render.project import (
    campaign_summary_for,
    project_report,
    report_id_for,
    report_title,
)
from switchboard.clerk.schemas.evidence import EvidencePackage
from switchboard.clerk.schemas.radar import (
    EXPORT_REPORT_FORMATS,
    HUMAN_REPORT_FORMATS,
    ClerkEvent,
    OpenReportRequest,
    OpenReportResponse,
    ReportFormat,
    ReportIndexEntry,
    ReportPart,
    content_type_for,
    primary_filename,
)
from switchboard.clerk.schemas.reports import (
    CampaignSummary,
    MachineReadableExport,
    PdfReadyDocument,
    ReportDocument,
    ReportKind,
    kind_for_scope,
)


@dataclass(frozen=True)
class RenderedReport:
    package: EvidencePackage
    document: ReportDocument
    markdown: str
    pdf: PdfReadyDocument
    csv_files: dict[str, str]
    summary: CampaignSummary
    report_json: str
    summary_json: str


@dataclass(frozen=True)
class SyntheticOutputs:
    single_call: RenderedReport
    multi_call_campaign: RenderedReport
    technical_incident: RenderedReport
    export: MachineReadableExport
    machine_readable_json: str


def render_package(package: EvidencePackage) -> RenderedReport:
    kind = kind_for_scope(package.scope)
    document = project_report(package, kind)
    summary = campaign_summary_for(package)
    return RenderedReport(
        package=package,
        document=document,
        markdown=render_markdown(document),
        pdf=render_pdf_ready(document),
        csv_files=render_csvs(package),
        summary=summary,
        report_json=dump_model(document),
        summary_json=dump_model(summary),
    )


def build_synthetic_outputs() -> SyntheticOutputs:
    single_bundle, campaign_bundle, incident_bundle = synthetic_bundles()
    single_call = render_package(package_bundle(single_bundle))
    multi_call_campaign = render_package(package_bundle(campaign_bundle))
    technical_incident = render_package(package_bundle(incident_bundle))
    export = machine_readable_export(
        [
            single_call.package,
            multi_call_campaign.package,
            technical_incident.package,
        ]
    )
    return SyntheticOutputs(
        single_call=single_call,
        multi_call_campaign=multi_call_campaign,
        technical_incident=technical_incident,
        export=export,
        machine_readable_json=dump_model(export),
    )


def build_synthetic_catalog() -> RadarReportCatalog:
    outputs = build_synthetic_outputs()
    catalog = RadarReportCatalog()
    occurred_at = outputs.export.generated_at
    for rendered in (
        outputs.single_call,
        outputs.multi_call_campaign,
        outputs.technical_incident,
    ):
        catalog.add_report(
            report_id=rendered.document.report_id,
            package_id=rendered.package.package_id,
            package_ids=[rendered.package.package_id],
            kind=rendered.document.kind,
            title=rendered.document.title,
            synthetic=rendered.package.synthetic,
            occurred_at=occurred_at,
            parts_by_format=_human_parts(rendered),
            emit_package_event=True,
        )
    report_id = report_id_for(EXPORT_ID, ReportKind.MACHINE_READABLE_JSON)
    catalog.add_report(
        report_id=report_id,
        package_id=EXPORT_ID,
        package_ids=list(outputs.export.package_ids),
        kind=ReportKind.MACHINE_READABLE_JSON,
        title=report_title(
            outputs.multi_call_campaign.package,
            ReportKind.MACHINE_READABLE_JSON,
        ),
        synthetic=outputs.export.synthetic,
        occurred_at=occurred_at,
        parts_by_format={
            ReportFormat.JSON: [
                _part(report_id, ReportFormat.JSON, outputs.machine_readable_json)
            ]
        },
        emit_package_event=False,
    )
    return catalog


def json_schemas() -> dict[str, object]:
    return {
        "evidence_package": EvidencePackage.model_json_schema(),
        "machine_readable_export": MachineReadableExport.model_json_schema(),
        "report_document": ReportDocument.model_json_schema(),
        "campaign_summary": CampaignSummary.model_json_schema(),
        "open_report_request": OpenReportRequest.model_json_schema(),
        "open_report_response": OpenReportResponse.model_json_schema(),
        "report_index_entry": ReportIndexEntry.model_json_schema(),
        "clerk_event": ClerkEvent.model_json_schema(),
    }


def write_review_artifacts(root: Path) -> None:
    outputs = build_synthetic_outputs()
    examples = root / "examples" / "synthetic"
    examples.mkdir(parents=True, exist_ok=True)
    written = {
        "single_call_report.md": outputs.single_call.markdown,
        "single_call_report.html": outputs.single_call.pdf.html,
        "multi_call_campaign_report.md": outputs.multi_call_campaign.markdown,
        "multi_call_campaign_report.html": outputs.multi_call_campaign.pdf.html,
        "technical_incident_report.md": outputs.technical_incident.markdown,
        "technical_incident_report.html": outputs.technical_incident.pdf.html,
        "machine_readable_export.json": outputs.machine_readable_json,
        "campaign_summary.json": outputs.multi_call_campaign.summary_json,
    }
    for name, text in written.items():
        (examples / name).write_text(text, encoding="utf-8")
    csv_dir = examples / "campaign_csv"
    csv_dir.mkdir(exist_ok=True)
    for name, text in outputs.multi_call_campaign.csv_files.items():
        (csv_dir / name).write_text(text, encoding="utf-8")
    schema_dir = root / "docs" / "schemas"
    schema_dir.mkdir(parents=True, exist_ok=True)
    for name, schema in json_schemas().items():
        (schema_dir / f"{name}.schema.json").write_text(
            json.dumps(schema, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def _human_parts(rendered: RenderedReport) -> dict[ReportFormat, list[ReportPart]]:
    report_id = rendered.document.report_id
    parts: dict[ReportFormat, list[ReportPart]] = {
        ReportFormat.JSON: [_part(report_id, ReportFormat.JSON, rendered.report_json)],
        ReportFormat.MARKDOWN: [_part(report_id, ReportFormat.MARKDOWN, rendered.markdown)],
        ReportFormat.PDF_READY: [_part(report_id, ReportFormat.PDF_READY, rendered.pdf.html)],
        ReportFormat.CSV: [
            ReportPart(
                filename=name,
                content_type=content_type_for(ReportFormat.CSV),
                body=rendered.csv_files[name],
            )
            for name in sorted(rendered.csv_files)
        ],
        ReportFormat.CAMPAIGN_SUMMARY: [
            _part(report_id, ReportFormat.CAMPAIGN_SUMMARY, rendered.summary_json)
        ],
    }
    if tuple(parts) != HUMAN_REPORT_FORMATS:
        raise RuntimeError("human report formats drifted")
    return parts


def _part(report_id: str, report_format: ReportFormat, body: str) -> ReportPart:
    if report_format == ReportFormat.CSV:
        raise RuntimeError("csv parts are built per file")
    if report_format not in HUMAN_REPORT_FORMATS and report_format not in EXPORT_REPORT_FORMATS:
        raise RuntimeError(f"unsupported format {report_format.value}")
    return ReportPart(
        filename=primary_filename(report_id, report_format),
        content_type=content_type_for(report_format),
        body=body,
    )
