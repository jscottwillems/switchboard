import type { LiveFixture, CampaignFixture } from '@/mocks/fixtureTypes'
import type {
  ActivityBucket,
  CallDetail,
  CallSession,
  Campaign,
  CampaignAttribution,
  CampaignSignal,
  CampaignSimilarity,
  CampaignTimelineEntry,
  ClassifiedValue,
  ConversationTurn,
  CorrelationNote,
  DashboardEvent,
  IntelligenceFinding,
  MediaStream,
  PairedRead,
  PipelineLatency,
  ServiceHealth,
  StateTransition,
  SystemHealth,
  TimelineEntry,
  TranscriptSegment,
} from '@/types/models'
import {
  CLASSIFICATIONS,
  CONVERSATION_STATES,
  OBSERVATION_CATEGORIES,
  PROVIDER_ROLES,
  PROVIDER_STATUSES,
  SERVICES,
} from '@/types/models'

const RECORD_LAYERS = ['observation', 'interpretation', 'attribution'] as const
const CALL_STATES = ['ringing', 'in_progress', 'completed', 'failed'] as const
const CAMPAIGN_STATUSES = ['hypothesized', 'corroborated', 'closed'] as const
const FINDING_KINDS = [
  'callback_number',
  'pretext',
  'organization_name',
  'payment_method',
  'url',
  'person_name',
  'other',
] as const
const FINDING_STATUSES = ['proposed', 'accepted', 'rejected'] as const
const SPEAKERS = ['caller', 'honeypot'] as const
const SOURCES = ['stt', 'tts_input'] as const
const EVENT_TYPES = [
  'telephony.call.received',
  'telephony.call.answered',
  'telephony.call.completed',
  'telephony.call.failed',
  'media.stream.started',
  'media.stream.stopped',
  'media.stream.failed',
  'speech.segment.partial',
  'speech.segment.final',
  'speech.synthesis.requested',
  'speech.synthesis.completed',
  'speech.synthesis.failed',
  'conversation.response.selected',
  'conversation.turn.recorded',
  'intelligence.finding.proposed',
  'campaign.opened',
  'campaign.attribution.proposed',
] as const
const PRODUCERS = ['api', 'media_gateway', 'intelligence'] as const
const MEDIA_STATES = ['connecting', 'streaming', 'closed', 'failed'] as const

function fail(ctx: string, message: string): never {
  throw new Error(`${ctx}: ${message}`)
}

function record(value: unknown, ctx: string): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) fail(ctx, 'expected an object')
  return value as Record<string, unknown>
}

function array(value: unknown, ctx: string): unknown[] {
  if (!Array.isArray(value)) fail(ctx, 'expected an array')
  return value
}

function text(source: Record<string, unknown>, key: string, ctx: string): string {
  const value = source[key]
  if (typeof value !== 'string' || value.length === 0) fail(ctx, `${key} must be a non-empty string`)
  return value
}

function nullableText(source: Record<string, unknown>, key: string, ctx: string): string | null {
  const value = source[key]
  if (value === null) return null
  if (typeof value !== 'string' || value.length === 0) fail(ctx, `${key} must be a string or null`)
  return value
}

function numberValue(source: Record<string, unknown>, key: string, ctx: string): number {
  const value = source[key]
  if (typeof value !== 'number' || Number.isNaN(value)) fail(ctx, `${key} must be a number`)
  return value
}

function score(source: Record<string, unknown>, key: string, ctx: string): number {
  const value = numberValue(source, key, ctx)
  if (value < 0 || value > 1) fail(ctx, `${key} must be 0..1`)
  return value
}

function nullableScore(source: Record<string, unknown>, key: string, ctx: string): number | null {
  const value = source[key]
  if (value === null) return null
  return score(source, key, ctx)
}

function booleanValue(source: Record<string, unknown>, key: string, ctx: string): boolean {
  const value = source[key]
  if (typeof value !== 'boolean') fail(ctx, `${key} must be a boolean`)
  return value
}

function oneOf<T extends string>(source: Record<string, unknown>, key: string, allowed: readonly T[], ctx: string): T {
  const value = text(source, key, ctx)
  if (!(allowed as readonly string[]).includes(value)) fail(ctx, `${key} has unexpected value ${value}`)
  return value as T
}

