"""Markdown rendering of a report document."""

from __future__ import annotations

from switchboard.clerk.schemas.provenance import ABSENT
from switchboard.clerk.schemas.reports import ReportDocument, ReportEntry


def render_markdown(document: ReportDocument) -> str:
    lines = [
        f"# {document.title}",
        "",
        f"> {document.banner}",
        "",
        f"Upstream input schema: {document.upstream_input_schema}",
        f"Package ID: {document.package_id}",
        f"Report ID: {document.report_id}",
        f"Synthetic: {str(document.synthetic).lower()}",
        "",
    ]
    for section in document.sections:
        lines.append(f"## {section.title}")
        lines.append("")
        if section.empty:
            lines.append(ABSENT)
            lines.append("")
            continue
        for entry in section.entries:
            lines.extend(_entry_lines(entry))
    text = "\n".join(lines)
    if not text.endswith("\n"):
        text += "\n"
    return text


def _entry_lines(entry: ReportEntry) -> list[str]:
    lines: list[str] = []
    if entry.entry_id is not None:
        lines.append(f"### {entry.entry_id}")
        lines.append("")
    if entry.fact_class is not None:
        lines.append(f"- fact_class: {entry.fact_class.value}")
    if entry.epistemic is not None:
        lines.append(f"- epistemic: {entry.epistemic.value}")
    if entry.confirmed is not None:
        lines.append(f"- confirmed: {str(entry.confirmed).lower()}")
    for field in entry.fields:
        if "\n" in field.value:
            lines.append(f"- {field.name}:")
            lines.extend(f"    {line}" for line in field.value.splitlines())
        else:
            lines.append(f"- {field.name}: {field.value}")
    lines.append("")
    return lines
