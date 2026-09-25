import type {
  ActivityBucket,
  CallDetail,
  CampaignTimelineEntry,
  ClassifiedValue,
  CorrelationReasoning,
  IntelligenceItem,
  StateTransition,
  StructuredObservation,
  SystemHealth,
  TechnicalEvent,
  TimelineEntry,
  TranscriptTurn,
} from '@/types/models'
import {
  CALL_STATUSES,
  CAMPAIGN_STATUSES,
  CLASSIFICATIONS,
  CONVERSATION_STATES,
  INTELLIGENCE_BASES,
  INTELLIGENCE_KINDS,
  OBSERVATION_CATEGORIES,
  PROVENANCES,
  PROVIDER_ROLES,
  PROVIDER_STATUSES,
  SEVERITIES,
  SPEAKERS,
  TECHNICAL_SOURCES,
  TIMELINE_KINDS,
} from '@/types/models'
import type { CampaignFixture, LiveCallFixture, LiveDetailExtra } from '@/mocks/fixtureTypes'

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
  if (typeof value !== 'string') fail(ctx, `${key} must be a string or null`)
  return value
}

function numberValue(source: Record<string, unknown>, key: string, ctx: string): number {
  const value = source[key]
  if (typeof value !== 'number' || Number.isNaN(value)) fail(ctx, `${key} must be a number`)
  return value
}

function nullableScore(source: Record<string, unknown>, key: string, ctx: string): number | null {
  const value = source[key]
  if (value === null) return null
  if (typeof value !== 'number' || value < 0 || value > 1) fail(ctx, `${key} must be null or 0..1`)
  return value
}

function oneOf<T extends string>(source: Record<string, unknown>, key: string, allowed: readonly T[], ctx: string): T {
  const value = text(source, key, ctx)
  if (!(allowed as readonly string[]).includes(value)) fail(ctx, `${key} has unexpected value ${value}`)
  return value as T
}

function classified(value: unknown, ctx: string): ClassifiedValue {
  const source = record(value, ctx)
  return {
    label: oneOf(source, 'label', CLASSIFICATIONS, ctx),
    provenance: oneOf(source, 'provenance', PROVENANCES, ctx),
    confidence: nullableScore(source, 'confidence', ctx),
  }
}

function intelligence(value: unknown, ctx: string): IntelligenceItem {
  const source = record(value, ctx)
  return {
    id: text(source, 'id', ctx),
    kind: oneOf(source, 'kind', INTELLIGENCE_KINDS, ctx),
    label: text(source, 'label', ctx),
    value: text(source, 'value', ctx),
    provenance: oneOf(source, 'provenance', PROVENANCES, ctx),
    basis: oneOf(source, 'basis', INTELLIGENCE_BASES, ctx),
    confidence: nullableScore(source, 'confidence', ctx),
    evidenceTurnIds: array(source.evidenceTurnIds, `${ctx}.evidenceTurnIds`).map((item, index) => {
      if (typeof item !== 'string') fail(ctx, `evidenceTurnIds[${index}] must be a string`)
      return item
    }),
  }
}

function intelligenceList(value: unknown, ctx: string): IntelligenceItem[] {
  return array(value, ctx).map((item, index) => intelligence(item, `${ctx}[${index}]`))
}

function transcript(value: unknown, ctx: string): TranscriptTurn {
  const source = record(value, ctx)
  return {
    id: text(source, 'id', ctx),
    speaker: oneOf(source, 'speaker', SPEAKERS, ctx),
    text: text(source, 'text', ctx),
    offsetMs: numberValue(source, 'offsetMs', ctx),
    provenance: oneOf(source, 'provenance', PROVENANCES, ctx),
  }
}

function timeline(value: unknown, ctx: string, withAt: boolean): TimelineEntry {
  const source = record(value, ctx)
  return {
    id: text(source, 'id', ctx),
    at: withAt ? text(source, 'at', ctx) : '',
    offsetMs: numberValue(source, 'offsetMs', ctx),
    kind: oneOf(source, 'kind', TIMELINE_KINDS, ctx),
    title: text(source, 'title', ctx),
    detail: text(source, 'detail', ctx),
  }
}