function stringList(value: unknown, ctx: string): string[] {
  return array(value, ctx).map((item, index) => {
    if (typeof item !== 'string' || item.length === 0) fail(ctx, `[${index}] must be a string`)
    return item
  })
}

function payload(value: unknown, ctx: string): Record<string, unknown> {
  const source = record(value, ctx)
  return source
}

function session(value: unknown, ctx: string): CallSession {
  const source = record(value, ctx)
  const layer = oneOf(source, 'record_layer', RECORD_LAYERS, ctx)
  if (layer !== 'observation') fail(ctx, 'session record_layer must be observation')
  return {
    record_layer: 'observation',
    id: text(source, 'id', ctx),
    operator_number_id: nullableText(source, 'operator_number_id', ctx),
    external_call_id: text(source, 'external_call_id', ctx),
    carrier: text(source, 'carrier', ctx),
    caller_number_e164: text(source, 'caller_number_e164', ctx),
    called_number_e164: text(source, 'called_number_e164', ctx),
    state: oneOf(source, 'state', CALL_STATES, ctx),
    started_at: text(source, 'started_at', ctx),
    answered_at: nullableText(source, 'answered_at', ctx),
    ended_at: nullableText(source, 'ended_at', ctx),
    end_reason: nullableText(source, 'end_reason', ctx),
  }
}

function mediaStream(value: unknown, ctx: string): MediaStream {
  const source = record(value, ctx)
  if (oneOf(source, 'record_layer', RECORD_LAYERS, ctx) !== 'observation') fail(ctx, 'media record_layer')
  if (text(source, 'protocol', ctx) !== 'switchboard.media.v1') fail(ctx, 'protocol')
  const encoding = text(source, 'encoding', ctx)
  if (encoding !== 'audio/pcmu' && encoding !== 'audio/pcm') fail(ctx, 'encoding')
  return {
    record_layer: 'observation',
    id: text(source, 'id', ctx),
    call_session_id: text(source, 'call_session_id', ctx),
    external_stream_id: text(source, 'external_stream_id', ctx),
    protocol: 'switchboard.media.v1',
    encoding,
    sample_rate_hz: numberValue(source, 'sample_rate_hz', ctx),
    state: oneOf(source, 'state', MEDIA_STATES, ctx),
    started_at: text(source, 'started_at', ctx),
    ended_at: nullableText(source, 'ended_at', ctx),
  }
}

function segment(value: unknown, ctx: string): TranscriptSegment {
  const source = record(value, ctx)
  if (oneOf(source, 'record_layer', RECORD_LAYERS, ctx) !== 'observation') fail(ctx, 'transcript record_layer')
  return {
    record_layer: 'observation',
    id: text(source, 'id', ctx),
    call_session_id: text(source, 'call_session_id', ctx),
    media_stream_id: text(source, 'media_stream_id', ctx),
    sequence: numberValue(source, 'sequence', ctx),
    speaker: oneOf(source, 'speaker', SPEAKERS, ctx),
    source: oneOf(source, 'source', SOURCES, ctx),
    text: text(source, 'text', ctx),
    language: nullableText(source, 'language', ctx),
    start_offset_ms: numberValue(source, 'start_offset_ms', ctx),
    end_offset_ms: numberValue(source, 'end_offset_ms', ctx),
    is_final: booleanValue(source, 'is_final', ctx),
    stt_confidence: nullableScore(source, 'stt_confidence', ctx),
    provider: text(source, 'provider', ctx),
    created_at: text(source, 'created_at', ctx),
  }
}

function turn(value: unknown, ctx: string): ConversationTurn {
  const source = record(value, ctx)
  if (oneOf(source, 'record_layer', RECORD_LAYERS, ctx) !== 'interpretation') fail(ctx, 'turn record_layer')
  return {
    record_layer: 'interpretation',
    id: text(source, 'id', ctx),
    call_session_id: text(source, 'call_session_id', ctx),
    turn_index: numberValue(source, 'turn_index', ctx),
    speaker: oneOf(source, 'speaker', SPEAKERS, ctx),
    text: text(source, 'text', ctx),
    transcript_segment_ids: stringList(source.transcript_segment_ids, `${ctx}.transcript_segment_ids`),
    strategy_id: nullableText(source, 'strategy_id', ctx),
    confidence: score(source, 'confidence', ctx),
    created_at: text(source, 'created_at', ctx),
  }
}

