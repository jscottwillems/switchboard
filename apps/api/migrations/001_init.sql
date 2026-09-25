-- Switchboard contract 0.1.0
-- Three Postgres schemas keep observations, interpretations, and attribution apart.
-- obs rows are facts. interp rows cite obs. attr rows cite interp findings and obs sessions.
-- No foreign key points from obs back to interp or attr.

CREATE SCHEMA IF NOT EXISTS ops;
CREATE SCHEMA IF NOT EXISTS obs;
CREATE SCHEMA IF NOT EXISTS interp;
CREATE SCHEMA IF NOT EXISTS attr;

CREATE TABLE ops.operator_number (
    id uuid PRIMARY KEY,
    e164 text NOT NULL UNIQUE CHECK (e164 ~ '^\+[1-9][0-9]{1,14}$'),
    label text NOT NULL,
    status text NOT NULL CHECK (status IN ('active', 'retired')),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE obs.call_session (
    id uuid PRIMARY KEY,
    operator_number_id uuid REFERENCES ops.operator_number (id),
    external_call_id text NOT NULL,
    carrier text NOT NULL,
    caller_number_e164 text NOT NULL,
    called_number_e164 text NOT NULL,
    state text NOT NULL CHECK (state IN ('ringing', 'in_progress', 'completed', 'failed')),
    started_at timestamptz NOT NULL,
    answered_at timestamptz,
    ended_at timestamptz,
    end_reason text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (carrier, external_call_id)
);

CREATE TABLE obs.webhook_receipt (
    id uuid PRIMARY KEY,
    call_session_id uuid REFERENCES obs.call_session (id),
    provider text NOT NULL,
    event_type text NOT NULL,
    payload jsonb NOT NULL,
    signature_valid boolean,
    received_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE obs.media_stream (
    id uuid PRIMARY KEY,
    call_session_id uuid NOT NULL REFERENCES obs.call_session (id),
    external_stream_id text NOT NULL,
    protocol text NOT NULL CHECK (protocol = 'switchboard.media.v1'),
    encoding text NOT NULL CHECK (encoding IN ('audio/pcmu', 'audio/pcm')),
    sample_rate_hz integer NOT NULL CHECK (sample_rate_hz > 0),
    state text NOT NULL CHECK (state IN ('connecting', 'streaming', 'closed', 'failed')),
    started_at timestamptz NOT NULL,
    ended_at timestamptz,
    UNIQUE (call_session_id, external_stream_id)
);

CREATE TABLE obs.transcript_segment (
    id uuid PRIMARY KEY,
    call_session_id uuid NOT NULL REFERENCES obs.call_session (id),
    media_stream_id uuid NOT NULL REFERENCES obs.media_stream (id),
    sequence integer NOT NULL CHECK (sequence >= 0),
    speaker text NOT NULL CHECK (speaker IN ('caller', 'honeypot')),
    source text NOT NULL CHECK (source IN ('stt', 'tts_input')),
    text text NOT NULL,
    language text,
    start_offset_ms integer NOT NULL CHECK (start_offset_ms >= 0),
    end_offset_ms integer NOT NULL CHECK (end_offset_ms >= 0),
    is_final boolean NOT NULL,
    stt_confidence double precision CHECK (
        stt_confidence IS NULL OR (stt_confidence >= 0 AND stt_confidence <= 1)
    ),
    provider text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (call_session_id, sequence)
);

CREATE INDEX transcript_session_idx ON obs.transcript_segment (call_session_id, sequence);

CREATE TABLE interp.conversation_turn (
    id uuid PRIMARY KEY,
    call_session_id uuid NOT NULL REFERENCES obs.call_session (id),
    turn_index integer NOT NULL CHECK (turn_index >= 0),
    speaker text NOT NULL CHECK (speaker IN ('caller', 'honeypot')),
    text text NOT NULL,
    transcript_segment_ids uuid[] NOT NULL,
    strategy_id text,
    confidence double precision NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (call_session_id, turn_index)
);

CREATE TABLE interp.intelligence_finding (
    id uuid PRIMARY KEY,
    call_session_id uuid NOT NULL REFERENCES obs.call_session (id),
    kind text NOT NULL CHECK (
        kind IN (
            'callback_number',
            'pretext',
            'organization_name',
            'payment_method',
            'url',
            'person_name',
            'other'
        )
    ),
    value text NOT NULL,
    raw_quote text NOT NULL,
    transcript_segment_ids uuid[] NOT NULL CHECK (cardinality(transcript_segment_ids) >= 1),
    extractor text NOT NULL,
    extractor_version text NOT NULL,
    confidence double precision NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    status text NOT NULL CHECK (status IN ('proposed', 'accepted', 'rejected')),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX finding_session_idx ON interp.intelligence_finding (call_session_id);

CREATE TABLE attr.campaign (
    id uuid PRIMARY KEY,
    label text NOT NULL,
    status text NOT NULL CHECK (status IN ('hypothesized', 'corroborated', 'closed')),
    summary text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE attr.campaign_attribution (
    id uuid PRIMARY KEY,
    campaign_id uuid NOT NULL REFERENCES attr.campaign (id),
    call_session_id uuid NOT NULL REFERENCES obs.call_session (id),
    supporting_finding_ids uuid[] NOT NULL CHECK (cardinality(supporting_finding_ids) >= 1),
    method text NOT NULL,
    method_version text NOT NULL,
    confidence double precision NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    rationale text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX attribution_session_idx ON attr.campaign_attribution (call_session_id);
CREATE INDEX attribution_campaign_idx ON attr.campaign_attribution (campaign_id);
