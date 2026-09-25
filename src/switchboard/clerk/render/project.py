"""Project an evidence package onto a report document and row views."""

from __future__ import annotations

from typing import assert_never

from switchboard.clerk.errors import RenderError
from switchboard.clerk.render.format import iso_z, join_ids, present, score_text
from switchboard.clerk.schemas.evidence import EvidencePackage
from switchboard.clerk.schemas.provenance import (
    SYNTHETIC_BANNER,
    UNMARKED_BANNER,
    EpistemicLayer,
    FactClass,
    legend_definition,
)
from switchboard.clerk.schemas.reports import (
    CampaignSummary,
    ConfidenceView,
    ReportDocument,
    ReportEntry,
    ReportField,
    ReportKind,
    ReportSection,
    ReportSectionId,
    TimestampView,
    kind_for_scope,
    section_title,
)


def report_id_for(package_id: str, kind: ReportKind) -> str:
    return f"{package_id}__{kind.value}"


def report_title(package: EvidencePackage, kind: ReportKind) -> str:
    match kind:
        case ReportKind.SINGLE_CALL:
            return f"Single-call evidence report {package.calls[0].identity.call_id}"
        case ReportKind.MULTI_CALL_CAMPAIGN:
            campaign = package.campaign
            if campaign is None:
                raise RenderError("campaign report requires a campaign association")
            return f"Multi-call campaign evidence report {campaign.campaign_id}"
        case ReportKind.TECHNICAL_INCIDENT:
            incident = package.incident
            if incident is None:
                raise RenderError("technical incident report requires an incident record")
            return f"Technical incident evidence report {incident.incident_id}"
        case ReportKind.MACHINE_READABLE_JSON:
            return "Machine-readable evidence export"
        case _ as unreachable:
            assert_never(unreachable)


def campaign_summary_for(package: EvidencePackage) -> CampaignSummary:
    campaign = package.campaign
    if campaign is None:
        return CampaignSummary(
            package_id=package.package_id,
            synthetic=package.synthetic,
            associated=False,
        )
    return CampaignSummary(
        package_id=package.package_id,
        synthetic=package.synthetic,
        associated=True,
        campaign_id=campaign.campaign_id,
        label=campaign.label,
        fact_class=campaign.fact_class,
        epistemic=campaign.epistemic,
        confidence_level=campaign.confidence.level,
        confidence_score=campaign.confidence.score,
        confidence_basis=campaign.confidence.basis,
        packaged_call_ids=list(campaign.packaged_call_ids),
        member_call_ids=list(campaign.member_call_ids),
        reason_codes=[reason.code for reason in campaign.reasons],
    )


def iter_confidence(package: EvidencePackage) -> list[ConfidenceView]:
    rows: list[ConfidenceView] = []
    for call in package.calls:
        for spoken in call.spoken_identifiers:
            rows.append(
                ConfidenceView(
                    subject_id=spoken.identifier_id,
                    fact_class=spoken.fact_class,
                    epistemic=spoken.epistemic,
                    level=spoken.confidence.level,
                    score=spoken.confidence.score,
                    basis=spoken.confidence.basis,
                )
            )
        for observation in call.observations:
            rows.append(
                ConfidenceView(
                    subject_id=observation.observation_id,
                    fact_class=observation.fact_class,
                    epistemic=observation.epistemic,
                    level=observation.confidence.level,
                    score=observation.confidence.score,
                    basis=observation.confidence.basis,
                )
            )
    campaign = package.campaign
    if campaign is not None:
        rows.append(
            ConfidenceView(
                subject_id=campaign.campaign_id,
                fact_class=campaign.fact_class,
                epistemic=campaign.epistemic,
                level=campaign.confidence.level,
                score=campaign.confidence.score,
                basis=campaign.confidence.basis,
            )
        )
        for reason in campaign.reasons:
            rows.append(
                ConfidenceView(
                    subject_id=reason.reason_id,
                    fact_class=reason.fact_class,
                    epistemic=reason.epistemic,
                    level=reason.confidence.level,
                    score=reason.confidence.score,
                    basis=reason.confidence.basis,
                )
            )
    return rows