function finding(value: unknown, ctx: string): IntelligenceFinding {
  const source = record(value, ctx)
  if (oneOf(source, 'record_layer', RECORD_LAYERS, ctx) !== 'interpretation') fail(ctx, 'finding record_layer')
  const transcript_segment_ids = stringList(source.transcript_segment_ids, `${ctx}.transcript_segment_ids`)
  if (transcript_segment_ids.length === 0) fail(ctx, 'finding needs a transcript citation')
  return {
    record_layer: 'interpretation',
    id: text(source, 'id', ctx),
    call_session_id: text(source, 'call_session_id', ctx),
    kind: oneOf(source, 'kind', FINDING_KINDS, ctx),
    value: text(source, 'value', ctx),
    raw_quote: text(source, 'raw_quote', ctx),
    transcript_segment_ids,
    extractor: text(source, 'extractor', ctx),
    extractor_version: text(source, 'extractor_version', ctx),
    confidence: score(source, 'confidence', ctx),
    status: oneOf(source, 'status', FINDING_STATUSES, ctx),
    created_at: text(source, 'created_at', ctx),
  }
}

function attribution(value: unknown, ctx: string): CampaignAttribution {
  const source = record(value, ctx)
  if (oneOf(source, 'record_layer', RECORD_LAYERS, ctx) !== 'attribution') fail(ctx, 'attribution record_layer')
  const supporting = stringList(source.supporting_finding_ids, `${ctx}.supporting_finding_ids`)
  if (supporting.length === 0) fail(ctx, 'attribution needs a finding')
  return {
    record_layer: 'attribution',
    id: text(source, 'id', ctx),
    campaign_id: text(source, 'campaign_id', ctx),
    call_session_id: text(source, 'call_session_id', ctx),
    supporting_finding_ids: supporting,
    method: text(source, 'method', ctx),
    method_version: text(source, 'method_version', ctx),
    confidence: score(source, 'confidence', ctx),
    rationale: text(source, 'rationale', ctx),
    created_at: text(source, 'created_at', ctx),
  }
}

function classified(value: unknown, ctx: string): ClassifiedValue {
  const source = record(value, ctx)
  return {
    label: oneOf(source, 'label', CLASSIFICATIONS, ctx),
    record_layer: oneOf(source, 'record_layer', RECORD_LAYERS, ctx),
    confidence: nullableScore(source, 'confidence', ctx),
  }
}

function pipeline(value: unknown, ctx: string): PipelineLatency {
  const source = record(value, ctx)
  return {
    sampled_at: text(source, 'sampled_at', ctx),
    stt_ms: numberValue(source, 'stt_ms', ctx),
    select_ms: numberValue(source, 'select_ms', ctx),
    tts_ms: numberValue(source, 'tts_ms', ctx),
    e2e_ms: numberValue(source, 'e2e_ms', ctx),
  }
}

function timelineEntry(value: unknown, ctx: string): TimelineEntry {
  const source = record(value, ctx)
  const eventType = source.event_type
  if (eventType !== null && (typeof eventType !== 'string' || !(EVENT_TYPES as readonly string[]).includes(eventType))) {
    fail(ctx, 'event_type')
  }
  return {
    id: text(source, 'id', ctx),
    at: text(source, 'at', ctx),
    offset_ms: numberValue(source, 'offset_ms', ctx),
    event_type: eventType as TimelineEntry['event_type'],
    title: text(source, 'title', ctx),
    detail: text(source, 'detail', ctx),
  }
}

function transition(value: unknown, ctx: string): StateTransition {
  const source = record(value, ctx)
  const from = source.from
  if (from !== null && (typeof from !== 'string' || !(CONVERSATION_STATES as readonly string[]).includes(from))) {
    fail(ctx, 'from')
  }
  return {
    id: text(source, 'id', ctx),
    at: text(source, 'at', ctx),
    offset_ms: numberValue(source, 'offset_ms', ctx),
    from: from as StateTransition['from'],
    to: oneOf(source, 'to', CONVERSATION_STATES, ctx),
    reason: text(source, 'reason', ctx),
    record_layer: oneOf(source, 'record_layer', RECORD_LAYERS, ctx),
  }
}

