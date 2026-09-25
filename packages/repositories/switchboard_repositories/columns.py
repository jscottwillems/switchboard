"""Column lists for the tables in apps/api/migrations/001_init.sql.

Findings have no campaign column. Do not add one here.
"""

CALL_SESSION_COLUMNS = """
    id,
    operator_number_id,
    external_call_id,
    carrier,
    caller_number_e164,
    called_number_e164,
    state,
    started_at,
    answered_at,
    ended_at,
    end_reason
"""

OPERATOR_NUMBER_COLUMNS = """
    id,
    e164,
    label,
    status,
    created_at
"""

WEBHOOK_RECEIPT_COLUMNS = """
    id,
    call_session_id,
    provider,
    event_type,
    payload,
    signature_valid,
    received_at
"""

MEDIA_STREAM_COLUMNS = """
    id,
    call_session_id,
    external_stream_id,
    protocol,
    encoding,
    sample_rate_hz,
    state,
    started_at,
    ended_at
"""

TRANSCRIPT_COLUMNS = """
    id,
    call_session_id,
    media_stream_id,
    sequence,
    speaker,
    source,
    text,
    language,
    start_offset_ms,
    end_offset_ms,
    is_final,
    stt_confidence,
    provider,
    created_at
"""

CONVERSATION_TURN_COLUMNS = """
    id,
    call_session_id,
    turn_index,
    speaker,
    text,
    transcript_segment_ids,
    strategy_id,
    confidence,
    created_at
"""

FINDING_COLUMNS = """
    id,
    call_session_id,
    kind,
    value,
    raw_quote,
    transcript_segment_ids,
    extractor,
    extractor_version,
    confidence,
    status,
    created_at
"""

CAMPAIGN_COLUMNS = """
    id,
    label,
    status,
    summary,
    created_at,
    updated_at
"""

ATTRIBUTION_COLUMNS = """
    id,
    campaign_id,
    call_session_id,
    supporting_finding_ids,
    method,
    method_version,
    confidence,
    rationale,
    created_at
"""