function transition(value: unknown, ctx: string, withAt: boolean): StateTransition {
  const source = record(value, ctx)
  const from = source.from
  if (from !== null && (typeof from !== 'string' || !(CONVERSATION_STATES as readonly string[]).includes(from))) {
    fail(ctx, 'from must be a conversation state or null')
  }
  return {
    id: text(source, 'id', ctx),
    at: withAt ? text(source, 'at', ctx) : '',
    offsetMs: numberValue(source, 'offsetMs', ctx),
    from: from as StateTransition['from'],
    to: oneOf(source, 'to', CONVERSATION_STATES, ctx),
    reason: text(source, 'reason', ctx),
    provenance: oneOf(source, 'provenance', PROVENANCES, ctx),
  }
}

function observation(value: unknown, ctx: string, withAt: boolean): StructuredObservation {
  const source = record(value, ctx)
  const raw = record(source.raw, `${ctx}.raw`)
  const interpretation = source.interpretation
  let parsedInterpretation: StructuredObservation['interpretation'] = null
  if (interpretation !== null) {
    const reading = record(interpretation, `${ctx}.interpretation`)
    parsedInterpretation = {
      text: text(reading, 'text', `${ctx}.interpretation`),
      provenance: oneOf(reading, 'provenance', PROVENANCES, `${ctx}.interpretation`),
    }
  }
  return {
    id: text(source, 'id', ctx),
    at: withAt ? text(source, 'at', ctx) : '',
    offsetMs: numberValue(source, 'offsetMs', ctx),
    category: oneOf(source, 'category', OBSERVATION_CATEGORIES, ctx),
    raw: {
      text: text(raw, 'text', `${ctx}.raw`),
      provenance: oneOf(raw, 'provenance', PROVENANCES, `${ctx}.raw`),
    },
    interpretation: parsedInterpretation,
  }
}

function correlation(value: unknown, ctx: string): CorrelationReasoning {
  const source = record(value, ctx)
  return {
    id: text(source, 'id', ctx),
    campaignId: nullableText(source, 'campaignId', ctx),
    campaignName: nullableText(source, 'campaignName', ctx),
    score: numberValue(source, 'score', ctx),
    summary: text(source, 'summary', ctx),
    explanation: text(source, 'explanation', ctx),
    provenance: oneOf(source, 'provenance', PROVENANCES, ctx),
    matchedOn: array(source.matchedOn, `${ctx}.matchedOn`).map((item, index) => {
      const match = record(item, `${ctx}.matchedOn[${index}]`)
      return {
        label: text(match, 'label', `${ctx}.matchedOn[${index}]`),
        provenance: oneOf(match, 'provenance', PROVENANCES, `${ctx}.matchedOn[${index}]`),
      }
    }),
  }
}

function attributes(value: unknown, ctx: string): TechnicalEvent['attributes'] {
  return array(value, ctx).map((item, index) => {
    const attribute = record(item, `${ctx}[${index}]`)
    return {
      key: text(attribute, 'key', `${ctx}[${index}]`),
      value: text(attribute, 'value', `${ctx}[${index}]`),
    }
  })
}

function technical(value: unknown, ctx: string, withAt: boolean): TechnicalEvent {
  const source = record(value, ctx)
  return {
    id: text(source, 'id', ctx),
    at: withAt ? text(source, 'at', ctx) : '',
    offsetMs: numberValue(source, 'offsetMs', ctx),
    source: oneOf(source, 'source', TECHNICAL_SOURCES, ctx),
    severity: oneOf(source, 'severity', SEVERITIES, ctx),
    message: text(source, 'message', ctx),
    attributes: attributes(source.attributes, `${ctx}.attributes`),
  }
}