function paired(value: unknown, ctx: string): PairedRead {
  const source = record(value, ctx)
  const raw = record(source.raw, `${ctx}.raw`)
  if (text(raw, 'record_layer', `${ctx}.raw`) !== 'observation') fail(ctx, 'raw layer')
  const interpretation = source.interpretation
  let parsed: PairedRead['interpretation'] = null
  if (interpretation !== null) {
    const side = record(interpretation, `${ctx}.interpretation`)
    if (text(side, 'record_layer', `${ctx}.interpretation`) !== 'interpretation') fail(ctx, 'interpretation layer')
    parsed = { text: text(side, 'text', `${ctx}.interpretation`), record_layer: 'interpretation' }
  }
  return {
    id: text(source, 'id', ctx),
    at: text(source, 'at', ctx),
    offset_ms: numberValue(source, 'offset_ms', ctx),
    category: oneOf(source, 'category', OBSERVATION_CATEGORIES, ctx),
    raw: { text: text(raw, 'text', `${ctx}.raw`), record_layer: 'observation' },
    interpretation: parsed,
  }
}

function note(value: unknown, ctx: string): CorrelationNote {
  const source = record(value, ctx)
  return {
    id: text(source, 'id', ctx),
    campaign_id: nullableText(source, 'campaign_id', ctx),
    campaign_label: nullableText(source, 'campaign_label', ctx),
    score: score(source, 'score', ctx),
    summary: text(source, 'summary', ctx),
    explanation: text(source, 'explanation', ctx),
    record_layer: oneOf(source, 'record_layer', RECORD_LAYERS, ctx),
    matched_on: array(source.matched_on, `${ctx}.matched_on`).map((item, index) => {
      const match = record(item, `${ctx}.matched_on[${index}]`)
      return {
        label: text(match, 'label', `${ctx}.matched_on[${index}]`),
        record_layer: oneOf(match, 'record_layer', RECORD_LAYERS, `${ctx}.matched_on[${index}]`),
      }
    }),
  }
}

function dashboardEvent(value: unknown, ctx: string): DashboardEvent {
  const source = record(value, ctx)
  if (source.event_version !== 1) fail(ctx, 'event_version')
  return {
    event_id: text(source, 'event_id', ctx),
    event_type: oneOf(source, 'event_type', EVENT_TYPES, ctx),
    event_version: 1,
    occurred_at: text(source, 'occurred_at', ctx),
    producer: oneOf(source, 'producer', PRODUCERS, ctx),
    call_session_id: text(source, 'call_session_id', ctx),
    causation_id: nullableText(source, 'causation_id', ctx),
    payload: payload(source.payload, `${ctx}.payload`),
    offset_ms: numberValue(source, 'offset_ms', ctx),
  }
}

function callDetail(value: unknown, ctx: string): CallDetail {
  const source = record(value, ctx)
  const gaps = record(source.gaps, `${ctx}.gaps`)
  return {
    session: session(source.session, `${ctx}.session`),
    media_streams: array(source.media_streams, `${ctx}.media_streams`).map((item, index) =>
      mediaStream(item, `${ctx}.media_streams[${index}]`),
    ),
    transcript: array(source.transcript, `${ctx}.transcript`).map((item, index) => segment(item, `${ctx}.transcript[${index}]`)),
    turns: array(source.turns, `${ctx}.turns`).map((item, index) => turn(item, `${ctx}.turns[${index}]`)),
    findings: array(source.findings, `${ctx}.findings`).map((item, index) => finding(item, `${ctx}.findings[${index}]`)),
    attributions: array(source.attributions, `${ctx}.attributions`).map((item, index) =>
      attribution(item, `${ctx}.attributions[${index}]`),
    ),
    events: array(source.events, `${ctx}.events`).map((item, index) => dashboardEvent(item, `${ctx}.events[${index}]`)),
    gaps: {
      conversation_state: oneOf(gaps, 'conversation_state', CONVERSATION_STATES, `${ctx}.gaps`),
      conversation_state_record_layer: oneOf(gaps, 'conversation_state_record_layer', RECORD_LAYERS, `${ctx}.gaps`),
      classification: classified(gaps.classification, `${ctx}.gaps.classification`),
      engagement_duration_ms: numberValue(gaps, 'engagement_duration_ms', `${ctx}.gaps`),
      duration_ms: numberValue(gaps, 'duration_ms', `${ctx}.gaps`),
      campaign_id: nullableText(gaps, 'campaign_id', `${ctx}.gaps`),
      campaign_label: nullableText(gaps, 'campaign_label', `${ctx}.gaps`),
      pipeline: pipeline(gaps.pipeline, `${ctx}.gaps.pipeline`),
      timeline: array(gaps.timeline, `${ctx}.gaps.timeline`).map((item, index) =>
        timelineEntry(item, `${ctx}.gaps.timeline[${index}]`),
      ),
      state_transitions: array(gaps.state_transitions, `${ctx}.gaps.state_transitions`).map((item, index) =>
        transition(item, `${ctx}.gaps.state_transitions[${index}]`),
      ),
      paired_reads: array(gaps.paired_reads, `${ctx}.gaps.paired_reads`).map((item, index) =>
        paired(item, `${ctx}.gaps.paired_reads[${index}]`),
      ),
      correlation_notes: array(gaps.correlation_notes, `${ctx}.gaps.correlation_notes`).map((item, index) =>
        note(item, `${ctx}.gaps.correlation_notes[${index}]`),
      ),
      key_finding_ids: stringList(gaps.key_finding_ids, `${ctx}.gaps.key_finding_ids`),
    },
  }
}

