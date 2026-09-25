/**
 * Turns authoring fixtures into Atlas contract shapes.
 * Seeds may still say observed/inferred/unverified, active/abandoned, and camelCase.
 * Files written to src/mocks use record_layer, CallState, CampaignStatus, FindingKind,
 * and EventType names from packages/schemas.
 */
import { createHash } from 'node:crypto'

const CALLED = '+15550001001'
const OPERATOR_NUMBER_ID = '00000000-0000-4000-8000-000000000001'

const FINDING_KINDS = new Set([
  'callback_number',
  'pretext',
  'organization_name',
  'payment_method',
  'url',
  'person_name',
  'other',
])

const EVENT_TYPES = new Set([
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
])

export function uuidFor(key) {
  const hex = createHash('sha256').update(`switchboard.mock.v1:${key}`).digest('hex')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-4${hex.slice(13, 16)}-a${hex.slice(17, 20)}-${hex.slice(20, 32)}`
}

function toE164(value) {
  const digits = String(value).replace(/\D/g, '')
  if (digits.length === 10) return `+1${digits}`
  if (digits.length === 11 && digits.startsWith('1')) return `+${digits}`
  throw new Error(`Not an E.164-capable number: ${value}`)
}

function recordLayer(provenance, basis) {
  if (provenance === 'observation' || provenance === 'interpretation' || provenance === 'attribution') {
    return provenance
  }
  if (provenance === 'inferred' || basis === 'derived') return 'interpretation'
  return 'observation'
}

function callState(status) {
  switch (status) {
    case 'active':
    case 'in_progress':
      return 'in_progress'
    case 'completed':
      return 'completed'
    case 'ringing':
      return 'ringing'
    case 'abandoned':
    case 'error':
    case 'failed':
      return 'failed'
    default:
      throw new Error(`Unknown call status ${status}`)
  }
}

function campaignStatus(status) {
  switch (status) {
    case 'active':
    case 'corroborated':
      return 'corroborated'
    case 'watching':
    case 'hypothesized':
      return 'hypothesized'
    case 'closed':
      return 'closed'
    default:
      throw new Error(`Unknown campaign status ${status}`)
  }
}

function findingKind(kind, label) {
  if (FINDING_KINDS.has(kind)) return kind
  switch (kind) {
    case 'callback':
      return 'callback_number'
    case 'amount':
      return 'payment_method'
    case 'script_phrase':
    case 'tactic':
      return 'pretext'
    case 'entity':
      return /name/i.test(label) ? 'person_name' : 'organization_name'
    case 'indicator':
      return 'other'
    default:
      throw new Error(`Unknown intelligence kind ${kind}`)
  }
}

function findingConfidence(item) {
  if (typeof item.confidence === 'number') return item.confidence
  if (item.provenance === 'unverified') return 0.35
  if (item.provenance === 'observed' || item.provenance === 'observation') return 0.8
  return 0.7
}

function producerFor(eventType) {
  if (eventType.startsWith('telephony.')) return 'api'
  if (eventType.startsWith('intelligence.') || eventType.startsWith('campaign.')) return 'intelligence'
  return 'media_gateway'
}

function assertEvent(eventType) {
  if (!EVENT_TYPES.has(eventType)) throw new Error(`Bad event type ${eventType}`)
  return eventType
}

function technicalEventType(event, state) {
  const message = `${event.message ?? ''}`
  if (event.severity === 'error' && event.source === 'tts') return 'speech.synthesis.failed'
  if (event.severity === 'error') return 'telephony.call.failed'
  switch (event.source) {
    case 'telephony':
      if (/end|released|disconnect|completed|drop/i.test(message)) {
        return state === 'failed' ? 'telephony.call.failed' : 'telephony.call.completed'
      }
      return 'telephony.call.answered'
    case 'stt':
      return 'speech.segment.final'
    case 'tts':
      return 'speech.synthesis.completed'
    case 'llm':
      return 'conversation.response.selected'
    case 'orchestrator':
      return 'conversation.turn.recorded'
    default:
      throw new Error(`Unknown technical source ${event.source}`)
  }
}

function timelineEventType(entry, state) {
  if (entry.kind === 'error') return 'telephony.call.failed'
  if (entry.kind === 'intel') return 'intelligence.finding.proposed'
  if (entry.kind === 'transcript') return 'speech.segment.final'
  if (entry.kind === 'state') return null
  if (entry.kind === 'telephony') {
    if (/release|disconnect|end|drop|underrun|closed/i.test(`${entry.title} ${entry.detail}`)) {
      return state === 'failed' ? 'telephony.call.failed' : 'telephony.call.completed'
    }
    return 'telephony.call.answered'
  }
  return null
}

function eventPayload(eventType, legacyId, event) {
  const attributes = {}
  for (const attribute of event.attributes ?? []) attributes[attribute.key] = attribute.value
  switch (eventType) {
    case 'telephony.call.answered':
      return { external_call_id: legacyId }
    case 'telephony.call.completed':
      return { external_call_id: legacyId, end_reason: event.message ?? null }
    case 'telephony.call.failed':
    case 'speech.synthesis.failed':
    case 'media.stream.failed':
      return eventType === 'speech.synthesis.failed'
        ? { turn_id: uuidFor(`turn-end:${legacyId}`), end_reason: event.message }
        : eventType === 'media.stream.failed'
          ? { media_stream_id: uuidFor(`stream:${legacyId}`), end_reason: event.message }
          : { external_call_id: legacyId, end_reason: event.message }
    case 'speech.synthesis.completed':
      return { turn_id: uuidFor(`turn-end:${legacyId}`), duration_ms: event.offsetMs ?? 0 }
    case 'conversation.response.selected':
      return {
        turn_id: uuidFor(`turn-end:${legacyId}`),
        strategy_id: 'fixed.v1',
        text: event.message,
        confidence: 1,
      }
    case 'conversation.turn.recorded':
      return {
        turn_id: uuidFor(`turn-end:${legacyId}`),
        turn_index: 0,
        speaker: 'honeypot',
        text: event.message,
        transcript_segment_ids: [],
        strategy_id: 'fixed.v1',
        confidence: 1,
      }
    case 'speech.segment.final':
      return {
        transcript_segment_id: uuidFor(`segment-event:${event.id}`),
        speaker: 'caller',
        text: event.message,
        is_final: true,
        stt_confidence: 0.9,
        start_offset_ms: event.offsetMs ?? 0,
        end_offset_ms: event.offsetMs ?? 0,
        sequence: 0,
      }
    default:
      return { note: event.message ?? '', ...attributes }
  }
}

function buildIdMap(history, live, campaigns) {
  const idMap = new Map()
  for (const call of history) idMap.set(call.id, uuidFor(`call:${call.id}`))
  for (const pair of live) idMap.set(pair.board.id, uuidFor(`call:${pair.board.id}`))
  for (const campaign of campaigns) idMap.set(campaign.id, uuidFor(`campaign:${campaign.id}`))
  return idMap
}

function mapId(idMap, legacy) {
  if (legacy == null) return null
  const mapped = idMap.get(legacy)
  if (!mapped) throw new Error(`Unmapped id ${legacy}`)
  return mapped
}

function alignTranscript(turns, callSessionId, mediaStreamId, startedMs) {
  const segments = []
  const byLegacy = new Map()
  turns.forEach((turn, sequence) => {
    const start = turn.offsetMs ?? turn.start_offset_ms
    const end = start + Math.max(400, Math.min(8000, String(turn.text).length * 45))
    const caller = turn.speaker === 'caller'
    const segment = {
      record_layer: 'observation',
      id: uuidFor(`segment:${turn.id}`),
      call_session_id: callSessionId,
      media_stream_id: mediaStreamId,
      sequence,
      speaker: turn.speaker,
      source: caller ? 'stt' : 'tts_input',
      text: turn.text,
      language: 'en',
      start_offset_ms: start,
      end_offset_ms: end,
      is_final: true,
      stt_confidence: caller ? 0.9 : null,
      provider: caller ? 'mock-stt' : 'mock-tts',
      created_at: new Date(startedMs + start).toISOString(),
    }
    segments.push(segment)
    byLegacy.set(turn.id, segment.id)
  })
  const conversationTurns = segments.map((segment) => ({
    record_layer: 'interpretation',
    id: uuidFor(`turn:${segment.id}`),
    call_session_id: callSessionId,
    turn_index: segment.sequence,
    speaker: segment.speaker,
    text: segment.text,
    transcript_segment_ids: [segment.id],
    strategy_id: segment.speaker === 'honeypot' ? 'fixed.v1' : null,
    confidence: segment.speaker === 'honeypot' ? 1 : 1,
    created_at: segment.created_at,
  }))
  return { segments, conversationTurns, byLegacy }
}

function alignFindings(items, callSessionId, byLegacy, createdAt) {
  return items.map((item) => {
    const transcript_segment_ids = (item.evidenceTurnIds ?? []).map((turnId) => {
      const segmentId = byLegacy.get(turnId)
      if (!segmentId) throw new Error(`Finding ${item.id} cites missing turn ${turnId}`)
      return segmentId
    })
    if (transcript_segment_ids.length === 0) {
      const fallback = byLegacy.values().next().value
      if (!fallback) throw new Error(`Finding ${item.id} has no transcript to cite`)
      transcript_segment_ids.push(fallback)
    }
    return {
      record_layer: 'interpretation',
      id: uuidFor(`finding:${item.id}`),
      call_session_id: callSessionId,
      kind: findingKind(item.kind, item.label),
      value: item.value,
      raw_quote: item.label,
      transcript_segment_ids,
      extractor: 'fixture.rule',
      extractor_version: '0.1.0',
      confidence: findingConfidence(item),
      status: 'proposed',
      created_at: createdAt,
    }
  })
}

function alignSignal(item) {
  return {
    id: uuidFor(`signal:${item.id}`),
    kind: findingKind(item.kind, item.label),
    value: item.value,
    raw_quote: item.label,
    record_layer: item.basis === 'raw' || item.provenance === 'observed' || item.provenance === 'unverified'
      ? recordLayer(item.provenance, item.basis)
      : 'interpretation',
    confidence: item.confidence ?? null,
    status: 'proposed',
  }
}

function alignNotes(notes, idMap) {
  return notes.map((item) => ({
    id: uuidFor(`note:${item.id}`),
    campaign_id: mapId(idMap, item.campaignId),
    campaign_label: item.campaignName,
    score: item.score,
    summary: item.summary,
    explanation: item.explanation,
    record_layer: recordLayer(item.provenance, 'derived'),
    matched_on: (item.matchedOn ?? []).map((match) => ({
      label: match.label,
      record_layer: recordLayer(match.provenance),
    })),
  }))
}

function alignPaired(observations) {
  return observations.map((item) => ({
    id: uuidFor(`pair:${item.id}`),
    at: item.at ?? null,
    offset_ms: item.offsetMs,
    category: item.category,
    raw: { text: item.raw.text, record_layer: 'observation' },
    interpretation: item.interpretation
      ? { text: item.interpretation.text, record_layer: 'interpretation' }
      : null,
  }))
}

function alignTransitions(transitions) {
  return transitions.map((item) => ({
    id: uuidFor(`state:${item.id}`),
    at: item.at ?? null,
    offset_ms: item.offsetMs,
    from: item.from,
    to: item.to,
    reason: item.reason,
    record_layer: recordLayer(item.provenance),
  }))
}

function alignTimeline(entries, state) {
  return entries.map((entry) => {
    const eventType = timelineEventType(entry, state)
    return {
      id: uuidFor(`timeline:${entry.id}`),
      at: entry.at ?? null,
      offset_ms: entry.offsetMs,
      event_type: eventType,
      title: entry.title,
      detail: entry.detail,
    }
  })
}

function alignEvents(events, callSessionId, legacyId, state) {
  return events.map((event) => {
    const eventType = assertEvent(technicalEventType(event, state))
    return {
      event_id: uuidFor(`event:${event.id}`),
      event_type: eventType,
      event_version: 1,
      occurred_at: event.at ?? new Date(event.offsetMs ?? 0).toISOString(),
      producer: producerFor(eventType),
      call_session_id: callSessionId,
      causation_id: null,
      payload: eventPayload(eventType, legacyId, event),
      offset_ms: event.offsetMs,
    }
  })
}

function mediaStream(callSessionId, legacyId, startedAt, endedAt, live) {
  return {
    record_layer: 'observation',
    id: uuidFor(`stream:${legacyId}`),
    call_session_id: callSessionId,
    external_stream_id: `mock-stream-${legacyId}`,
    protocol: 'switchboard.media.v1',
    encoding: 'audio/pcmu',
    sample_rate_hz: 8000,
    state: live ? 'streaming' : endedAt ? 'closed' : 'failed',
    started_at: startedAt,
    ended_at: live ? null : endedAt,
  }
}

function classificationOf(value) {
  return {
    label: value.label,
    record_layer: recordLayer(value.provenance),
    confidence: value.confidence,
  }
}

function pipelineOf(pipeline, sampledAt) {
  const select = pipeline.llmMs ?? pipeline.select_ms
  return {
    sampled_at: sampledAt,
    stt_ms: pipeline.sttMs ?? pipeline.stt_ms,
    select_ms: select,
    tts_ms: pipeline.ttsMs ?? pipeline.tts_ms,
    e2e_ms: pipeline.e2eMs ?? pipeline.e2e_ms,
  }
}

function attributionsFor(callSessionId, findings, notes, createdAt) {
  return notes
    .filter((note) => note.campaign_id)
    .map((note) => ({
      record_layer: 'attribution',
      id: uuidFor(`attr:${note.id}`),
      campaign_id: note.campaign_id,
      call_session_id: callSessionId,
      supporting_finding_ids: findings.slice(0, Math.min(2, findings.length)).map((finding) => finding.id),
      method: 'fixture.shared_indicators',
      method_version: '0.1.0',
      confidence: note.score,
      rationale: note.explanation,
      created_at: createdAt,
    }))
    .filter((row) => row.supporting_finding_ids.length > 0)
}

function alignHistoryCall(legacy, idMap) {
  const legacyId = legacy.id
  const callSessionId = mapId(idMap, legacyId)
  const startedMs = Date.parse(legacy.startedAt)
  const endedAt = legacy.endedAt
  const state = callState(legacy.status)
  const mediaStreamId = uuidFor(`stream:${legacyId}`)
  const { segments, conversationTurns, byLegacy } = alignTranscript(
    legacy.transcript,
    callSessionId,
    mediaStreamId,
    startedMs,
  )
  const findings = alignFindings(legacy.intelligence, callSessionId, byLegacy, endedAt ?? legacy.startedAt)
  const notes = alignNotes(legacy.correlation, idMap)
  const createdAt = endedAt ?? legacy.startedAt
  return {
    session: {
      record_layer: 'observation',
      id: callSessionId,
      operator_number_id: OPERATOR_NUMBER_ID,
      external_call_id: legacyId,
      carrier: 'mock',
      caller_number_e164: toE164(legacy.callerNumberMasked),
      called_number_e164: CALLED,
      state,
      started_at: legacy.startedAt,
      answered_at: new Date(startedMs + 200).toISOString(),
      ended_at: endedAt,
      end_reason: state === 'completed' || state === 'failed' ? legacy.timeline?.at(-1)?.detail ?? null : null,
    },
    media_streams: [mediaStream(callSessionId, legacyId, legacy.startedAt, endedAt, false)],
    transcript: segments,
    turns: conversationTurns,
    findings,
    attributions: attributionsFor(callSessionId, findings, notes, createdAt),
    events: alignEvents(legacy.technicalEvents, callSessionId, legacyId, state),
    gaps: {
      conversation_state: legacy.conversationState,
      conversation_state_record_layer: recordLayer(legacy.stateProvenance),
      classification: classificationOf(legacy.classification),
      engagement_duration_ms: legacy.engagementDurationMs,
      duration_ms: legacy.durationMs,
      campaign_id: mapId(idMap, legacy.campaignId),
      campaign_label: legacy.campaignName,
      pipeline: pipelineOf(legacy.pipeline, legacy.pipeline.sampledAt),
      timeline: alignTimeline(legacy.timeline, state),
      state_transitions: alignTransitions(legacy.stateTransitions),
      paired_reads: alignPaired(legacy.observations),
      correlation_notes: notes,
      key_finding_ids: legacy.keyIndicators.map((item) => uuidFor(`finding:${item.id}`)),
    },
  }
}

function alignLive(pair, idMap) {
  const board = pair.board
  const extra = pair.extra
  const legacyId = board.id
  const callSessionId = mapId(idMap, legacyId)
  const startedMs = 0
  const mediaStreamId = uuidFor(`stream:${legacyId}`)
  const { segments, conversationTurns, byLegacy } = alignTranscript(
    board.transcript,
    callSessionId,
    mediaStreamId,
    startedMs,
  )
  const findings = alignFindings(board.intelligence, callSessionId, byLegacy, new Date(0).toISOString())
  const notes = alignNotes(extra.correlation, idMap)
  const startedAt = new Date(0).toISOString()
  const call = {
    session: {
      record_layer: 'observation',
      id: callSessionId,
      operator_number_id: OPERATOR_NUMBER_ID,
      external_call_id: legacyId,
      carrier: 'mock',
      caller_number_e164: toE164(board.callerNumberMasked),
      called_number_e164: CALLED,
      state: 'in_progress',
      started_at: startedAt,
      answered_at: new Date(200).toISOString(),
      ended_at: null,
      end_reason: null,
    },
    media_streams: [mediaStream(callSessionId, legacyId, startedAt, null, true)],
    transcript: segments,
    turns: conversationTurns,
    findings,
    attributions: attributionsFor(callSessionId, findings, notes, startedAt),
    events: alignEvents(extra.technicalEvents, callSessionId, legacyId, 'in_progress').map((event) => ({
      ...event,
      occurred_at: new Date(event.offset_ms).toISOString(),
    })),
    gaps: {
      conversation_state: board.conversationState,
      conversation_state_record_layer: recordLayer(board.stateProvenance),
      classification: classificationOf(board.classification),
      engagement_duration_ms: 0,
      duration_ms: 0,
      campaign_id: mapId(idMap, board.campaignId),
      campaign_label: board.campaignName,
      pipeline: pipelineOf(board.pipeline, startedAt),
      timeline: alignTimeline(extra.timeline, 'in_progress').map((entry) => ({
        ...entry,
        at: new Date(entry.offset_ms).toISOString(),
      })),
      state_transitions: alignTransitions(extra.stateTransitions).map((entry) => ({
        ...entry,
        at: new Date(entry.offset_ms).toISOString(),
      })),
      paired_reads: alignPaired(extra.observations).map((entry) => ({
        ...entry,
        at: new Date(entry.offset_ms).toISOString(),
      })),
      correlation_notes: notes,
      key_finding_ids: extra.keyIndicators.map((item) => uuidFor(`finding:${item.id}`)),
    },
  }
  return {
    started_offset_sec: board.startedOffsetSec,
    engagement_delay_ms: extra.engagementDelayMs,
    call,
  }
}

function alignCampaign(campaign, idMap) {
  const id = mapId(idMap, campaign.id)
  return {
    campaign: {
      record_layer: 'attribution',
      id,
      label: campaign.name,
      status: campaignStatus(campaign.status),
      summary: campaign.summary,
      created_at: campaign.firstSeenAt,
      updated_at: campaign.lastSeenAt,
    },
    gaps: {
      classification: classificationOf(campaign.classification),
      call_count: campaign.callCount,
      activity: campaign.activity,
      timeline: campaign.timeline.map((entry, index) => ({
        id: uuidFor(`ctl:${entry.id}`),
        at: entry.at,
        title: entry.title,
        detail: entry.detail,
        event_type: index === 0 ? 'campaign.opened' : 'campaign.attribution.proposed',
      })),
      related_call_ids: campaign.relatedCallIds.map((callId) => mapId(idMap, callId)),
      script_phrases: campaign.commonScriptPhrases.map(alignSignal),
      shared_indicators: campaign.sharedIndicators.map(alignSignal),
      similarity: campaign.similarity.map((item) => ({
        call_id: mapId(idMap, item.callId),
        external_call_id: item.callId,
        score: item.score,
        explanation: item.explanation,
        record_layer: recordLayer(item.provenance, 'derived'),
      })),
    },
  }
}

function alignSystem(system, liveCount) {
  return {
    sampled_at: system.sampledAt,
    services: [
      { service: 'api', status: 'ok', version: '0.1.0' },
      { service: 'media_gateway', status: 'ok', version: '0.1.0' },
      { service: 'intelligence', status: 'ok', version: '0.1.0' },
      { service: 'dashboard', status: 'ok', version: '0.1.0' },
    ],
    providers: system.providers.map((provider) => ({
      id: provider.id,
      name: provider.name,
      role: provider.role === 'llm' ? 'selector' : provider.role,
      status: provider.status,
      latency_ms: provider.latencyMs,
      detail: provider.detail,
    })),
    latency: {
      stt_ms: system.latency.sttMs,
      select_ms: system.latency.llmMs,
      tts_ms: system.latency.ttsMs,
      e2e_ms: system.latency.e2eMs,
    },
    concurrency: {
      active_calls: liveCount,
      capacity: system.concurrency.capacity,
      queue_depth: system.concurrency.queueDepth,
    },
    cost: {
      window_label: system.cost.windowLabel,
      currency: 'USD',
      stt: system.cost.stt,
      tts: system.cost.tts,
      selector: system.cost.llm,
      telephony: system.cost.telephony,
    },
    errors: system.errors,
  }
}

export function alignCatalog(history, livePairs, campaigns, system) {
  const idMap = buildIdMap(history, livePairs, campaigns)
  return {
    history: history.map((call) => alignHistoryCall(call, idMap)),
    live: livePairs.map((pair) => alignLive(pair, idMap)),
    campaigns: campaigns.map((campaign) => alignCampaign(campaign, idMap)),
    system: alignSystem(system, livePairs.length),
  }
}
