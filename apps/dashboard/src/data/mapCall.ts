import type { CallDetail, CallGaps, CallSummary, LiveCall } from '@/types/models'
import type { CallDetailResponse, CallSession, CallSessionSummary, CampaignAttribution } from '@switchboard/schemas'

function elapsedMs(startedAt: string, endedAt: string | null, nowMs: number): number {
  const start = Date.parse(startedAt)
  if (Number.isNaN(start)) return 0
  const end = endedAt === null ? nowMs : Date.parse(endedAt)
  if (Number.isNaN(end)) return 0
  return Math.max(0, end - start)
}

function engagementMs(answeredAt: string | null, endedAt: string | null, nowMs: number): number | null {
  if (answeredAt === null) return null
  const start = Date.parse(answeredAt)
  if (Number.isNaN(start)) return null
  const end = endedAt === null ? nowMs : Date.parse(endedAt)
  if (Number.isNaN(end)) return null
  return Math.max(0, end - start)
}

/**
 * Gap columns the screens already render. Values are derived from the read model
 * or left empty. Nothing here is sent back to the API.
 */
export function gapsForApiCall(
  session: CallSession,
  attributions: CampaignAttribution[],
  nowMs: number,
): CallGaps {
  const link = attributions[0] ?? null
  return {
    conversation_state: null,
    conversation_state_record_layer: null,
    classification: { label: 'unknown', record_layer: 'interpretation', confidence: null },
    engagement_duration_ms: engagementMs(session.answered_at, session.ended_at, nowMs),
    duration_ms: elapsedMs(session.started_at, session.ended_at, nowMs),
    campaign_id: link ? link.campaign_id : null,
    campaign_label: null,
    pipeline: null,
    timeline: [],
    state_transitions: [],
    paired_reads: [],
    correlation_notes: [],
    key_finding_ids: [],
  }
}

/** List rows are `CallSessionSummary`. Carrier id and answer time stay on the detail session. */
export function sessionFromSummary(summary: CallSessionSummary): CallSession {
  return {
    record_layer: 'observation',
    id: summary.id,
    operator_number_id: null,
    external_call_id: '',
    carrier: '',
    caller_number_e164: summary.caller_number_e164,
    called_number_e164: summary.called_number_e164,
    state: summary.state,
    started_at: summary.started_at,
    answered_at: null,
    ended_at: summary.ended_at,
    end_reason: null,
  }
}

export function summaryFromListItem(item: CallSessionSummary, nowMs: number): CallSummary {
  const session = sessionFromSummary(item)
  const gaps = gapsForApiCall(session, [], nowMs)
  return {
    session,
    gaps: {
      conversation_state: gaps.conversation_state,
      conversation_state_record_layer: gaps.conversation_state_record_layer,
      classification: gaps.classification,
      engagement_duration_ms: gaps.engagement_duration_ms,
      duration_ms: gaps.duration_ms,
      campaign_id: gaps.campaign_id,
      campaign_label: gaps.campaign_label,
    },
    key_findings: [],
  }
}

export function detailFromResponse(body: CallDetailResponse, nowMs: number): CallDetail {
  const transcript = [...body.transcript].sort((left, right) => left.sequence - right.sequence)
  const turns = [...body.turns].sort((left, right) => left.turn_index - right.turn_index)
  return {
    session: body.session,
    media_streams: body.media_streams,
    transcript,
    turns,
    findings: body.findings,
    attributions: body.attributions,
    events: [],
    gaps: gapsForApiCall(body.session, body.attributions, nowMs),
  }
}

export function liveFromDetail(detail: CallDetail): LiveCall {
  return {
    session: detail.session,
    transcript: detail.transcript,
    findings: detail.findings,
    gaps: {
      conversation_state: detail.gaps.conversation_state,
      conversation_state_record_layer: detail.gaps.conversation_state_record_layer,
      classification: detail.gaps.classification,
      campaign_id: detail.gaps.campaign_id,
      campaign_label: detail.gaps.campaign_label,
      pipeline: detail.gaps.pipeline,
    },
  }
}