function campaign(value: unknown, ctx: string): Campaign {
  const source = record(value, ctx)
  if (oneOf(source, 'record_layer', RECORD_LAYERS, ctx) !== 'attribution') fail(ctx, 'campaign record_layer')
  return {
    record_layer: 'attribution',
    id: text(source, 'id', ctx),
    label: text(source, 'label', ctx),
    status: oneOf(source, 'status', CAMPAIGN_STATUSES, ctx),
    summary: nullableText(source, 'summary', ctx),
    created_at: text(source, 'created_at', ctx),
    updated_at: text(source, 'updated_at', ctx),
  }
}

function signal(value: unknown, ctx: string): CampaignSignal {
  const source = record(value, ctx)
  return {
    id: text(source, 'id', ctx),
    kind: oneOf(source, 'kind', FINDING_KINDS, ctx),
    value: text(source, 'value', ctx),
    raw_quote: text(source, 'raw_quote', ctx),
    record_layer: oneOf(source, 'record_layer', RECORD_LAYERS, ctx),
    confidence: nullableScore(source, 'confidence', ctx),
    status: oneOf(source, 'status', FINDING_STATUSES, ctx),
  }
}

function similarity(value: unknown, ctx: string): CampaignSimilarity {
  const source = record(value, ctx)
  return {
    call_id: text(source, 'call_id', ctx),
    external_call_id: text(source, 'external_call_id', ctx),
    score: score(source, 'score', ctx),
    explanation: text(source, 'explanation', ctx),
    record_layer: oneOf(source, 'record_layer', RECORD_LAYERS, ctx),
  }
}

function campaignTimeline(value: unknown, ctx: string): CampaignTimelineEntry {
  const source = record(value, ctx)
  return {
    id: text(source, 'id', ctx),
    at: text(source, 'at', ctx),
    title: text(source, 'title', ctx),
    detail: text(source, 'detail', ctx),
    event_type: oneOf(source, 'event_type', ['campaign.opened', 'campaign.attribution.proposed'] as const, ctx),
  }
}

function activity(value: unknown, ctx: string): ActivityBucket {
  const source = record(value, ctx)
  return {
    day: text(source, 'day', ctx),
    hour: numberValue(source, 'hour', ctx),
    count: numberValue(source, 'count', ctx),
  }
}

export function parseCallDetails(value: unknown): CallDetail[] {
  return array(value, 'call-details').map((item, index) => callDetail(item, `call-details[${index}]`))
}

export function parseLiveFixtures(value: unknown): LiveFixture[] {
  return array(value, 'live-calls').map((item, index) => {
    const source = record(item, `live-calls[${index}]`)
    return {
      started_offset_sec: numberValue(source, 'started_offset_sec', `live-calls[${index}]`),
      engagement_delay_ms: numberValue(source, 'engagement_delay_ms', `live-calls[${index}]`),
      call: callDetail(source.call, `live-calls[${index}].call`),
    }
  })
}