function pipelineNumbers(source: Record<string, unknown>, ctx: string): {
  sttMs: number
  llmMs: number
  ttsMs: number
  e2eMs: number
} {
  return {
    sttMs: numberValue(source, 'sttMs', ctx),
    llmMs: numberValue(source, 'llmMs', ctx),
    ttsMs: numberValue(source, 'ttsMs', ctx),
    e2eMs: numberValue(source, 'e2eMs', ctx),
  }
}

export function parseCallDetails(value: unknown): CallDetail[] {
  return array(value, 'callDetails').map((item, index) => {
    const ctx = `callDetails[${index}]`
    const source = record(item, ctx)
    const pipeline = record(source.pipeline, `${ctx}.pipeline`)
    return {
      id: text(source, 'id', ctx),
      startedAt: text(source, 'startedAt', ctx),
      endedAt: nullableText(source, 'endedAt', ctx),
      durationMs: numberValue(source, 'durationMs', ctx),
      engagementDurationMs: numberValue(source, 'engagementDurationMs', ctx),
      status: oneOf(source, 'status', CALL_STATUSES, ctx),
      callerNumberMasked: text(source, 'callerNumberMasked', ctx),
      conversationState: oneOf(source, 'conversationState', CONVERSATION_STATES, ctx),
      stateProvenance: oneOf(source, 'stateProvenance', PROVENANCES, ctx),
      classification: classified(source.classification, `${ctx}.classification`),
      campaignId: nullableText(source, 'campaignId', ctx),
      campaignName: nullableText(source, 'campaignName', ctx),
      keyIndicators: intelligenceList(source.keyIndicators, `${ctx}.keyIndicators`),
      intelligence: intelligenceList(source.intelligence, `${ctx}.intelligence`),
      pipeline: {
        sampledAt: text(pipeline, 'sampledAt', `${ctx}.pipeline`),
        ...pipelineNumbers(pipeline, `${ctx}.pipeline`),
      },
      timeline: array(source.timeline, `${ctx}.timeline`).map((entry, entryIndex) => timeline(entry, `${ctx}.timeline[${entryIndex}]`, true)),
      transcript: array(source.transcript, `${ctx}.transcript`).map((entry, entryIndex) => transcript(entry, `${ctx}.transcript[${entryIndex}]`)),
      stateTransitions: array(source.stateTransitions, `${ctx}.stateTransitions`).map((entry, entryIndex) =>
        transition(entry, `${ctx}.stateTransitions[${entryIndex}]`, true),
      ),
      observations: array(source.observations, `${ctx}.observations`).map((entry, entryIndex) =>
        observation(entry, `${ctx}.observations[${entryIndex}]`, true),
      ),
      correlation: array(source.correlation, `${ctx}.correlation`).map((entry, entryIndex) => correlation(entry, `${ctx}.correlation[${entryIndex}]`)),
      technicalEvents: array(source.technicalEvents, `${ctx}.technicalEvents`).map((entry, entryIndex) =>
        technical(entry, `${ctx}.technicalEvents[${entryIndex}]`, true),
      ),
    }
  })
}

export function parseLiveCalls(value: unknown): LiveCallFixture[] {
  return array(value, 'liveCalls').map((item, index) => {
    const ctx = `liveCalls[${index}]`
    const source = record(item, ctx)
    const pipeline = record(source.pipeline, `${ctx}.pipeline`)
    return {
      id: text(source, 'id', ctx),
      startedOffsetSec: numberValue(source, 'startedOffsetSec', ctx),
      callerNumberMasked: text(source, 'callerNumberMasked', ctx),
      conversationState: oneOf(source, 'conversationState', CONVERSATION_STATES, ctx),
      stateProvenance: oneOf(source, 'stateProvenance', PROVENANCES, ctx),
      classification: classified(source.classification, `${ctx}.classification`),
      campaignId: nullableText(source, 'campaignId', ctx),
      campaignName: nullableText(source, 'campaignName', ctx),
      transcript: array(source.transcript, `${ctx}.transcript`).map((entry, entryIndex) => transcript(entry, `${ctx}.transcript[${entryIndex}]`)),
      intelligence: intelligenceList(source.intelligence, `${ctx}.intelligence`),
      pipeline: pipelineNumbers(pipeline, `${ctx}.pipeline`),
    }
  })
}

