import type { OpsDataPort } from '@/data/port'
import type {
  CallDetail,
  CallSummary,
  CampaignDetail,
  CampaignSummary,
  LiveCall,
  SystemHealth,
} from '@/types/models'
import {
  callDetails,
  campaignFixtures,
  liveCallFixtures,
  liveDetailExtras,
  systemHealthFixture,
} from '@/mocks/fixtures'
import type { CampaignFixture, LiveCallFixture, LiveDetailExtra } from '@/mocks/fixtureTypes'

const RESPONSE_DELAY_MS = 40

function delay(): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, RESPONSE_DELAY_MS)
  })
}

function stamp<T extends { offsetMs: number }>(startMs: number, item: T): T & { at: string } {
  return { ...item, at: new Date(startMs + item.offsetMs).toISOString() }
}

function toCallSummary(detail: CallDetail): CallSummary {
  return {
    id: detail.id,
    startedAt: detail.startedAt,
    endedAt: detail.endedAt,
    durationMs: detail.durationMs,
    engagementDurationMs: detail.engagementDurationMs,
    status: detail.status,
    callerNumberMasked: detail.callerNumberMasked,
    conversationState: detail.conversationState,
    stateProvenance: detail.stateProvenance,
    classification: detail.classification,
    campaignId: detail.campaignId,
    campaignName: detail.campaignName,
    keyIndicators: detail.keyIndicators,
  }
}

function assembleLiveCall(fixture: LiveCallFixture, nowMs: number): LiveCall {
  const startedAtMs = nowMs + fixture.startedOffsetSec * 1000
  return {
    id: fixture.id,
    startedAt: new Date(startedAtMs).toISOString(),
    callerNumberMasked: fixture.callerNumberMasked,
    status: 'active',
    conversationState: fixture.conversationState,
    stateProvenance: fixture.stateProvenance,
    classification: fixture.classification,
    campaignId: fixture.campaignId,
    campaignName: fixture.campaignName,
    transcript: fixture.transcript,
    intelligence: fixture.intelligence,
    pipeline: {
      sampledAt: new Date(nowMs).toISOString(),
      sttMs: fixture.pipeline.sttMs,
      llmMs: fixture.pipeline.llmMs,
      ttsMs: fixture.pipeline.ttsMs,
      e2eMs: fixture.pipeline.e2eMs,
    },
  }
}

function assembleLiveDetail(fixture: LiveCallFixture, extra: LiveDetailExtra, nowMs: number): CallDetail {
  const live = assembleLiveCall(fixture, nowMs)
  const startedAtMs = Date.parse(live.startedAt)
  const durationMs = Math.max(0, nowMs - startedAtMs)
  return {
    id: live.id,
    startedAt: live.startedAt,
    endedAt: null,
    durationMs,
    engagementDurationMs: Math.max(0, durationMs - extra.engagementDelayMs),
    status: 'active',
    callerNumberMasked: live.callerNumberMasked,
    conversationState: live.conversationState,
    stateProvenance: live.stateProvenance,
    classification: live.classification,
    campaignId: live.campaignId,
    campaignName: live.campaignName,
    keyIndicators: extra.keyIndicators,
    intelligence: live.intelligence,
    pipeline: live.pipeline,
    timeline: extra.timeline.map((entry) => stamp(startedAtMs, entry)),
    transcript: live.transcript,
    stateTransitions: extra.stateTransitions.map((entry) => stamp(startedAtMs, entry)),
    observations: extra.observations.map((entry) => stamp(startedAtMs, entry)),
    correlation: extra.correlation,
    technicalEvents: extra.technicalEvents.map((entry) => stamp(startedAtMs, entry)),
  }
}

function indexById<T extends { id: string }>(items: T[]): Map<string, T> {
  const map = new Map<string, T>()
  for (const item of items) {
    if (map.has(item.id)) throw new Error(`Duplicate fixture id ${item.id}`)
    map.set(item.id, item)
  }
  return map
}

function assertCatalog(): void {
  const extras = indexById(liveDetailExtras)
  for (const call of liveCallFixtures) {
    if (!extras.has(call.id)) throw new Error(`Missing live detail extra for ${call.id}`)
  }
  const known = new Set<string>([...callDetails.map((call) => call.id), ...liveCallFixtures.map((call) => call.id)])
  for (const campaign of campaignFixtures) {
    for (const callId of campaign.relatedCallIds) {
      if (!known.has(callId)) throw new Error(`Campaign ${campaign.id} references missing call ${callId}`)
    }
  }
}

