"""CSV tables projected from an evidence package."""

from __future__ import annotations

import csv
import io

from switchboard.clerk.render.format import iso_z, score_text
from switchboard.clerk.render.project import campaign_summary_for, iter_confidence, iter_timestamps
from switchboard.clerk.schemas.evidence import EvidencePackage
from switchboard.clerk.schemas.reports import CampaignSummary

CSV_FILENAMES: tuple[str, ...] = (
    "artifacts.csv",
    "association_reasons.csv",
    "calls.csv",
    "campaign_summary.csv",
    "confidence.csv",
    "observations.csv",
    "spoken_identifiers.csv",
    "supporting_timestamps.csv",
    "transcript_excerpts.csv",
)
_ID_SEPARATOR = "|"


def render_csvs(package: EvidencePackage) -> dict[str, str]:
    summary = campaign_summary_for(package)
    files = {
        "calls.csv": _calls(package),
        "transcript_excerpts.csv": _excerpts(package),
        "spoken_identifiers.csv": _spoken(package),
        "observations.csv": _observations(package),
        "association_reasons.csv": _reasons(package),
        "artifacts.csv": _artifacts(package),
        "confidence.csv": _confidence(package),
        "supporting_timestamps.csv": _timestamps(package),
        "campaign_summary.csv": _summary(summary),
    }
    if tuple(sorted(files)) != CSV_FILENAMES:
        raise RuntimeError("csv filenames drifted from CSV_FILENAMES")
    return files


def _calls(package: EvidencePackage) -> str:
    rows: list[list[str]] = []
    for call in package.calls:
        metadata = call.reported_caller_metadata
        rows.append(
            [
                call.identity.call_id,
                _optional(call.identity.session_id),
                iso_z(call.started_at),
                iso_z(call.ended_at),
                str(call.duration_seconds),
                _optional(metadata.displayed_caller_number),
                _optional(metadata.displayed_caller_name),
                _optional(metadata.displayed_callee_number),
                metadata.fact_class.value,
                metadata.epistemic.value,
            ]
        )
    return _table(
        [
            "call_id",
            "session_id",
            "started_at",
            "ended_at",
            "duration_seconds",
            "displayed_caller_number",
            "displayed_caller_name",
            "displayed_callee_number",
            "displayed_fact_class",
            "displayed_epistemic",
        ],
        rows,
    )


def _excerpts(package: EvidencePackage) -> str:
    rows: list[list[str]] = []
    for call in package.calls:
        for excerpt in call.transcript_excerpts:
            rows.append(
                [
                    excerpt.excerpt_id,
                    excerpt.call_id,
                    excerpt.speaker,
                    iso_z(excerpt.started_at),
                    iso_z(excerpt.ended_at) if excerpt.ended_at is not None else "",
                    excerpt.text,
                    excerpt.fact_class.value,
                    excerpt.epistemic.value,
                ]
            )
    return _table(
        [
            "excerpt_id",
            "call_id",
            "speaker",
            "started_at",
            "ended_at",
            "text",
            "fact_class",
            "epistemic",
        ],
        rows,
    )


def _spoken(package: EvidencePackage) -> str:
    rows: list[list[str]] = []
    for call in package.calls:
        for spoken in call.spoken_identifiers:
            rows.append(
                [
                    spoken.identifier_id,
                    spoken.call_id,
                    spoken.kind,
                    spoken.value,
                    spoken.excerpt_id,
                    iso_z(spoken.recorded_at),
                    spoken.confidence.level.value,
                    score_text(spoken.confidence.score),
                    spoken.confidence.basis,
                    spoken.fact_class.value,
                    spoken.epistemic.value,
                ]
            )
    return _table(
        [
            "identifier_id",
            "call_id",
            "kind",
            "value",
            "excerpt_id",
            "recorded_at",
            "confidence_level",
            "confidence_score",
            "confidence_basis",
            "fact_class",
            "epistemic",
        ],
        rows,
    )


def _observations(package: EvidencePackage) -> str:
    rows: list[list[str]] = []
    for call in package.calls:
        for observation in call.observations:
            rows.append(
                [
                    observation.observation_id,
                    observation.call_id,
                    observation.category,
                    observation.statement,
                    str(observation.confirmed).lower(),
                    observation.fact_class.value,
                    observation.epistemic.value,
                    iso_z(observation.recorded_at),
                    observation.confidence.level.value,
                    score_text(observation.confidence.score),
                    observation.confidence.basis,
                    _ID_SEPARATOR.join(observation.supporting_excerpt_ids),
                    _ID_SEPARATOR.join(observation.supporting_artifact_ids),
                ]
            )
    return _table(
        [
            "observation_id",
            "call_id",
            "category",
            "statement",
            "confirmed",
            "fact_class",
            "epistemic",
            "recorded_at",
            "confidence_level",
            "confidence_score",
            "confidence_basis",
            "supporting_excerpt_ids",
            "supporting_artifact_ids",
        ],
        rows,
    )


