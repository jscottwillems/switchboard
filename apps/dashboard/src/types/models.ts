/**
 * Dashboard read models.
 *
 * Contract fields use the names and enums in packages/schemas (contract 0.1.0).
 * Anything the screens render that those contracts do not define lives under `gaps`
 * and is listed in docs/FRONTEND_DATA_REQUIREMENTS.md.
 */

import type {
  CallSession,
  CallState,
  Campaign,
  CampaignAttribution,
  CampaignStatus,
  ConversationTurn,
  EventType,
  FindingKind,
  FindingStatus,
  IntelligenceFinding,
  MediaStream,
  RecordLayer,
  Speaker,
  TranscriptSegment,
  TranscriptSource,
} from '@switchboard/schemas'

export type {
  CallSession,
  CallState,
  Campaign,
  CampaignAttribution,
  CampaignStatus,
  ConversationTurn,
  EventType,
  FindingKind,
  FindingStatus,
  IntelligenceFinding,
  MediaStream,
  RecordLayer,
  Speaker,
  TranscriptSegment,
  TranscriptSource,
}

/** UI scam-family labels. Not a field on CallSession or Campaign. */
export const CLASSIFICATIONS = [
  'irs_impersonation',
  'tech_support',
  'bank_fraud',
  'romance',
  'utility_shutoff',
  'unknown',
] as const
export type Classification = (typeof CLASSIFICATIONS)[number]

/** Dialogue beat the operator board shows. Not CallState. */
export const CONVERSATION_STATES = [
  'ringing',
  'greeting',
  'identity_probe',
  'pretext',
  'urgency',
  'payment_request',
  'compliance_stall',
  'extraction',
  'closing',
  'ended',
] as const
export type ConversationState = (typeof CONVERSATION_STATES)[number]

/** Paired-read categories. Not FindingKind. */
export const OBSERVATION_CATEGORIES = [
  'payment',
  'identity',
  'threat',
  'tooling',
  'script',
  'callback',
  'other',
] as const
export type ObservationCategory = (typeof OBSERVATION_CATEGORIES)[number]

export const SEVERITIES = ['info', 'warn', 'error'] as const
export type Severity = (typeof SEVERITIES)[number]

/** Hot-path roles for the operator gauge. Not HealthResponse.service. */
export const PROVIDER_ROLES = ['telephony', 'stt', 'tts', 'selector'] as const
export type ProviderRole = (typeof PROVIDER_ROLES)[number]

export const PROVIDER_STATUSES = ['ok', 'degraded', 'down'] as const
export type ProviderStatus = (typeof PROVIDER_STATUSES)[number]

export const SERVICES = ['api', 'media_gateway', 'intelligence', 'dashboard'] as const
export type ServiceName = (typeof SERVICES)[number]

export interface ClassifiedValue {
  label: Classification
  record_layer: RecordLayer
  confidence: number | null
}

export interface PipelineLatency {
  sampled_at: string
  stt_ms: number
  select_ms: number
  tts_ms: number
  e2e_ms: number
}

export interface TimelineEntry {
  id: string
  at: string
  offset_ms: number
  /** Null when the row is an operator note rather than a bus event. */
  event_type: EventType | null
  title: string
  detail: string
}

export interface StateTransition {
  id: string
  at: string
  offset_ms: number
  from: ConversationState | null
  to: ConversationState
  reason: string
  record_layer: RecordLayer
}

export interface PairedRead {
  id: string
  at: string
  offset_ms: number
  category: ObservationCategory
  raw: { text: string; record_layer: 'observation' }
  interpretation: { text: string; record_layer: 'interpretation' } | null
}

export interface CorrelationNote {
  id: string
  campaign_id: string | null
  campaign_label: string | null
  score: number
  summary: string
  explanation: string
  record_layer: RecordLayer
  matched_on: Array<{ label: string; record_layer: RecordLayer }>
}

/** EventEnvelope plus the media-timeline offset the table shows. offset_ms is not on the envelope. */
export interface DashboardEvent {
  event_id: string
  event_type: EventType
  event_version: 1
  occurred_at: string
  producer: 'api' | 'media_gateway' | 'intelligence'
  call_session_id: string
  causation_id: string | null
  payload: Record<string, unknown>
  offset_ms: number
}