export function parseLiveExtras(value: unknown): LiveDetailExtra[] {
  return array(value, 'liveExtras').map((item, index) => {
    const ctx = `liveExtras[${index}]`
    const source = record(item, ctx)
    return {
      id: text(source, 'id', ctx),
      engagementDelayMs: numberValue(source, 'engagementDelayMs', ctx),
      keyIndicators: intelligenceList(source.keyIndicators, `${ctx}.keyIndicators`),
      timeline: array(source.timeline, `${ctx}.timeline`).map((entry, entryIndex) => {
        const parsed = timeline(entry, `${ctx}.timeline[${entryIndex}]`, false)
        return { id: parsed.id, offsetMs: parsed.offsetMs, kind: parsed.kind, title: parsed.title, detail: parsed.detail }
      }),
      stateTransitions: array(source.stateTransitions, `${ctx}.stateTransitions`).map((entry, entryIndex) => {
        const parsed = transition(entry, `${ctx}.stateTransitions[${entryIndex}]`, false)
        return {
          id: parsed.id,
          offsetMs: parsed.offsetMs,
          from: parsed.from,
          to: parsed.to,
          reason: parsed.reason,
          provenance: parsed.provenance,
        }
      }),
      observations: array(source.observations, `${ctx}.observations`).map((entry, entryIndex) => {
        const parsed = observation(entry, `${ctx}.observations[${entryIndex}]`, false)
        return {
          id: parsed.id,
          offsetMs: parsed.offsetMs,
          category: parsed.category,
          raw: parsed.raw,
          interpretation: parsed.interpretation,
        }
      }),
      correlation: array(source.correlation, `${ctx}.correlation`).map((entry, entryIndex) => correlation(entry, `${ctx}.correlation[${entryIndex}]`)),
      technicalEvents: array(source.technicalEvents, `${ctx}.technicalEvents`).map((entry, entryIndex) => {
        const parsed = technical(entry, `${ctx}.technicalEvents[${entryIndex}]`, false)
        return {
          id: parsed.id,
          offsetMs: parsed.offsetMs,
          source: parsed.source,
          severity: parsed.severity,
          message: parsed.message,
          attributes: parsed.attributes,
        }
      }),
    }
  })
}

function activity(value: unknown, ctx: string): ActivityBucket {
  const source = record(value, ctx)
  const hour = numberValue(source, 'hour', ctx)
  if (hour < 0 || hour > 23) fail(ctx, 'hour out of range')
  return {
    day: text(source, 'day', ctx),
    hour,
    count: numberValue(source, 'count', ctx),
  }
}