export function parseCampaigns(value: unknown): CampaignFixture[] {
  return array(value, 'campaigns').map((item, index) => {
    const source = record(item, `campaigns[${index}]`)
    const gaps = record(source.gaps, `campaigns[${index}].gaps`)
    const ctx = `campaigns[${index}].gaps`
    return {
      campaign: campaign(source.campaign, `campaigns[${index}].campaign`),
      gaps: {
        classification: classified(gaps.classification, `${ctx}.classification`),
        call_count: numberValue(gaps, 'call_count', ctx),
        activity: array(gaps.activity, `${ctx}.activity`).map((bucket, bucketIndex) =>
          activity(bucket, `${ctx}.activity[${bucketIndex}]`),
        ),
        timeline: array(gaps.timeline, `${ctx}.timeline`).map((entry, entryIndex) =>
          campaignTimeline(entry, `${ctx}.timeline[${entryIndex}]`),
        ),
        related_call_ids: stringList(gaps.related_call_ids, `${ctx}.related_call_ids`),
        script_phrases: array(gaps.script_phrases, `${ctx}.script_phrases`).map((entry, entryIndex) =>
          signal(entry, `${ctx}.script_phrases[${entryIndex}]`),
        ),
        shared_indicators: array(gaps.shared_indicators, `${ctx}.shared_indicators`).map((entry, entryIndex) =>
          signal(entry, `${ctx}.shared_indicators[${entryIndex}]`),
        ),
        similarity: array(gaps.similarity, `${ctx}.similarity`).map((entry, entryIndex) =>
          similarity(entry, `${ctx}.similarity[${entryIndex}]`),
        ),
      },
    }
  })
}

export function parseSystemHealth(value: unknown): SystemHealth {
  const source = record(value, 'system')
  const latency = record(source.latency, 'system.latency')
  const concurrency = record(source.concurrency, 'system.concurrency')
  const cost = record(source.cost, 'system.cost')
  if (text(cost, 'currency', 'system.cost') !== 'USD') fail('system.cost', 'currency')
  const services = array(source.services, 'system.services').map((item, index): ServiceHealth => {
    const row = record(item, `system.services[${index}]`)
    if (text(row, 'status', `system.services[${index}]`) !== 'ok') fail(`system.services[${index}]`, 'status')
    return {
      service: oneOf(row, 'service', SERVICES, `system.services[${index}]`),
      status: 'ok',
      version: text(row, 'version', `system.services[${index}]`),
    }
  })
  return {
    sampled_at: text(source, 'sampled_at', 'system'),
    services,
    providers: array(source.providers, 'system.providers').map((item, index) => {
      const row = record(item, `system.providers[${index}]`)
      return {
        id: text(row, 'id', `system.providers[${index}]`),
        name: text(row, 'name', `system.providers[${index}]`),
        role: oneOf(row, 'role', PROVIDER_ROLES, `system.providers[${index}]`),
        status: oneOf(row, 'status', PROVIDER_STATUSES, `system.providers[${index}]`),
        latency_ms: numberValue(row, 'latency_ms', `system.providers[${index}]`),
        detail: text(row, 'detail', `system.providers[${index}]`),
      }
    }),
    latency: {
      stt_ms: numberValue(latency, 'stt_ms', 'system.latency'),
      select_ms: numberValue(latency, 'select_ms', 'system.latency'),
      tts_ms: numberValue(latency, 'tts_ms', 'system.latency'),
      e2e_ms: numberValue(latency, 'e2e_ms', 'system.latency'),
    },
    concurrency: {
      active_calls: numberValue(concurrency, 'active_calls', 'system.concurrency'),
      capacity: numberValue(concurrency, 'capacity', 'system.concurrency'),
      queue_depth: numberValue(concurrency, 'queue_depth', 'system.concurrency'),
    },
    cost: {
      window_label: text(cost, 'window_label', 'system.cost'),
      currency: 'USD',
      stt: numberValue(cost, 'stt', 'system.cost'),
      tts: numberValue(cost, 'tts', 'system.cost'),
      selector: numberValue(cost, 'selector', 'system.cost'),
      telephony: numberValue(cost, 'telephony', 'system.cost'),
    },
    errors: array(source.errors, 'system.errors').map((item, index) => {
      const row = record(item, `system.errors[${index}]`)
      const severity = text(row, 'severity', `system.errors[${index}]`)
      if (severity !== 'warn' && severity !== 'error') fail(`system.errors[${index}]`, 'severity')
      return {
        id: text(row, 'id', `system.errors[${index}]`),
        at: text(row, 'at', `system.errors[${index}]`),
        source: text(row, 'source', `system.errors[${index}]`),
        severity,
        message: text(row, 'message', `system.errors[${index}]`),
      }
    }),
  }
}
