"""Report generation from synthetic fixtures."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from switchboard.clerk.adapters.upstream import ProvisionalBundle, ProvisionalCallSession
from switchboard.clerk.fixtures.synthetic_calls import (
    CALL_2,
    CAMPAIGN_ID,
    DERIVED_STATEMENT,
    DISPLAYED_LINE,
    EXCERPT_1,
    EXCERPT_3,
    INCIDENT_ID,
    INCIDENT_SUMMARY,
    PAI_LINE,
    SIP_FROM_LINE,
    SIGNALING_LOG,
    synthetic_bundles,
    synthetic_world,
)
from switchboard.clerk.packaging import package_bundle
from switchboard.clerk.pipeline import build_synthetic_outputs, json_schemas, render_package
from switchboard.clerk.schemas.evidence import EvidencePackage
from switchboard.clerk.schemas.provenance import ABSENT, UNMARKED_BANNER, FactClass, PackageScope
from switchboard.clerk.schemas.reports import (
    REQUIRED_SECTION_IDS,
    MachineReadableExport,
    ReportDocument,
    ReportKind,
    ReportSectionId,
)


def _outputs():
    return build_synthetic_outputs()


def _markdown_section(text: str, title: str) -> str:
    marker = f"\n## {title}\n"
    start = text.index(marker) + len(marker)
    rest = text[start:]
    nxt = rest.find("\n## ")
    return rest if nxt < 0 else rest[:nxt]


def _html_section(html: str, section_id: str) -> str:
    marker = f'<section id="{section_id}">'
    start = html.index(marker) + len(marker)
    rest = html[start:]
    nxt = rest.find('<section id="')
    return rest if nxt < 0 else rest[:nxt]


def test_fixture_values_are_substrings_of_their_sources() -> None:
    world = synthetic_world()
    excerpts = {excerpt.excerpt_id: excerpt.text for call in world.calls for excerpt in call.excerpts}
    assert "This is the Visa fraud department." in excerpts["syn-ex-001"]
    assert "Marcus" in excerpts["syn-ex-001"]
    assert "1-800-555-0199" in excerpts["syn-ex-002"]
    assert "Visa" in excerpts["syn-ex-004"]
    assert "1-800-555-0199" in excerpts["syn-ex-004"]
    assert "CARD SERVICES" not in " ".join(excerpts.values())
    assert "+1-202-555-0143" not in " ".join(excerpts.values())
    artifact = world.artifacts[0].inline_text or ""
    assert artifact == SIGNALING_LOG
    for note in (SIP_FROM_LINE, DISPLAYED_LINE, PAI_LINE):
        assert note in artifact
    observations = {item.observation_id: item for item in world.observations}
    assert observations["syn-obs-001"].statement in excerpts["syn-ex-001"]
    assert observations["syn-obs-002"].statement == EXCERPT_3 == excerpts["syn-ex-003"]
    assert observations["syn-obs-004"].statement == SIP_FROM_LINE
    assert observations["syn-obs-003"].statement == DERIVED_STATEMENT
    assert observations["syn-obs-003"].statement not in excerpts["syn-ex-001"]
    assert world.synthetic is True


def test_four_outputs_exist_and_are_labeled_synthetic() -> None:
    outputs = _outputs()
    reports = (
        outputs.single_call,
        outputs.multi_call_campaign,
        outputs.technical_incident,
    )
    kinds = [report.document.kind for report in reports]
    assert kinds == [
        ReportKind.SINGLE_CALL,
        ReportKind.MULTI_CALL_CAMPAIGN,
        ReportKind.TECHNICAL_INCIDENT,
    ]
    for report in reports:
        assert report.package.synthetic is True
        assert report.document.synthetic is True
        assert "SYNTHETIC FIXTURE" in report.markdown
        assert "SYNTHETIC FIXTURE" in report.pdf.html
        assert report.pdf.page_size == "A4"
        assert report.pdf.content_type.startswith("text/html")
        assert set(report.csv_files) >= {"calls.csv", "observations.csv", "campaign_summary.csv"}
    export = MachineReadableExport.model_validate_json(outputs.machine_readable_json)
    assert export == outputs.export
    assert export.synthetic is True
    assert [package.package_id for package in export.packages] == export.package_ids
    assert len(export.packages) == 3


def test_required_sections_and_provenance_legend() -> None:
    outputs = _outputs()
    for report in (
        outputs.single_call,
        outputs.multi_call_campaign,
        outputs.technical_incident,
    ):
        ids = [section.section_id for section in report.document.sections]
        body = [section_id for section_id in ids if section_id != ReportSectionId.INCIDENT_RECORD]
        assert tuple(body) == REQUIRED_SECTION_IDS
        legend = report.document.sections[0]
        assert {entry.entry_id for entry in legend.entries} == {item.value for item in FactClass}
        for section in report.document.sections:
            assert section.title in report.markdown
            assert f'<section id="{section.section_id.value}">' in report.pdf.html
            for entry in section.entries:
                for field in entry.fields:
                    for line in field.value.splitlines():
                        assert line in report.markdown
                        assert line in report.pdf.html or _escaped(line) in report.pdf.html


def test_reported_spoken_derived_and_confirmed_stay_apart() -> None:
    report = _outputs().multi_call_campaign
    html = report.pdf.html
    displayed = _html_section(html, "displayed_caller_metadata")
    spoken = _html_section(html, "spoken_identifiers")
    observations = _html_section(html, "structured_observations")
    reasons = _html_section(html, "association_reasons")
    assert 'data-fact-class="reported_caller_metadata"' in displayed
    assert "CARD SERVICES" in displayed
    assert "+1-202-555-0143" in displayed
    assert "1-800-555-0199" not in displayed
    assert "Visa" not in displayed
    assert 'data-fact-class="spoken_identifier"' in spoken
    assert "1-800-555-0199" in spoken
    assert "Marcus" in spoken
    assert "CARD SERVICES" not in spoken
    assert 'data-fact-class="confirmed_observation"' in observations
    assert 'data-fact-class="raw_observation"' in observations
    assert 'data-fact-class="derived_interpretation"' in observations
    assert DERIVED_STATEMENT in observations
    assert "confirmed: false" in observations
    assert "confirmed: true" in observations
    assert 'data-fact-class="derived_association"' in reasons
    assert "CARD SERVICES" in reasons
    assert "<sip:" not in html
    assert "&lt;sip:" in html


def test_single_call_does_not_import_the_other_call_or_the_incident() -> None:
    report = _outputs().single_call
    text = report.markdown
    assert "syn-call-002" in _markdown_section(text, "Campaign association")
    assert "+1-202-555-0177" not in text
    assert INCIDENT_SUMMARY not in text
    assert INCIDENT_ID not in text
    assert report.summary.associated is True
    assert report.summary.packaged_call_ids == ["syn-call-001"]
    assert report.summary.member_call_ids == ["syn-call-001", CALL_2]
    assert report.summary.fact_class is FactClass.DERIVED_ASSOCIATION


def test_campaign_report_omits_the_incident_record() -> None:
    report = _outputs().multi_call_campaign
    assert report.package.incident is None
    assert INCIDENT_SUMMARY not in report.markdown
    assert INCIDENT_ID not in report.markdown
    assert CAMPAIGN_ID in report.markdown
    assert "Synthetic card-issuer impersonation" in report.summary_json
    assert report.document.scope is PackageScope.CAMPAIGN
    assert len(report.package.calls) == 2


def test_incident_report_omits_campaign_attribution() -> None:
    report = _outputs().technical_incident
    campaign = _markdown_section(report.markdown, "Campaign association")
    reasons = _markdown_section(report.markdown, "Association reasons")
    assert ABSENT in campaign
    assert ABSENT in reasons
    assert CAMPAIGN_ID not in report.markdown
    assert "Synthetic card-issuer impersonation" not in report.markdown
    incident = _html_section(report.pdf.html, "incident_record")
    assert INCIDENT_SUMMARY in incident
    assert 'data-fact-class="derived_interpretation"' in incident
    assert SIP_FROM_LINE in report.markdown
    artifacts = _html_section(report.pdf.html, "relevant_artifacts")
    assert 'data-fact-class="raw_observation"' in artifacts
    assert _escaped(SIP_FROM_LINE) in artifacts
    assert report.summary.associated is False
    assert report.summary.campaign_id is None


def test_renderer_does_not_add_connective_claims() -> None:
    outputs = _outputs()
    banned = ("therefore", "likely", "probably", "we conclude")
    for report in (
        outputs.single_call,
        outputs.multi_call_campaign,
        outputs.technical_incident,
    ):
        lowered = report.markdown.lower()
        for word in banned:
            assert word not in lowered


def test_unmarked_package_uses_the_unmarked_banner_and_invents_nothing() -> None:
    bundle = ProvisionalBundle(
        package_id="test-pkg-real-flag",
        synthetic=False,
        generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        scope=PackageScope.SINGLE_CALL,
        calls=[
            ProvisionalCallSession(
                call_id="test-call-1",
                started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                ended_at=datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc),
                duration_seconds=60,
            )
        ],
    )
    rendered = render_package(package_bundle(bundle))
    assert rendered.markdown.startswith("# Single-call evidence report test-call-1\n")
    assert UNMARKED_BANNER in rendered.markdown
    assert "Visa" not in rendered.markdown
    assert "SYNTHETIC FIXTURE" not in rendered.markdown
    assert _markdown_section(rendered.markdown, "Spoken identifiers").strip() == ABSENT


def test_transcript_text_is_copied_verbatim() -> None:
    package = package_bundle(synthetic_bundles()[0])
    text = package.calls[0].transcript_excerpts[0].text
    assert text == EXCERPT_1
    document = ReportDocument.model_validate_json(render_package(package).report_json)
    excerpts = next(
        section
        for section in document.sections
        if section.section_id is ReportSectionId.TRANSCRIPT_EXCERPTS
    )
    values = [field.value for entry in excerpts.entries for field in entry.fields if field.name == "text"]
    assert EXCERPT_1 in values


def test_csv_keeps_displayed_metadata_distinct_from_spoken_identifiers() -> None:
    csv_files = _outputs().multi_call_campaign.csv_files
    calls = csv_files["calls.csv"]
    spoken = csv_files["spoken_identifiers.csv"]
    assert "displayed_fact_class" in calls.splitlines()[0]
    assert "reported_caller_metadata" in calls
    assert "CARD SERVICES" in calls
    assert "1-800-555-0199" not in calls
    assert "spoken_identifier" in spoken
    assert "1-800-555-0199" in spoken
    assert "CARD SERVICES" not in spoken
    assert "campaign_attribution" in csv_files["association_reasons.csv"]
    assert "derived_interpretation" in csv_files["observations.csv"]
    assert "confirmed_observation" in csv_files["observations.csv"]


def test_committed_review_artifacts_match_the_generator() -> None:
    root = Path(__file__).resolve().parents[1]
    outputs = _outputs()
    examples = root / "examples" / "synthetic"
    expected = {
        "single_call_report.md": outputs.single_call.markdown,
        "single_call_report.html": outputs.single_call.pdf.html,
        "multi_call_campaign_report.md": outputs.multi_call_campaign.markdown,
        "multi_call_campaign_report.html": outputs.multi_call_campaign.pdf.html,
        "technical_incident_report.md": outputs.technical_incident.markdown,
        "technical_incident_report.html": outputs.technical_incident.pdf.html,
        "machine_readable_export.json": outputs.machine_readable_json,
        "campaign_summary.json": outputs.multi_call_campaign.summary_json,
    }
    for name, text in expected.items():
        assert (examples / name).read_text(encoding="utf-8") == text
    csv_dir = examples / "campaign_csv"
    for name, text in outputs.multi_call_campaign.csv_files.items():
        assert (csv_dir / name).read_text(encoding="utf-8") == text
    for name, schema in json_schemas().items():
        path = root / "docs" / "schemas" / f"{name}.schema.json"
        assert json.loads(path.read_text(encoding="utf-8")) == schema


def _escaped(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
