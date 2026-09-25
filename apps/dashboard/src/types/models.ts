/**
 * Read models for the ops dashboard.
 * Field-by-field UI usage is listed in docs/FRONTEND_DATA_REQUIREMENTS.md.
 * These types are the frontend contract, not a claim that a backend implements them.
 */

export const PROVENANCES = ['observed', 'inferred', 'unverified'] as const
export type Provenance = (typeof PROVENANCES)[number]

export const INTELLIGENCE_BASES = ['raw', 'derived'] as const
export type IntelligenceBasis = (typeof INTELLIGENCE_BASES)[number]

export const CLASSIFICATIONS = [
  'irs_impersonation',
  'tech_support',
  'bank_fraud',
  'romance',
  'utility_shutoff',
  'unknown',
] as const
export type Classification = (typeof CLASSIFICATIONS)[number]

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

export const CALL_STATUSES = ['active', 'completed', 'abandoned', 'error'] as const
export type CallStatus = (typeof CALL_STATUSES)[number]

export const CAMPAIGN_STATUSES = ['active', 'watching', 'closed'] as const
export type CampaignStatus = (typeof CAMPAIGN_STATUSES)[number]

export const INTELLIGENCE_KINDS = [
  'indicator',
  'entity',
  'script_phrase',
  'tactic',
  'amount',
  'callback',
] as const
export type IntelligenceKind = (typeof INTELLIGENCE_KINDS)[number]

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

export const SPEAKERS = ['caller', 'honeypot'] as const
export type Speaker = (typeof SPEAKERS)[number]

export const TIMELINE_KINDS = ['telephony', 'state', 'intel', 'transcript', 'error'] as const
export type TimelineKind = (typeof TIMELINE_KINDS)[number]

export const TECHNICAL_SOURCES = ['telephony', 'stt', 'tts', 'llm', 'orchestrator'] as const
export type TechnicalSource = (typeof TECHNICAL_SOURCES)[number]

export const SEVERITIES = ['info', 'warn', 'error'] as const
export type Severity = (typeof SEVERITIES)[number]

export const PROVIDER_ROLES = ['telephony', 'stt', 'tts', 'llm'] as const
export type ProviderRole = (typeof PROVIDER_ROLES)[number]

export const PROVIDER_STATUSES = ['ok', 'degraded', 'down'] as const
export type ProviderStatus = (typeof PROVIDER_STATUSES)[number]

export interface ClassifiedValue {
  label: Classification
  provenance: Provenance
  confidence: number | null
}

export interface IntelligenceItem {
  id: string
  kind: IntelligenceKind
  label: string
  value: string
  provenance: Provenance
  basis: IntelligenceBasis
  confidence: number | null
  evidenceTurnIds: string[]
}

export interface TranscriptTurn {
  id: string
  speaker: Speaker
  text: string
  offsetMs: number
  provenance: Provenance
}

export interface PipelineLatency {
  sampledAt: string
  sttMs: number
  llmMs: number
  ttsMs: number
  e2eMs: number
}

export interface TimelineEntry {
  id: string
  at: string
  offsetMs: number
  kind: TimelineKind
  title: string
  detail: string
}

export interface StateTransition {
  id: string
  at: string
  offsetMs: number
  from: ConversationState | null
  to: ConversationState
  reason: string
  provenance: Provenance
}

export interface ObservationText {
  text: string
  provenance: Provenance
}

export interface StructuredObservation {
  id: string
  at: string
  offsetMs: number
  category: ObservationCategory
  raw: ObservationText
  interpretation: ObservationText | null
}

export interface CorrelationMatch {
  label: string
  provenance: Provenance
}

export interface CorrelationReasoning {
  id: string
  campaignId: string | null
  campaignName: string | null
  score: number
  summary: string
  explanation: string
  provenance: Provenance
  matchedOn: CorrelationMatch[]
}

export interface EventAttribute {
  key: string
  value: string
}

export interface TechnicalEvent {
  id: string
  at: string
  offsetMs: number
  source: TechnicalSource
  severity: Severity
  message: string
  attributes: EventAttribute[]
}

export interface CallSummary {
  id: string
  startedAt: string
  endedAt: string | null
  durationMs: number
  engagementDurationMs: number
  status: CallStatus
  callerNumberMasked: string
  conversationState: ConversationState
  stateProvenance: Provenance
  classification: ClassifiedValue
  campaignId: string | null
  campaignName: string | null
  keyIndicators: IntelligenceItem[]
}

export interface CallDetail extends CallSummary {
  intelligence: IntelligenceItem[]
  pipeline: PipelineLatency
  timeline: TimelineEntry[]
  transcript: TranscriptTurn[]
  stateTransitions: StateTransition[]
  observations: StructuredObservation[]
  correlation: CorrelationReasoning[]
  technicalEvents: TechnicalEvent[]
}

export interface LiveCall {
  id: string
  startedAt: string
  callerNumberMasked: string
  status: 'active'
  conversationState: ConversationState
  stateProvenance: Provenance
  classification: ClassifiedValue
  campaignId: string | null
  campaignName: string | null
  transcript: TranscriptTurn[]
  intelligence: IntelligenceItem[]
  pipeline: PipelineLatency
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
}

export interface CampaignSimilarity {
  callId: string
  score: number
  explanation: string
  provenance: Provenance
}

export interface CampaignSummary {
  id: string
  name: string
  status: CampaignStatus
  classification: ClassifiedValue
  firstSeenAt: string
  lastSeenAt: string
  callCount: number
  activeCallCount: number
  summary: string
  topIndicators: IntelligenceItem[]
  activity: ActivityBucket[]
}

export interface CampaignDetail extends CampaignSummary {
  timeline: CampaignTimelineEntry[]
  relatedCalls: CallSummary[]
  commonScriptPhrases: IntelligenceItem[]
  sharedIndicators: IntelligenceItem[]
  similarity: CampaignSimilarity[]
}

export interface ProviderHealth {
  id: string
  name: string
  role: ProviderRole
  status: ProviderStatus
  latencyMs: number
  detail: string
}

export interface SystemHealth {
  sampledAt: string
  providers: ProviderHealth[]
  latency: {
    sttMs: number
    llmMs: number
    ttsMs: number
    e2eMs: number
  }
  concurrency: {
    activeCalls: number
    capacity: number
    queueDepth: number
  }
  cost: {
    windowLabel: string
    currency: 'USD'
    stt: number
    tts: number
    llm: number
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
