"""Map 001_init.sql rows onto the canonical Pydantic models."""

import json
from typing import Any, Mapping

from switchboard_schemas.attribution import Campaign, CampaignAttribution
from switchboard_schemas.interpretations import ConversationTurn, IntelligenceFinding
from switchboard_schemas.observations import (
    CallSession,
    MediaStream,
    OperatorNumber,
    TranscriptSegment,
    WebhookReceipt,
)


def operator_number_from_row(row: Mapping[str, Any]) -> OperatorNumber:
    return OperatorNumber.model_validate(
        {
            "id": row["id"],
            "e164": row["e164"],
            "label": row["label"],
            "status": row["status"],
            "created_at": row["created_at"],
        }
    )


def call_session_from_row(row: Mapping[str, Any]) -> CallSession:
    return CallSession.model_validate(
        {
            "id": row["id"],
            "operator_number_id": row["operator_number_id"],
            "external_call_id": row["external_call_id"],
            "carrier": row["carrier"],
            "caller_number_e164": row["caller_number_e164"],
            "called_number_e164": row["called_number_e164"],
            "state": row["state"],
            "started_at": row["started_at"],
            "answered_at": row["answered_at"],
            "ended_at": row["ended_at"],
            "end_reason": row["end_reason"],
        }
    )


def webhook_receipt_from_row(row: Mapping[str, Any]) -> WebhookReceipt:
    return WebhookReceipt.model_validate(
        {
            "id": row["id"],
            "call_session_id": row["call_session_id"],
            "provider": row["provider"],
            "event_type": row["event_type"],
            "payload": _json_object(row["payload"]),
            "signature_valid": row["signature_valid"],
            "received_at": row["received_at"],
        }
    )


def media_stream_from_row(row: Mapping[str, Any]) -> MediaStream:
    return MediaStream.model_validate(
        {
            "id": row["id"],
            "call_session_id": row["call_session_id"],
            "external_stream_id": row["external_stream_id"],
            "protocol": row["protocol"],
            "encoding": row["encoding"],
            "sample_rate_hz": row["sample_rate_hz"],
            "state": row["state"],
            "started_at": row["started_at"],
            "ended_at": row["ended_at"],
        }
    )


def transcript_from_row(row: Mapping[str, Any]) -> TranscriptSegment:
    return TranscriptSegment.model_validate(
        {
            "id": row["id"],
            "call_session_id": row["call_session_id"],
            "media_stream_id": row["media_stream_id"],
            "sequence": row["sequence"],
            "speaker": row["speaker"],
            "source": row["source"],
            "text": row["text"],
            "language": row["language"],
            "start_offset_ms": row["start_offset_ms"],
            "end_offset_ms": row["end_offset_ms"],
            "is_final": row["is_final"],
            "stt_confidence": row["stt_confidence"],
            "provider": row["provider"],
            "created_at": row["created_at"],
        }
    )


def conversation_turn_from_row(row: Mapping[str, Any]) -> ConversationTurn:
    return ConversationTurn.model_validate(
        {
            "id": row["id"],
            "call_session_id": row["call_session_id"],
            "turn_index": row["turn_index"],
            "speaker": row["speaker"],
            "text": row["text"],
            "transcript_segment_ids": list(row["transcript_segment_ids"]),
            "strategy_id": row["strategy_id"],
            "confidence": row["confidence"],
            "created_at": row["created_at"],
        }
    )


def finding_from_row(row: Mapping[str, Any]) -> IntelligenceFinding:
    return IntelligenceFinding.model_validate(
        {
            "id": row["id"],
            "call_session_id": row["call_session_id"],
            "kind": row["kind"],
            "value": row["value"],
            "raw_quote": row["raw_quote"],
            "transcript_segment_ids": list(row["transcript_segment_ids"]),
            "extractor": row["extractor"],
            "extractor_version": row["extractor_version"],
            "confidence": row["confidence"],
            "status": row["status"],
            "created_at": row["created_at"],
        }
    )


def campaign_from_row(row: Mapping[str, Any]) -> Campaign:
    return Campaign.model_validate(
        {
            "id": row["id"],
            "label": row["label"],
            "status": row["status"],
            "summary": row["summary"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
    )


def attribution_from_row(row: Mapping[str, Any]) -> CampaignAttribution:
    return CampaignAttribution.model_validate(
        {
            "id": row["id"],
            "campaign_id": row["campaign_id"],
            "call_session_id": row["call_session_id"],
            "supporting_finding_ids": list(row["supporting_finding_ids"]),
            "method": row["method"],
            "method_version": row["method_version"],
            "confidence": row["confidence"],
            "rationale": row["rationale"],
            "created_at": row["created_at"],
        }
    )


def _json_object(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return parsed
    raise TypeError("webhook payload must be a JSON object")
