"""Campaign list and detail read stored attr rows through the repository port."""

from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from switchboard_api.deps import open_observation_writer
from switchboard_api.main import app
from switchboard_intelligence.correlator_worker import propose_callback_campaigns
from switchboard_intelligence.deps import open_attribution_writer, open_finding_writer
from switchboard_schemas.api import AttributionListResponse, CampaignListResponse
from switchboard_schemas.attribution import Campaign
from switchboard_schemas.enums import (
    CallState,
    CampaignStatus,
    FindingKind,
    FindingStatus,
)
from switchboard_schemas.interpretations import IntelligenceFinding
from switchboard_schemas.observations import CallSession

from tests.db_support import database_url as configured_database_url
from tests.db_support import truncate_records
from tests.operator_support import OPERATOR_HEADERS

client = TestClient(app, headers=OPERATOR_HEADERS)

NOW = datetime(2026, 9, 25, 22, 0, tzinfo=timezone.utc)
DEV_OPERATOR_ID = UUID("00000000-0000-4000-8000-000000000001")
SHARED = "+15551234567"


@pytest.fixture
def database_url() -> Iterator[str]:
    url = configured_database_url()
    truncate_records(url)
    yield url
    truncate_records(url)


def _session(external: str) -> CallSession:
    return CallSession(
        id=uuid4(),
        operator_number_id=DEV_OPERATOR_ID,
        external_call_id=external,
        carrier="mock",
        caller_number_e164="+15551212000",
        called_number_e164="+15550001001",
        state=CallState.RINGING,
        started_at=NOW,
    )


def _finding(call_session_id: UUID, created_at: datetime) -> IntelligenceFinding:
    return IntelligenceFinding(
        id=uuid4(),
        call_session_id=call_session_id,
        kind=FindingKind.CALLBACK_NUMBER,
        value=SHARED,
        raw_quote=SHARED,
        transcript_segment_ids=[uuid4()],
        extractor="e164",
        extractor_version="0.1.0",
        confidence=1.0,
        status=FindingStatus.PROPOSED,
        created_at=created_at,
    )


def test_empty_list_and_unknown_campaign(database_url: str) -> None:
    del database_url
    listing = client.get("/v1/campaigns")
    assert listing.status_code == 200
    assert listing.json() == {"items": [], "next_cursor": None}
    missing = client.get(f"/v1/campaigns/{uuid4()}")
    assert missing.status_code == 404
    assert missing.json() == {
        "error": "campaign_not_found",
        "message": "No campaign exists with that id.",
    }


def test_limit_bounds_and_bad_cursor_are_invalid_requests(database_url: str) -> None:
    del database_url
    for limit in (0, 201):
        response = client.get("/v1/campaigns", params={"limit": limit})
        assert response.status_code == 422
        assert response.json()["error"] == "invalid_request"
    rejected = client.get("/v1/campaigns", params={"cursor": "not-a-cursor"})
    assert rejected.status_code == 422
    body = rejected.json()
    assert body["error"] == "invalid_request"
    assert "not-a-cursor" not in body["message"]


def test_list_default_limit_is_50() -> None:
    parameters = client.app.openapi()["paths"]["/v1/campaigns"]["get"]["parameters"]
    limit = next(item for item in parameters if item["name"] == "limit")
    assert limit["schema"]["default"] == 50
    assert limit["schema"]["minimum"] == 1
    assert limit["schema"]["maximum"] == 200


def test_list_pages_newest_created_at_first(database_url: str) -> None:
    del database_url
    older = Campaign(
        id=uuid4(),
        label="older cluster",
        status=CampaignStatus.HYPOTHESIZED,
        summary=None,
        created_at=NOW,
        updated_at=NOW,
    )
    newer = Campaign(
        id=uuid4(),
        label="newer cluster",
        status=CampaignStatus.CLOSED,
        summary="closed after review",
        created_at=NOW + timedelta(seconds=5),
        updated_at=NOW + timedelta(seconds=9),
    )
    with open_attribution_writer() as writer:
        stored_older, _ = writer.campaigns().insert(older)
        stored_newer, _ = writer.campaigns().insert(newer)

    first = client.get("/v1/campaigns", params={"limit": 1})
    assert first.status_code == 200
    first_page = CampaignListResponse.model_validate(first.json())
    assert first_page.items == [stored_newer]
    assert first_page.next_cursor is not None
    assert "call_count" not in first.json()["items"][0]

    second = client.get("/v1/campaigns", params={"limit": 1, "cursor": first_page.next_cursor})
    assert second.status_code == 200
    second_page = CampaignListResponse.model_validate(second.json())
    assert second_page.items == [stored_older]
    assert second_page.next_cursor is None

    detail = client.get(f"/v1/campaigns/{stored_older.id}")
    assert detail.status_code == 200
    assert Campaign.model_validate(detail.json()) == stored_older
    assert detail.json()["record_layer"] == "attribution"
    assert set(detail.json()) == {
        "record_layer",
        "id",
        "label",
        "status",
        "summary",
        "created_at",
        "updated_at",
    }


def test_shared_callback_campaign_is_on_the_read_api(database_url: str) -> None:
    del database_url
    with open_observation_writer() as writer:
        left, _ = writer.call_sessions().insert_ringing(_session("shared-left"))
        right, _ = writer.call_sessions().insert_ringing(_session("shared-right"))
    with open_finding_writer() as writer:
        left_finding, _ = writer.findings().insert(_finding(left.id, NOW))
        right_finding, _ = writer.findings().insert(
            _finding(right.id, NOW + timedelta(seconds=30))
        )

    waiting, waiting_rows = propose_callback_campaigns([left_finding])
    assert waiting == []
    assert waiting_rows == []
    assert client.get("/v1/campaigns").json() == {"items": [], "next_cursor": None}

    campaigns, attributions = propose_callback_campaigns([left_finding, right_finding])
    assert len(campaigns) == 1
    assert len(attributions) == 2
    with open_attribution_writer() as writer:
        stored_campaign, created = writer.campaigns().insert(campaigns[0])
        assert created
        stored_rows = []
        for row in attributions:
            stored, inserted = writer.attributions().insert(row)
            assert inserted
            stored_rows.append(stored)

    listing = client.get("/v1/campaigns")
    assert listing.status_code == 200
    page = CampaignListResponse.model_validate(listing.json())
    assert page.items == [stored_campaign]
    assert page.next_cursor is None
    assert page.items[0].status is CampaignStatus.HYPOTHESIZED
    assert page.items[0].label == f"callback {SHARED}"

    detail = client.get(f"/v1/campaigns/{stored_campaign.id}")
    assert detail.status_code == 200
    assert Campaign.model_validate(detail.json()) == stored_campaign
    assert SHARED in detail.json()["summary"]

    by_call = {row.call_session_id: row for row in stored_rows}
    assert set(by_call) == {left.id, right.id}
    for session_id, expected in by_call.items():
        linked = client.get(f"/v1/calls/{session_id}/attributions")
        assert linked.status_code == 200
        body = AttributionListResponse.model_validate(linked.json())
        assert body.attributions == [expected]
        assert body.attributions[0].campaign_id == stored_campaign.id
        assert body.attributions[0].record_layer == "attribution"
