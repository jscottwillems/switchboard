"""PDF-ready HTML. The page is A4 print CSS over the same report fields."""

from __future__ import annotations

from html import escape

from switchboard.clerk.schemas.provenance import ABSENT
from switchboard.clerk.schemas.reports import PdfReadyDocument, ReportDocument, ReportEntry

_STYLE = """
@page { size: A4; margin: 16mm; }
body { font-family: Georgia, "Times New Roman", serif; font-size: 11pt; color: #111; }
.banner { border: 1px solid #111; padding: 8px; margin-bottom: 16px; font-weight: 700; }
h1 { font-size: 16pt; }
h2 { font-size: 13pt; border-bottom: 1px solid #111; page-break-after: avoid; }
h3 { font-size: 11pt; page-break-after: avoid; }
.tag, .field-name { font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 9pt; }
pre { white-space: pre-wrap; font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 9pt; }
article { break-inside: avoid; margin-bottom: 8px; }
"""


def render_pdf_ready(document: ReportDocument) -> PdfReadyDocument:
    parts = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        f"<title>{escape(document.title)}</title>",
        f"<style>{_STYLE}</style>",
        "</head>",
        "<body>",
        f"<h1>{escape(document.title)}</h1>",
        f'<p class="banner">{escape(document.banner)}</p>',
        "<dl>",
        f"<dt>Upstream input schema</dt><dd>{escape(document.upstream_input_schema)}</dd>",
        f"<dt>Package ID</dt><dd>{escape(document.package_id)}</dd>",
        f"<dt>Report ID</dt><dd>{escape(document.report_id)}</dd>",
        f"<dt>Synthetic</dt><dd>{str(document.synthetic).lower()}</dd>",
        "</dl>",
    ]
    for section in document.sections:
        parts.append(f'<section id="{section.section_id.value}">')
        parts.append(f"<h2>{escape(section.title)}</h2>")
        if section.empty:
            parts.append(f"<p>{escape(ABSENT)}</p>")
        else:
            parts.extend(_article(entry) for entry in section.entries)
        parts.append("</section>")
    parts.extend(["</body>", "</html>", ""])
    return PdfReadyDocument(
        report_id=document.report_id,
        title=document.title,
        synthetic=document.synthetic,
        html="\n".join(parts),
    )


def _article(entry: ReportEntry) -> str:
    attributes = ""
    if entry.fact_class is not None and entry.epistemic is not None:
        attributes = (
            f' data-fact-class="{entry.fact_class.value}"'
            f' data-epistemic="{entry.epistemic.value}"'
        )
    lines = [f"<article{attributes}>"]
    if entry.entry_id is not None:
        lines.append(f"<h3>{escape(entry.entry_id)}</h3>")
    tags: list[str] = []
    if entry.fact_class is not None:
        tags.append(f"fact_class: {entry.fact_class.value}")
    if entry.epistemic is not None:
        tags.append(f"epistemic: {entry.epistemic.value}")
    if entry.confirmed is not None:
        tags.append(f"confirmed: {str(entry.confirmed).lower()}")
    if tags:
        lines.append(f'<p class="tag">{escape(" | ".join(tags))}</p>')
    lines.append("<dl>")
    for field in entry.fields:
        lines.append(f'<dt class="field-name">{escape(field.name)}</dt>')
        if "\n" in field.value:
            lines.append(f"<dd><pre>{escape(field.value)}</pre></dd>")
        else:
            lines.append(f"<dd>{escape(field.value)}</dd>")
    lines.append("</dl>")
    lines.append("</article>")
    return "\n".join(lines)