def iter_timestamps(package: EvidencePackage) -> list[TimestampView]:
    rows: list[TimestampView] = []
    for call in package.calls:
        call_id = call.identity.call_id
        rows.append(
            _stamp(
                call_id,
                "call.started_at",
                iso_z(call.started_at),
                call_id,
                None,
                None,
                FactClass.RAW_OBSERVATION,
                EpistemicLayer.RAW_OBSERVATION,
            )
        )
        rows.append(
            _stamp(
                call_id,
                "call.ended_at",
                iso_z(call.ended_at),
                call_id,
                None,
                None,
                FactClass.RAW_OBSERVATION,
                EpistemicLayer.RAW_OBSERVATION,
            )
        )
        for excerpt in call.transcript_excerpts:
            rows.append(
                _stamp(
                    excerpt.excerpt_id,
                    "excerpt.started_at",
                    iso_z(excerpt.started_at),
                    call_id,
                    excerpt.excerpt_id,
                    None,
                    FactClass.RAW_OBSERVATION,
                    EpistemicLayer.RAW_OBSERVATION,
                )
            )
            if excerpt.ended_at is not None:
                rows.append(
                    _stamp(
                        excerpt.excerpt_id,
                        "excerpt.ended_at",
                        iso_z(excerpt.ended_at),
                        call_id,
                        excerpt.excerpt_id,
                        None,
                        FactClass.RAW_OBSERVATION,
                        EpistemicLayer.RAW_OBSERVATION,
                    )
                )
        for spoken in call.spoken_identifiers:
            rows.append(
                _stamp(
                    spoken.identifier_id,
                    "spoken_identifier.recorded_at",
                    iso_z(spoken.recorded_at),
                    call_id,
                    spoken.excerpt_id,
                    None,
                    FactClass.SPOKEN_IDENTIFIER,
                    EpistemicLayer.RAW_OBSERVATION,
                )
            )
        for observation in call.observations:
            for stamp in observation.supporting_timestamps:
                rows.append(
                    _stamp(
                        stamp.source_id,
                        stamp.label,
                        iso_z(stamp.at),
                        stamp.call_id,
                        stamp.excerpt_id,
                        stamp.artifact_id,
                        observation.fact_class,
                        observation.epistemic,
                    )
                )
    campaign = package.campaign
    if campaign is not None:
        for reason in campaign.reasons:
            for stamp in reason.supporting_timestamps:
                rows.append(
                    _stamp(
                        stamp.source_id,
                        stamp.label,
                        iso_z(stamp.at),
                        stamp.call_id,
                        stamp.excerpt_id,
                        stamp.artifact_id,
                        FactClass.DERIVED_ASSOCIATION,
                        EpistemicLayer.CAMPAIGN_ATTRIBUTION,
                    )
                )
    return rows


def project_report(package: EvidencePackage, kind: ReportKind) -> ReportDocument:
    match kind:
        case ReportKind.MACHINE_READABLE_JSON:
            raise RenderError("machine-readable export is not a human report document")
        case (
            ReportKind.SINGLE_CALL
            | ReportKind.MULTI_CALL_CAMPAIGN
            | ReportKind.TECHNICAL_INCIDENT
        ):
            if kind != kind_for_scope(package.scope):
                raise RenderError("report kind does not match package scope")
            return _document(package, kind)
        case _ as unreachable:
            assert_never(unreachable)


def _document(package: EvidencePackage, kind: ReportKind) -> ReportDocument:
    sections = [_legend(), *_incident(package), *_body(package)]
    return ReportDocument(
        report_id=report_id_for(package.package_id, kind),
        kind=kind,
        scope=package.scope,
        package_id=package.package_id,
        synthetic=package.synthetic,
        title=report_title(package, kind),
        banner=SYNTHETIC_BANNER if package.synthetic else UNMARKED_BANNER,
        upstream_input_schema=package.upstream_input_schema,
        sections=sections,
    )


def _body(package: EvidencePackage) -> list[ReportSection]:
    return [
        _call_identity(package),
        _call_times(package),
        _displayed(package),
        _duration(package),
        _excerpts(package),
        _spoken(package),
        _observations(package),
        _campaign(package),
        _reasons(package),
        _supporting_timestamps(package),
        _artifacts(package),
        _confidence(package),
    ]


def _section(section_id: ReportSectionId, entries: list[ReportEntry]) -> ReportSection:
    return ReportSection(
        section_id=section_id,
        title=section_title(section_id),
        empty=len(entries) == 0,
        entries=entries,
    )


def _entry(
    entry_id: str | None,
    fact_class: FactClass | None,
    epistemic: EpistemicLayer | None,
    confirmed: bool | None,
    fields: list[tuple[str, str]],
) -> ReportEntry:
    return ReportEntry(
        entry_id=entry_id,
        fact_class=fact_class,
        epistemic=epistemic,
        confirmed=confirmed,
        fields=[ReportField(name=name, value=value) for name, value in fields],
    )


def _ids(name: str, values: list[str]) -> list[tuple[str, str]]:
    if not values:
        return [(name, join_ids(values))]
    return [(name, value) for value in values]


def _confidence_fields(level: str, score: float, basis: str) -> list[tuple[str, str]]:
    return [
        ("confidence_level", level),
        ("confidence_score", score_text(score)),
        ("confidence_basis", basis),
    ]