assertCatalog()

const historyById = indexById(callDetails)
const liveById = indexById(liveCallFixtures)
const extrasById = indexById(liveDetailExtras)
const campaignById = indexById(campaignFixtures)

function detailAt(callId: string, nowMs: number): CallDetail | null {
  const history = historyById.get(callId)
  if (history) return history
  const live = liveById.get(callId)
  if (!live) return null
  const extra = extrasById.get(callId)
  if (!extra) throw new Error(`Missing live detail extra for ${callId}`)
  return assembleLiveDetail(live, extra, nowMs)
}

function toCampaignSummary(fixture: CampaignFixture, liveCalls: LiveCall[]): CampaignSummary {
  let lastSeenMs = Date.parse(fixture.lastSeenAt)
  for (const call of liveCalls) {
    if (call.campaignId === fixture.id) lastSeenMs = Math.max(lastSeenMs, Date.parse(call.startedAt))
  }
  return {
    id: fixture.id,
    name: fixture.name,
    status: fixture.status,
    classification: fixture.classification,
    firstSeenAt: fixture.firstSeenAt,
    lastSeenAt: new Date(lastSeenMs).toISOString(),
    callCount: fixture.callCount,
    activeCallCount: liveCalls.filter((call) => call.campaignId === fixture.id).length,
    summary: fixture.summary,
    topIndicators: fixture.sharedIndicators.slice(0, 3),
    activity: fixture.activity,
  }
}

function toCampaignDetail(fixture: CampaignFixture, nowMs: number, liveCalls: LiveCall[]): CampaignDetail {
  const summary = toCampaignSummary(fixture, liveCalls)
  const relatedCalls: CallSummary[] = []
  for (const callId of fixture.relatedCallIds) {
    const detail = detailAt(callId, nowMs)
    if (!detail) throw new Error(`Campaign ${fixture.id} references missing call ${callId}`)
    relatedCalls.push(toCallSummary(detail))
  }
  relatedCalls.sort((left, right) => Date.parse(right.startedAt) - Date.parse(left.startedAt))
  return {
    ...summary,
    timeline: fixture.timeline,
    relatedCalls,
    commonScriptPhrases: fixture.commonScriptPhrases,
    sharedIndicators: fixture.sharedIndicators,
    similarity: fixture.similarity,
  }
}

export const mockOpsDataPort: OpsDataPort = {
  async fetchLiveCalls(): Promise<LiveCall[]> {
    await delay()
    const nowMs = Date.now()
    return liveCallFixtures
      .map((fixture) => assembleLiveCall(fixture, nowMs))
      .sort((left, right) => Date.parse(left.startedAt) - Date.parse(right.startedAt))
  },

  async fetchCallHistory(): Promise<CallSummary[]> {
    await delay()
    return callDetails
      .map((detail) => toCallSummary(detail))
      .sort((left, right) => Date.parse(right.startedAt) - Date.parse(left.startedAt))
  },

  async fetchCallDetail(callId: string): Promise<CallDetail | null> {
    await delay()
    return detailAt(callId, Date.now())
  },

  async fetchCampaigns(): Promise<CampaignSummary[]> {
    await delay()
    const nowMs = Date.now()
    const liveCalls = liveCallFixtures.map((fixture) => assembleLiveCall(fixture, nowMs))
    return campaignFixtures
      .map((fixture) => toCampaignSummary(fixture, liveCalls))
      .sort((left, right) => Date.parse(right.lastSeenAt) - Date.parse(left.lastSeenAt))
  },

  async fetchCampaignDetail(campaignId: string): Promise<CampaignDetail | null> {
    await delay()
    const fixture = campaignById.get(campaignId)
    if (!fixture) return null
    const nowMs = Date.now()
    const liveCalls = liveCallFixtures.map((item) => assembleLiveCall(item, nowMs))
    return toCampaignDetail(fixture, nowMs, liveCalls)
  },

  async fetchSystemHealth(): Promise<SystemHealth> {
    await delay()
    return systemHealthFixture
  },
}