def _reasons(package: EvidencePackage) -> str:
    rows: list[list[str]] = []
    campaign = package.campaign
    if campaign is not None:
        for reason in campaign.reasons:
            rows.append(
                [
                    reason.reason_id,
                    campaign.campaign_id,
                    reason.code,
                    reason.statement,
                    _ID_SEPARATOR.join(reason.call_ids),
                    reason.confidence.level.value,
                    score_text(reason.confidence.score),
                    reason.confidence.basis,
                    reason.fact_class.value,
                    reason.epistemic.value,
                ]
            )
    return _table(
        [
            "reason_id",
            "campaign_id",
            "code",
            "statement",
            "call_ids",
            "confidence_level",
            "confidence_score",
            "confidence_basis",
            "fact_class",
            "epistemic",
        ],
        rows,
    )


def _artifacts(package: EvidencePackage) -> str:
    rows = [
        [
            artifact.artifact_id,
            artifact.call_id,
            artifact.kind,
            artifact.label,
            artifact.uri,
            artifact.media_type,
            _optional(artifact.sha256),
            artifact.fact_class.value,
            artifact.epistemic.value,
            _optional(artifact.inline_text),
        ]
        for artifact in package.artifacts
    ]
    return _table(
        [
            "artifact_id",
            "call_id",
            "kind",
            "label",
            "uri",
            "media_type",
            "sha256",
            "fact_class",
            "epistemic",
            "inline_text",
        ],
        rows,
    )


def _confidence(package: EvidencePackage) -> str:
    rows = [
        [
            row.subject_id,
            row.fact_class.value,
            row.epistemic.value,
            row.level.value,
            score_text(row.score),
            row.basis,
        ]
        for row in iter_confidence(package)
    ]
    return _table(
        [
            "subject_id",
            "fact_class",
            "epistemic",
            "confidence_level",
            "confidence_score",
            "confidence_basis",
        ],
        rows,
    )


def _timestamps(package: EvidencePackage) -> str:
    rows: list[list[str]] = []
    for row in iter_timestamps(package):
        fact_class = "" if row.fact_class is None else row.fact_class.value
        epistemic = "" if row.epistemic is None else row.epistemic.value
        rows.append(
            [
                row.source_id,
                row.label,
                row.at,
                _optional(row.call_id),
                _optional(row.excerpt_id),
                _optional(row.artifact_id),
                fact_class,
                epistemic,
            ]
        )
    return _table(
        [
            "source_id",
            "label",
            "at",
            "call_id",
            "excerpt_id",
            "artifact_id",
            "fact_class",
            "epistemic",
        ],
        rows,
    )


def _summary(summary: CampaignSummary) -> str:
    fact_class = "" if summary.fact_class is None else summary.fact_class.value
    epistemic = "" if summary.epistemic is None else summary.epistemic.value
    level = "" if summary.confidence_level is None else summary.confidence_level.value
    score = "" if summary.confidence_score is None else score_text(summary.confidence_score)
    basis = "" if summary.confidence_basis is None else summary.confidence_basis
    return _table(
        [
            "package_id",
            "synthetic",
            "associated",
            "campaign_id",
            "label",
            "fact_class",
            "epistemic",
            "confidence_level",
            "confidence_score",
            "confidence_basis",
            "packaged_call_ids",
            "member_call_ids",
            "reason_codes",
        ],
        [
            [
                summary.package_id,
                str(summary.synthetic).lower(),
                str(summary.associated).lower(),
                _optional(summary.campaign_id),
                _optional(summary.label),
                fact_class,
                epistemic,
                level,
                score,
                basis,
                _ID_SEPARATOR.join(summary.packaged_call_ids),
                _ID_SEPARATOR.join(summary.member_call_ids),
                _ID_SEPARATOR.join(summary.reason_codes),
            ]
        ],
    )


def _optional(value: str | None) -> str:
    if value is None:
        return ""
    return value


def _cell(value: str) -> str:
    if value.startswith(("=", "@", "\t", "\r")):
        return "'" + value
    return value


def _table(headers: list[str], rows: list[list[str]]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(headers)
    for row in rows:
        writer.writerow([_cell(value) for value in row])
    return buffer.getvalue()
