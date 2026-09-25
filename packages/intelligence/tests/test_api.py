"""HTTP smoke test for the local extract endpoint."""

from fastapi.testclient import TestClient

from switchboard_intelligence.api import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_extract_endpoint_returns_distinct_record_types() -> None:
    response = client.post(
        "/v1/intelligence/extract",
        json={
            "call_id": "api-1",
            "segments": [
                {
                    "segment_id": "api-1-s00",
                    "speaker": "scammer",
                    "text": "I am calling from Medicare, fraud department. The processing fee is $49.95.",
                    "start_timestamp": 0,
                    "end_timestamp": 5,
                }
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["call_id"] == "api-1"
    assert body["schema_version"] == "sherlock.intelligence.v1"
    assert {item["record_type"] for item in body["observations"]} == {"observation"}
    assert {item["record_type"] for item in body["inferences"]} == {"inference"}
    assert body["attributions"] == []
    kinds = {item["kind"] for item in body["observations"]}
    assert "claimed_company" in kinds
    assert "fees" in kinds


def test_extract_endpoint_rejects_a_bad_transcript() -> None:
    response = client.post("/v1/intelligence/extract", json={"call_id": "api-2", "segments": []})
    assert response.status_code == 422
