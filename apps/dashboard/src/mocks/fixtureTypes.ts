import type {
  CallDetail,
  CampaignStatus,
  ClassifiedValue,
  CorrelationReasoning,
  IntelligenceItem,
  StateTransition,
  StructuredObservation,
  TechnicalEvent,
  TimelineEntry,
  TranscriptTurn,
} from '@/types/models'

/** Mock-only live board row. The adapter turns startedOffsetSec into startedAt. */
export interface LiveCallFixture {
  id: string
  startedOffsetSec: number
  callerNumberMasked: string
  conversationState: CallDetail['conversationState']
  stateProvenance: CallDetail['stateProvenance']
  classification: ClassifiedValue
  campaignId: string | null
  campaignName: string | null
  transcript: TranscriptTurn[]
  intelligence: IntelligenceItem[]
  pipeline: {
    sttMs: number
    llmMs: number
    ttsMs: number
    e2eMs: number
  }
}

export interface LiveDetailExtra {
  id: string
  engagementDelayMs: number
  keyIndicators: IntelligenceItem[]
  timeline: Array<Omit<TimelineEntry, 'at'>>
  stateTransitions: Array<Omit<StateTransition, 'at'>>
  observations: Array<Omit<StructuredObservation, 'at'>>
  correlation: CorrelationReasoning[]
  technicalEvents: Array<Omit<TechnicalEvent, 'at'>>
}

export interface CampaignFixture {
  id: string
  name: string
  status: CampaignStatus
  classification: ClassifiedValue
  firstSeenAt: string
  lastSeenAt: string
  callCount: number
  summary: string
  relatedCallIds: string[]
  timeline: Array<{ id: string; at: string; title: string; detail: string }>
  commonScriptPhrases: IntelligenceItem[]
  sharedIndicators: IntelligenceItem[]
  similarity: Array<{
    callId: string
    score: number
    explanation: string
    provenance: CallDetail['stateProvenance']
  }>
  activity: Array<{ day: string; hour: number; count: number }>
}
