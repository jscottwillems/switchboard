/**
 * Hand-mirrored wire types for contract version 0.1.0.
 * Canonical source: packages/schemas/switchboard_schemas (Pydantic).
 * Change Python first, then update this file in the same pull request.
 * Field names match JSON produced by Pydantic (snake_case).
 */

export const CONTRACT_VERSION = "0.1.0";
export const MEDIA_PROTOCOL = "switchboard.media.v1";

export type RecordLayer = "observation" | "interpretation" | "attribution";

export type CallState = "ringing" | "in_progress" | "completed" | "failed";

export type MediaStreamState = "connecting" | "streaming" | "closed" | "failed";

export type Speaker = "caller" | "honeypot";

export type TranscriptSource = "stt" | "tts_input";

export type FindingKind =
  | "callback_number"
  | "pretext"
  | "organization_name"
  | "payment_method"
  | "url"
  | "person_name"
  | "other";

export type FindingStatus = "proposed" | "accepted" | "rejected";

export type CampaignStatus = "hypothesized" | "corroborated" | "closed";

export type EventType =
  | "telephony.call.received"
  | "telephony.call.answered"
  | "telephony.call.completed"
  | "telephony.call.failed"
  | "media.stream.started"
  | "media.stream.stopped"
  | "media.stream.failed"
  | "speech.segment.partial"
  | "speech.segment.final"
  | "speech.synthesis.requested"
  | "speech.synthesis.completed"
  | "speech.synthesis.failed"
  | "conversation.response.selected"
  | "conversation.turn.recorded"
  | "intelligence.finding.proposed"
  | "campaign.opened"
  | "campaign.attribution.proposed";

export interface OperatorNumber {
  id: string;
  e164: string;
  label: string;
  status: "active" | "retired";
  created_at: string;
}

export interface CallSession {
  record_layer: "observation";
  id: string;
  operator_number_id: string | null;
  external_call_id: string;
  carrier: string;
  caller_number_e164: string;
  called_number_e164: string;
  state: CallState;
  started_at: string;
  answered_at: string | null;
  ended_at: string | null;
  end_reason: string | null;
}

export interface MediaStream {
  record_layer: "observation";
  id: string;
  call_session_id: string;
  external_stream_id: string;
  protocol: "switchboard.media.v1";
  encoding: "audio/pcmu" | "audio/pcm";
  sample_rate_hz: number;
  state: MediaStreamState;
  started_at: string;
  ended_at: string | null;
}

export interface TranscriptSegment {
  record_layer: "observation";
  id: string;
  call_session_id: string;
  media_stream_id: string;
  sequence: number;
  speaker: Speaker;
  source: TranscriptSource;
  text: string;
  language: string | null;
  start_offset_ms: number;
  end_offset_ms: number;
  is_final: boolean;
  /** Provider score. Not Switchboard interpretation confidence. */
  stt_confidence: number | null;
  provider: string;
  created_at: string;
}

export interface ConversationTurn {
  record_layer: "interpretation";
  id: string;
  call_session_id: string;
  turn_index: number;
  speaker: Speaker;
  text: string;
  transcript_segment_ids: string[];
  strategy_id: string | null;
  confidence: number;
  created_at: string;
}

export interface IntelligenceFinding {
  record_layer: "interpretation";
  id: string;
  call_session_id: string;
  kind: FindingKind;
  value: string;
  raw_quote: string;
  transcript_segment_ids: string[];
  extractor: string;
  extractor_version: string;
  confidence: number;
  status: FindingStatus;
  created_at: string;
}

export interface Campaign {
  record_layer: "attribution";
  id: string;
  label: string;
  status: CampaignStatus;
  summary: string | null;
  created_at: string;
  updated_at: string;
}

export interface CampaignAttribution {
  record_layer: "attribution";
  id: string;
  campaign_id: string;
  call_session_id: string;
  supporting_finding_ids: string[];
  method: string;
  method_version: string;
  confidence: number;
  rationale: string;
  created_at: string;
}

export interface CallSessionSummary {
  id: string;
  state: CallState;
  caller_number_e164: string;
  called_number_e164: string;
  started_at: string;
  ended_at: string | null;
}

export interface CallListResponse {
  items: CallSessionSummary[];
  next_cursor: string | null;
}

export interface CallDetailResponse {
  session: CallSession;
  media_streams: MediaStream[];
  transcript: TranscriptSegment[];
  turns: ConversationTurn[];
  findings: IntelligenceFinding[];
  attributions: CampaignAttribution[];
}

export interface ErrorBody {
  error: string;
  message: string;
}

export interface EventEnvelope {
  event_id: string;
  event_type: EventType;
  event_version: 1;
  occurred_at: string;
  producer: "api" | "media_gateway" | "intelligence";
  call_session_id: string;
  causation_id: string | null;
  payload: Record<string, unknown>;
}

export function callStateLabel(state: CallState): string {
  switch (state) {
    case "ringing":
      return "Ringing";
    case "in_progress":
      return "In progress";
    case "completed":
      return "Completed";
    case "failed":
      return "Failed";
    default: {
      const exhaustive: never = state;
      return exhaustive;
    }
  }
}