export interface CallGaps {
  conversation_state: ConversationState
  conversation_state_record_layer: RecordLayer
  classification: ClassifiedValue
  engagement_duration_ms: number
  duration_ms: number
  campaign_id: string | null
  campaign_label: string | null
  pipeline: PipelineLatency
  timeline: TimelineEntry[]
  state_transitions: StateTransition[]
  paired_reads: PairedRead[]
  correlation_notes: CorrelationNote[]
  key_finding_ids: string[]
}

/** CallDetailResponse plus operator gaps and the event log. */
export interface CallDetail {
  session: CallSession
  media_streams: MediaStream[]
  transcript: TranscriptSegment[]
  turns: ConversationTurn[]
  findings: IntelligenceFinding[]
  attributions: CampaignAttribution[]
  events: DashboardEvent[]
  gaps: CallGaps
}

export interface CallSummary {
  session: CallSession
  gaps: Pick<
    CallGaps,
    | 'conversation_state'
    | 'conversation_state_record_layer'
    | 'classification'
    | 'engagement_duration_ms'
    | 'duration_ms'
    | 'campaign_id'
    | 'campaign_label'
  >
  key_findings: IntelligenceFinding[]
}

export interface LiveCall {
  session: CallSession
  transcript: TranscriptSegment[]
  findings: IntelligenceFinding[]
  gaps: Pick<
    CallGaps,
    | 'conversation_state'
    | 'conversation_state_record_layer'
    | 'classification'
    | 'campaign_id'
    | 'campaign_label'
    | 'pipeline'
  >
}

/** Campaign-level chip. Not an IntelligenceFinding: findings require a call_session_id. */
export interface CampaignSignal {
  id: string
  kind: FindingKind
  value: string
  raw_quote: string
  record_layer: RecordLayer
  confidence: number | null
  status: FindingStatus
}

export interface ActivityBucket {
  day: string
  hour: number
  count: number
}

export interface CampaignTimelineEntry {
  id: string
  at: string
  title: string
  detail: string
  event_type: 'campaign.opened' | 'campaign.attribution.proposed'
}

export interface CampaignSimilarity {
  call_id: string
  external_call_id: string
  score: number
  explanation: string
  record_layer: RecordLayer
}

export interface CampaignGaps {
  classification: ClassifiedValue
  call_count: number
  active_call_count: number
  activity: ActivityBucket[]
  timeline: CampaignTimelineEntry[]
  script_phrases: CampaignSignal[]
  shared_indicators: CampaignSignal[]
  similarity: CampaignSimilarity[]
  related_call_ids: string[]
}

export interface CampaignSummary {
  campaign: Campaign
  gaps: Pick<CampaignGaps, 'classification' | 'call_count' | 'active_call_count' | 'activity' | 'shared_indicators'>
}

export interface CampaignDetail {
  campaign: Campaign
  gaps: CampaignGaps
  related_calls: CallSummary[]
}

export interface ProviderHealth {
  id: string
  name: string
  role: ProviderRole
  status: ProviderStatus
  latency_ms: number
  detail: string
}

export interface ServiceHealth {
  service: ServiceName
  status: 'ok'
  version: string
}

export interface SystemHealth {
  sampled_at: string
  services: ServiceHealth[]
  providers: ProviderHealth[]
  latency: {
    stt_ms: number
    select_ms: number
    tts_ms: number
    e2e_ms: number
  }
  concurrency: {
    active_calls: number
    capacity: number
    queue_depth: number
  }
  cost: {
    window_label: string
    currency: 'USD'
    stt: number
    tts: number
    selector: number
    telephony: number
  }
  errors: Array<{
    id: string
    at: string
    source: string
    severity: 'warn' | 'error'
    message: string
  }>
}

/** Shared row shape for finding lists and campaign signals. */
export interface FindingRow {
  id: string
  kind: FindingKind
  value: string
  raw_quote: string
  record_layer: RecordLayer
  confidence: number | null
  status: FindingStatus
}