def _legend() -> ReportSection:
    entries: list[ReportEntry] = []
    for fact_class in FactClass:
        epistemic, definition = legend_definition(fact_class)
        entries.append(
            _entry(
                fact_class.value,
                fact_class,
                epistemic,
                None,
                [("definition", definition)],
            )
        )
    return _section(ReportSectionId.PROVENANCE_LEGEND, entries)


def _incident(package: EvidencePackage) -> list[ReportSection]:
    incident = package.incident
    if incident is None:
        return []
    note_fields = [("technical_note", note) for note in incident.technical_notes]
    if not note_fields:
        note_fields = [("technical_note", join_ids([]))]
    return [
        _section(
            ReportSectionId.INCIDENT_RECORD,
            [
                _entry(
                    incident.incident_id,
                    FactClass.DERIVED_INTERPRETATION,
                    EpistemicLayer.DERIVED_INTERPRETATION,
                    False,
                    [
                        ("title", incident.title),
                        ("summary", incident.summary),
                        *_ids("call_id", list(incident.call_ids)),
                        *note_fields,
                    ],
                )
            ],
        )
    ]


def _call_identity(package: EvidencePackage) -> ReportSection:
    return _section(
        ReportSectionId.CALL_IDENTITY,
        [
            _entry(
                call.identity.call_id,
                None,
                None,
                None,
                [
                    ("call_id", call.identity.call_id),
                    ("session_id", present(call.identity.session_id)),
                ],
            )
            for call in package.calls
        ],
    )


def _call_times(package: EvidencePackage) -> ReportSection:
    return _section(
        ReportSectionId.TIMESTAMP,
        [
            _entry(
                call.identity.call_id,
                FactClass.RAW_OBSERVATION,
                EpistemicLayer.RAW_OBSERVATION,
                None,
                [
                    ("call_id", call.identity.call_id),
                    ("started_at", iso_z(call.started_at)),
                    ("ended_at", iso_z(call.ended_at)),
                ],
            )
            for call in package.calls
        ],
    )


def _displayed(package: EvidencePackage) -> ReportSection:
    return _section(
        ReportSectionId.DISPLAYED_CALLER_METADATA,
        [
            _entry(
                call.identity.call_id,
                FactClass.REPORTED_CALLER_METADATA,
                EpistemicLayer.RAW_OBSERVATION,
                None,
                [
                    ("call_id", call.identity.call_id),
                    (
                        "displayed_caller_number",
                        present(call.reported_caller_metadata.displayed_caller_number),
                    ),
                    (
                        "displayed_caller_name",
                        present(call.reported_caller_metadata.displayed_caller_name),
                    ),
                    (
                        "displayed_callee_number",
                        present(call.reported_caller_metadata.displayed_callee_number),
                    ),
                ],
            )
            for call in package.calls
        ],
    )


def _duration(package: EvidencePackage) -> ReportSection:
    return _section(
        ReportSectionId.CALL_DURATION,
        [
            _entry(
                call.identity.call_id,
                FactClass.RAW_OBSERVATION,
                EpistemicLayer.RAW_OBSERVATION,
                None,
                [
                    ("call_id", call.identity.call_id),
                    ("duration_seconds", str(call.duration_seconds)),
                ],
            )
            for call in package.calls
        ],
    )


def _excerpts(package: EvidencePackage) -> ReportSection:
    entries: list[ReportEntry] = []
    for call in package.calls:
        for excerpt in call.transcript_excerpts:
            ended = iso_z(excerpt.ended_at) if excerpt.ended_at is not None else present(None)
            entries.append(
                _entry(
                    excerpt.excerpt_id,
                    FactClass.RAW_OBSERVATION,
                    EpistemicLayer.RAW_OBSERVATION,
                    None,
                    [
                        ("call_id", excerpt.call_id),
                        ("speaker", excerpt.speaker),
                        ("started_at", iso_z(excerpt.started_at)),
                        ("ended_at", ended),
                        ("text", excerpt.text),
                    ],
                )
            )
    return _section(ReportSectionId.TRANSCRIPT_EXCERPTS, entries)


def _spoken(package: EvidencePackage) -> ReportSection:
    entries: list[ReportEntry] = []
    for call in package.calls:
        for spoken in call.spoken_identifiers:
            entries.append(
                _entry(
                    spoken.identifier_id,
                    spoken.fact_class,
                    spoken.epistemic,
                    None,
                    [
                        ("call_id", spoken.call_id),
                        ("kind", spoken.kind),
                        ("value", spoken.value),
                        ("excerpt_id", spoken.excerpt_id),
                        ("recorded_at", iso_z(spoken.recorded_at)),
                        *_confidence_fields(
                            spoken.confidence.level.value,
                            spoken.confidence.score,
                            spoken.confidence.basis,
                        ),
                    ],
                )
            )
    return _section(ReportSectionId.SPOKEN_IDENTIFIERS, entries)


