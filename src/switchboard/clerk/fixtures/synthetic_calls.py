"""Labeled synthetic calls. Reports may copy these fields and no others."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from switchboard.clerk.adapters.upstream import (
    ObservationStatus,
    ProvisionalArtifact,
    ProvisionalAssociationReason,
    ProvisionalBundle,
    ProvisionalCallSession,
    ProvisionalCampaign,
    ProvisionalExcerpt,
    ProvisionalIncident,
    ProvisionalObservation,
    ProvisionalSpokenIdentifier,
    ProvisionalTimestamp,
    ProvisionalWorld,
)
from switchboard.clerk.schemas.provenance import ConfidenceLevel, PackageScope

UTC = timezone.utc
GENERATED_AT = datetime(2026, 9, 25, 18, 0, tzinfo=UTC)
EXPORT_ID = "syn-export-synthetic-001"

SIGNALING_LOG = """\
# synthetic signaling excerpt syn-call-001
SIP From: <sip:+14155550138@example.invalid>
Displayed caller number: +1-202-555-0143
P-Asserted-Identity: absent
"""
SIP_FROM_LINE = "SIP From: <sip:+14155550138@example.invalid>"
DISPLAYED_LINE = "Displayed caller number: +1-202-555-0143"
PAI_LINE = "P-Asserted-Identity: absent"
SIGNALING_SHA256 = hashlib.sha256(SIGNALING_LOG.encode("utf-8")).hexdigest()

CALL_1 = "syn-call-001"
CALL_2 = "syn-call-002"
CAMPAIGN_ID = "syn-campaign-001"
INCIDENT_ID = "syn-incident-001"
PACKAGE_SINGLE = "syn-pkg-call-001"
PACKAGE_CAMPAIGN = "syn-pkg-campaign-001"
PACKAGE_INCIDENT = "syn-pkg-incident-001"

EXCERPT_1 = "This is the Visa fraud department. I am agent Marcus."
EXCERPT_2 = "Call me back at 1-800-555-0199 if we are disconnected."
EXCERPT_3 = "I need you to install a remote access program so I can secure the account."
EXCERPT_4 = "This is the Visa fraud department. Call me back at 1-800-555-0199."
INCIDENT_SUMMARY = (
    "Synthetic incident record: displayed caller number +1-202-555-0143 "
    "is not the SIP From user +1-415-555-0138."
)
DERIVED_STATEMENT = (
    "Fixture marks opening wording as similar to synthetic script code SYN-SCRIPT-7."
)


def _basis(record_id: str) -> str:
    return f"Confidence supplied with synthetic record {record_id}."


def synthetic_world() -> ProvisionalWorld:
    """The full synthetic world. Slice it; do not treat it as a shared schema."""

    start_1 = datetime(2026, 9, 20, 15, 4, tzinfo=UTC)
    end_1 = datetime(2026, 9, 20, 15, 7, 7, tzinfo=UTC)
    excerpt_1_at = datetime(2026, 9, 20, 15, 4, 12, tzinfo=UTC)
    excerpt_2_at = datetime(2026, 9, 20, 15, 5, 40, tzinfo=UTC)
    excerpt_3_at = datetime(2026, 9, 20, 15, 6, 10, tzinfo=UTC)
    start_2 = datetime(2026, 9, 21, 13, 15, tzinfo=UTC)
    end_2 = datetime(2026, 9, 21, 13, 17, 5, tzinfo=UTC)
    excerpt_4_at = datetime(2026, 9, 21, 13, 15, 20, tzinfo=UTC)

    call_1 = ProvisionalCallSession(
        call_id=CALL_1,
        session_id="syn-session-001",
        started_at=start_1,
        ended_at=end_1,
        duration_seconds=187,
        displayed_caller_number="+1-202-555-0143",
        displayed_caller_name="CARD SERVICES",
        displayed_callee_number="+1-555-0100",
        excerpts=[
            ProvisionalExcerpt(
                excerpt_id="syn-ex-001",
                speaker="caller",
                started_at=excerpt_1_at,
                text=EXCERPT_1,
            ),
            ProvisionalExcerpt(
                excerpt_id="syn-ex-002",
                speaker="caller",
                started_at=excerpt_2_at,
                text=EXCERPT_2,
            ),
            ProvisionalExcerpt(
                excerpt_id="syn-ex-003",
                speaker="caller",
                started_at=excerpt_3_at,
                text=EXCERPT_3,
            ),
        ],
    )
    call_2 = ProvisionalCallSession(
        call_id=CALL_2,
        session_id="syn-session-002",
        started_at=start_2,
        ended_at=end_2,
        duration_seconds=125,
        displayed_caller_number="+1-202-555-0177",
        displayed_caller_name="CARD SERVICES",
        displayed_callee_number="+1-555-0100",
        excerpts=[
            ProvisionalExcerpt(
                excerpt_id="syn-ex-004",
                speaker="caller",
                started_at=excerpt_4_at,
                text=EXCERPT_4,
            )
        ],
    )
    spoken = [
        ProvisionalSpokenIdentifier(
            identifier_id="syn-spk-001",
            call_id=CALL_1,
            kind="organization",
            value="Visa",
            excerpt_id="syn-ex-001",
            recorded_at=excerpt_1_at,
            confidence_level=ConfidenceLevel.HIGH,
            confidence_score=0.86,
            confidence_basis=_basis("syn-spk-001"),
        ),
        ProvisionalSpokenIdentifier(
            identifier_id="syn-spk-002",
            call_id=CALL_1,
            kind="person_name",
            value="Marcus",
            excerpt_id="syn-ex-001",
            recorded_at=excerpt_1_at,
            confidence_level=ConfidenceLevel.HIGH,
            confidence_score=0.80,
            confidence_basis=_basis("syn-spk-002"),
        ),
        ProvisionalSpokenIdentifier(
            identifier_id="syn-spk-003",
            call_id=CALL_1,
            kind="callback_number",
            value="1-800-555-0199",
            excerpt_id="syn-ex-002",
            recorded_at=excerpt_2_at,
            confidence_level=ConfidenceLevel.HIGH,
            confidence_score=0.92,
            confidence_basis=_basis("syn-spk-003"),
        ),
        ProvisionalSpokenIdentifier(
            identifier_id="syn-spk-004",
            call_id=CALL_2,
            kind="organization",
            value="Visa",
            excerpt_id="syn-ex-004",
            recorded_at=excerpt_4_at,
            confidence_level=ConfidenceLevel.HIGH,
            confidence_score=0.84,
            confidence_basis=_basis("syn-spk-004"),
        ),
        ProvisionalSpokenIdentifier(
            identifier_id="syn-spk-005",
            call_id=CALL_2,
            kind="callback_number",
            value="1-800-555-0199",
            excerpt_id="syn-ex-004",
            recorded_at=excerpt_4_at,
            confidence_level=ConfidenceLevel.HIGH,
            confidence_score=0.88,
            confidence_basis=_basis("syn-spk-005"),
        ),
    ]
    observations = [
        ProvisionalObservation(
            observation_id="syn-obs-001",
            call_id=CALL_1,
            category="impersonation",
            statement="This is the Visa fraud department.",
            status=ObservationStatus.CONFIRMED,
            confidence_level=ConfidenceLevel.HIGH,
            confidence_score=0.90,
            confidence_basis=_basis("syn-obs-001"),
            recorded_at=excerpt_1_at,
            supporting_excerpt_ids=["syn-ex-001"],
        ),
        ProvisionalObservation(
            observation_id="syn-obs-002",
            call_id=CALL_1,
            category="requested_action",
            statement=EXCERPT_3,
            status=ObservationStatus.RAW,
            confidence_level=ConfidenceLevel.MEDIUM,
            confidence_score=0.55,
            confidence_basis=_basis("syn-obs-002"),
            recorded_at=excerpt_3_at,
            supporting_excerpt_ids=["syn-ex-003"],
        ),
        ProvisionalObservation(
            observation_id="syn-obs-003",
            call_id=CALL_1,
            category="script_similarity",
            statement=DERIVED_STATEMENT,
            status=ObservationStatus.DERIVED,
            confidence_level=ConfidenceLevel.LOW,
            confidence_score=0.35,
            confidence_basis=_basis("syn-obs-003"),
            recorded_at=excerpt_1_at,
            supporting_excerpt_ids=["syn-ex-001"],
        ),
        ProvisionalObservation(
            observation_id="syn-obs-004",
            call_id=CALL_1,
            category="signaling",
            statement=SIP_FROM_LINE,
            status=ObservationStatus.CONFIRMED,
            confidence_level=ConfidenceLevel.HIGH,
            confidence_score=0.95,
            confidence_basis=_basis("syn-obs-004"),
            recorded_at=start_1,
            supporting_artifact_ids=["syn-art-001"],
        ),
        ProvisionalObservation(
            observation_id="syn-obs-005",
            call_id=CALL_2,
            category="impersonation",
            statement="This is the Visa fraud department.",
            status=ObservationStatus.CONFIRMED,
            confidence_level=ConfidenceLevel.HIGH,
            confidence_score=0.90,
            confidence_basis=_basis("syn-obs-005"),
            recorded_at=excerpt_4_at,
            supporting_excerpt_ids=["syn-ex-004"],
        ),
    ]
    campaign = ProvisionalCampaign(
        campaign_id=CAMPAIGN_ID,
        label="Synthetic card-issuer impersonation",
        member_call_ids=[CALL_1, CALL_2],
        reasons=[
            ProvisionalAssociationReason(
                reason_id="syn-reason-001",
                code="shared_spoken_callback",
                statement="Both calls include spoken callback number 1-800-555-0199.",
                call_ids=[CALL_1, CALL_2],
                timestamps=[
                    ProvisionalTimestamp(
                        label="excerpt.started_at",
                        at=excerpt_2_at,
                        call_id=CALL_1,
                        excerpt_id="syn-ex-002",
                    ),
                    ProvisionalTimestamp(
                        label="excerpt.started_at",
                        at=excerpt_4_at,
                        call_id=CALL_2,
                        excerpt_id="syn-ex-004",
                    ),
                ],
                confidence_level=ConfidenceLevel.HIGH,
                confidence_score=0.92,
                confidence_basis=_basis("syn-reason-001"),
            ),
            ProvisionalAssociationReason(
                reason_id="syn-reason-002",
                code="shared_displayed_cnam",
                statement="Both calls display caller name CARD SERVICES.",
                call_ids=[CALL_1, CALL_2],
                timestamps=[
                    ProvisionalTimestamp(
                        label="call.started_at",
                        at=start_1,
                        call_id=CALL_1,
                    ),
                    ProvisionalTimestamp(
                        label="call.started_at",
                        at=start_2,
                        call_id=CALL_2,
                    ),
                ],
                confidence_level=ConfidenceLevel.MEDIUM,
                confidence_score=0.60,
                confidence_basis=_basis("syn-reason-002"),
            ),
        ],
        confidence_level=ConfidenceLevel.HIGH,
        confidence_score=0.80,
        confidence_basis=_basis(CAMPAIGN_ID),
    )
    incident = ProvisionalIncident(
        incident_id=INCIDENT_ID,
        title="Synthetic signaling mismatch on syn-call-001",
        summary=INCIDENT_SUMMARY,
        call_ids=[CALL_1],
        technical_notes=[SIP_FROM_LINE, DISPLAYED_LINE, PAI_LINE],
    )
    return ProvisionalWorld(
        generated_at=GENERATED_AT,
        calls=[call_1, call_2],
        spoken_identifiers=spoken,
        observations=observations,
        artifacts=[
            ProvisionalArtifact(
                artifact_id="syn-art-001",
                call_id=CALL_1,
                kind="signaling_log",
                label="Synthetic SIP signaling excerpt",
                uri="synthetic://artifacts/syn-call-001/signaling.log",
                media_type="text/plain",
                inline_text=SIGNALING_LOG,
                sha256=SIGNALING_SHA256,
            )
        ],
        campaign=campaign,
        incident=incident,
    )


def synthetic_bundles() -> tuple[ProvisionalBundle, ProvisionalBundle, ProvisionalBundle]:
    """Single-call, multi-call campaign, and technical incident slices."""

    world = synthetic_world()
    return (
        world.slice(
            package_id=PACKAGE_SINGLE,
            scope=PackageScope.SINGLE_CALL,
            call_ids=[CALL_1],
            include_campaign=True,
            include_incident=False,
        ),
        world.slice(
            package_id=PACKAGE_CAMPAIGN,
            scope=PackageScope.CAMPAIGN,
            call_ids=[CALL_1, CALL_2],
            include_campaign=True,
            include_incident=False,
        ),
        world.slice(
            package_id=PACKAGE_INCIDENT,
            scope=PackageScope.TECHNICAL_INCIDENT,
            call_ids=[CALL_1],
            include_campaign=False,
            include_incident=True,
        ),
    )