export function parseCampaigns(value: unknown): CampaignFixture[] {
  return array(value, 'campaigns').map((item, index) => {
    const ctx = `campaigns[${index}]`
    const source = record(item, ctx)
    return {
      id: text(source, 'id', ctx),
      name: text(source, 'name', ctx),
      status: oneOf(source, 'status', CAMPAIGN_STATUSES, ctx),
      classification: classified(source.classification, `${ctx}.classification`),
      firstSeenAt: text(source, 'firstSeenAt', ctx),
      lastSeenAt: text(source, 'lastSeenAt', ctx),
      callCount: numberValue(source, 'callCount', ctx),
      summary: text(source, 'summary', ctx),
      relatedCallIds: array(source.relatedCallIds, `${ctx}.relatedCallIds`).map((entry, entryIndex) => {
        if (typeof entry !== 'string') fail(ctx, `relatedCallIds[${entryIndex}] must be a string`)
        return entry
      }),
      timeline: array(source.timeline, `${ctx}.timeline`).map((entry, entryIndex) => {
        const event = record(entry, `${ctx}.timeline[${entryIndex}]`)
        const parsed: CampaignTimelineEntry = {
          id: text(event, 'id', `${ctx}.timeline[${entryIndex}]`),
          at: text(event, 'at', `${ctx}.timeline[${entryIndex}]`),
          title: text(event, 'title', `${ctx}.timeline[${entryIndex}]`),
          detail: text(event, 'detail', `${ctx}.timeline[${entryIndex}]`),
        }
        return parsed
      }),
      commonScriptPhrases: intelligenceList(source.commonScriptPhrases, `${ctx}.commonScriptPhrases`),
      sharedIndicators: intelligenceList(source.sharedIndicators, `${ctx}.sharedIndicators`),
      similarity: array(source.similarity, `${ctx}.similarity`).map((entry, entryIndex) => {
        const item = record(entry, `${ctx}.similarity[${entryIndex}]`)
        return {
          callId: text(item, 'callId', `${ctx}.similarity[${entryIndex}]`),
          score: numberValue(item, 'score', `${ctx}.similarity[${entryIndex}]`),
          explanation: text(item, 'explanation', `${ctx}.similarity[${entryIndex}]`),
          provenance: oneOf(item, 'provenance', PROVENANCES, `${ctx}.similarity[${entryIndex}]`),
        }
      }),
      activity: array(source.activity, `${ctx}.activity`).map((entry, entryIndex) => activity(entry, `${ctx}.activity[${entryIndex}]`)),
    }
  })
}

export function parseSystemHealth(value: unknown): SystemHealth {
  const source = record(value, 'system')
  const latency = record(source.latency, 'system.latency')
  const concurrency = record(source.concurrency, 'system.concurrency')
  const cost = record(source.cost, 'system.cost')
  const currency = text(cost, 'currency', 'system.cost')
  if (currency !== 'USD') fail('system.cost', 'currency must be USD')
  return {
    sampledAt: text(source, 'sampledAt', 'system'),
    providers: array(source.providers, 'system.providers').map((item, index) => {
      const provider = record(item, `system.providers[${index}]`)
      return {
        id: text(provider, 'id', `system.providers[${index}]`),
        name: text(provider, 'name', `system.providers[${index}]`),
        role: oneOf(provider, 'role', PROVIDER_ROLES, `system.providers[${index}]`),
        status: oneOf(provider, 'status', PROVIDER_STATUSES, `system.providers[${index}]`),
        latencyMs: numberValue(provider, 'latencyMs', `system.providers[${index}]`),
        detail: text(provider, 'detail', `system.providers[${index}]`),
      }
    }),
    latency: pipelineNumbers(latency, 'system.latency'),
    concurrency: {
      activeCalls: numberValue(concurrency, 'activeCalls', 'system.concurrency'),
      capacity: numberValue(concurrency, 'capacity', 'system.concurrency'),
      queueDepth: numberValue(concurrency, 'queueDepth', 'system.concurrency'),
    },
    cost: {
      windowLabel: text(cost, 'windowLabel', 'system.cost'),
      currency: 'USD',
      stt: numberValue(cost, 'stt', 'system.cost'),
      tts: numberValue(cost, 'tts', 'system.cost'),
      llm: numberValue(cost, 'llm', 'system.cost'),
      telephony: numberValue(cost, 'telephony', 'system.cost'),
    },
    errors: array(source.errors, 'system.errors').map((item, index) => {
      const error = record(item, `system.errors[${index}]`)
      const severity = oneOf(error, 'severity', SEVERITIES, `system.errors[${index}]`)
      if (severity === 'info') fail(`system.errors[${index}]`, 'error log does not include info')
      return {
        id: text(error, 'id', `system.errors[${index}]`),
        at: text(error, 'at', `system.errors[${index}]`),
        source: text(error, 'source', `system.errors[${index}]`),
        severity,
        message: text(error, 'message', `system.errors[${index}]`),
      }
    }),
  }
}