def _observations(package: EvidencePackage) -> ReportSection:
    entries: list[ReportEntry] = []
    for call in package.calls:
        for observation in call.observations:
            entries.append(
                _entry(
                    observation.observation_id,
                    observation.fact_class,
                    observation.epistemic,
                    observation.confirmed,
                    [
                        ("call_id", observation.call_id),
                        ("category", observation.category),
                        ("statement", observation.statement),
                        ("recorded_at", iso_z(observation.recorded_at)),
                        *_confidence_fields(
                            observation.confidence.level.value,
                            observation.confidence.score,
                            observation.confidence.basis,
                        ),
                        ("supporting_excerpt_ids", join_ids(list(observation.supporting_excerpt_ids))),
                        (
                            "supporting_artifact_ids",
                            join_ids(list(observation.supporting_artifact_ids)),
                        ),
                    ],
                )
            )
    return _section(ReportSectionId.STRUCTURED_OBSERVATIONS, entries)


def _campaign(package: EvidencePackage) -> ReportSection:
    summary = campaign_summary_for(package)
    if not summary.associated:
        return _section(ReportSectionId.CAMPAIGN_ASSOCIATION, [])
    campaign_id = summary.campaign_id
    label = summary.label
    level = summary.confidence_level
    score = summary.confidence_score
    basis = summary.confidence_basis
    if (
        campaign_id is None
        or label is None
        or level is None
        or score is None
        or basis is None
    ):
        raise RenderError("associated campaign summary is missing campaign fields")
    return _section(
        ReportSectionId.CAMPAIGN_ASSOCIATION,
        [
            _entry(
                campaign_id,
                FactClass.DERIVED_ASSOCIATION,
                EpistemicLayer.CAMPAIGN_ATTRIBUTION,
                None,
                [
                    ("label", label),
                    *_ids("packaged_call_id", list(summary.packaged_call_ids)),
                    *_ids("member_call_id", list(summary.member_call_ids)),
                    *_confidence_fields(level.value, score, basis),
                ],
            )
        ],
    )


def _reasons(package: EvidencePackage) -> ReportSection:
    campaign = package.campaign
    if campaign is None or not campaign.reasons:
        return _section(ReportSectionId.ASSOCIATION_REASONS, [])
    return _section(
        ReportSectionId.ASSOCIATION_REASONS,
        [
            _entry(
                reason.reason_id,
                reason.fact_class,
                reason.epistemic,
                None,
                [
                    ("code", reason.code),
                    ("statement", reason.statement),
                    *_ids("call_id", list(reason.call_ids)),
                    *_confidence_fields(
                        reason.confidence.level.value,
                        reason.confidence.score,
                        reason.confidence.basis,
                    ),
                ],
            )
            for reason in campaign.reasons
        ],
    )


def _supporting_timestamps(package: EvidencePackage) -> ReportSection:
    return _section(
        ReportSectionId.SUPPORTING_TIMESTAMPS,
        [
            _entry(
                f"{row.source_id}:{row.label}:{row.at}",
                row.fact_class,
                row.epistemic,
                None,
                [
                    ("source_id", row.source_id),
                    ("label", row.label),
                    ("at", row.at),
                    ("call_id", present(row.call_id)),
                    ("excerpt_id", present(row.excerpt_id)),
                    ("artifact_id", present(row.artifact_id)),
                ],
            )
            for row in iter_timestamps(package)
        ],
    )


def _artifacts(package: EvidencePackage) -> ReportSection:
    return _section(
        ReportSectionId.RELEVANT_ARTIFACTS,
        [
            _entry(
                artifact.artifact_id,
                artifact.fact_class,
                artifact.epistemic,
                None,
                [
                    ("call_id", artifact.call_id),
                    ("kind", artifact.kind),
                    ("label", artifact.label),
                    ("uri", artifact.uri),
                    ("media_type", artifact.media_type),
                    ("sha256", present(artifact.sha256)),
                    ("inline_text", present(artifact.inline_text)),
                ],
            )
            for artifact in package.artifacts
        ],
    )


def _confidence(package: EvidencePackage) -> ReportSection:
    return _section(
        ReportSectionId.CONFIDENCE_LEVELS,
        [
            _entry(
                row.subject_id,
                row.fact_class,
                row.epistemic,
                None,
                _confidence_fields(row.level.value, row.score, row.basis),
            )
            for row in iter_confidence(package)
        ],
    )


def _stamp(
    source_id: str,
    label: str,
    at: str,
    call_id: str | None,
    excerpt_id: str | None,
    artifact_id: str | None,
    fact_class: FactClass,
    epistemic: EpistemicLayer,
) -> TimestampView:
    return TimestampView(
        source_id=source_id,
        label=label,
        at=at,
        call_id=call_id,
        excerpt_id=excerpt_id,
        artifact_id=artifact_id,
        fact_class=fact_class,
        epistemic=epistemic,
    )
