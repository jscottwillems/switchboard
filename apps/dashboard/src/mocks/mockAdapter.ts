import type { OpsDataPort } from '@/data/port'
import { primaryFilename } from '@/lib/reports'
import type { CampaignFixture, LiveFixture } from '@/mocks/fixtureTypes'
import { callDetails, campaignFixtures, liveFixtures, systemHealthFixture } from '@/mocks/fixtures'
import { reportCatalog } from '@/mocks/reportFixtures'
import type { OpenReportRequest, OpenReportResult, ReportIndexEntry } from '@/types/reports'
import type {
  CallDetail,
  CallSummary,
  CampaignDetail,
  CampaignSummary,
  IntelligenceFinding,
  LiveCall,
} from '@/types/models'

const RESPONSE_DELAY_MS = 40

function delay(): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, RESPONSE_DELAY_MS)
  })
}

function shiftIso(value: string, deltaMs: number): string {
  return new Date(Date.parse(value) + deltaMs).toISOString()
}

function shiftNullable(value: string | null, deltaMs: number): string | null {
  if (value === null) return null
  return shiftIso(value, deltaMs)
}

function materializeLive(fixture: LiveFixture, nowMs: number): CallDetail {
  const targetStart = nowMs + fixture.started_offset_sec * 1000
  const delta = targetStart - Date.parse(fixture.call.session.started_at)
  const durationMs = Math.max(0, nowMs - targetStart)
  const call = fixture.call
  return {
    session: {
      ...call.session,
      state: 'in_progress',
      started_at: shiftIso(call.session.started_at, delta),
      answered_at: shiftNullable(call.session.answered_at, delta),
      ended_at: null,
      end_reason: null,
    },
    media_streams: call.media_streams.map((stream) => ({
      ...stream,
      state: 'streaming',
      started_at: shiftIso(stream.started_at, delta),
      ended_at: null,
    })),
    transcript: call.transcript.map((segment) => ({
      ...segment,
      created_at: shiftIso(segment.created_at, delta),
    })),
    turns: call.turns.map((turn) => ({
      ...turn,
      created_at: shiftIso(turn.created_at, delta),
    })),
    findings: call.findings.map((finding) => ({
      ...finding,
      created_at: shiftIso(finding.created_at, delta),
    })),
    attributions: call.attributions.map((row) => ({
      ...row,
      created_at: shiftIso(row.created_at, delta),
    })),
    events: call.events.map((event) => ({
      ...event,
      occurred_at: shiftIso(event.occurred_at, delta),
    })),
    gaps: {
      ...call.gaps,
      duration_ms: durationMs,
      engagement_duration_ms: Math.max(0, durationMs - fixture.engagement_delay_ms),
      pipeline: {
        ...call.gaps.pipeline,
        sampled_at: new Date(nowMs).toISOString(),
      },
      timeline: call.gaps.timeline.map((entry) => ({ ...entry, at: shiftIso(entry.at, delta) })),
      state_transitions: call.gaps.state_transitions.map((entry) => ({ ...entry, at: shiftIso(entry.at, delta) })),
      paired_reads: call.gaps.paired_reads.map((entry) => ({ ...entry, at: shiftIso(entry.at, delta) })),
    },
  }
}

function keyFindings(call: CallDetail): IntelligenceFinding[] {
  const wanted = new Set(call.gaps.key_finding_ids)
  return call.findings.filter((finding) => wanted.has(finding.id))
}

function toCallSummary(call: CallDetail): CallSummary {
  return {
    session: call.session,
    gaps: {
      conversation_state: call.gaps.conversation_state,
      conversation_state_record_layer: call.gaps.conversation_state_record_layer,
      classification: call.gaps.classification,
      engagement_duration_ms: call.gaps.engagement_duration_ms,
      duration_ms: call.gaps.duration_ms,
      campaign_id: call.gaps.campaign_id,
      campaign_label: call.gaps.campaign_label,
    },
    key_findings: keyFindings(call),
  }
}

function toLiveCall(call: CallDetail): LiveCall {
  return {
    session: call.session,
    transcript: call.transcript,
    findings: call.findings,
    gaps: {
      conversation_state: call.gaps.conversation_state,
      conversation_state_record_layer: call.gaps.conversation_state_record_layer,
      classification: call.gaps.classification,
      campaign_id: call.gaps.campaign_id,
      campaign_label: call.gaps.campaign_label,
      pipeline: call.gaps.pipeline,
    },
  }
}

function indexById<T extends { id: string }>(items: T[], label: string): Map<string, T> {
  const map = new Map<string, T>()
  for (const item of items) {
    if (map.has(item.id)) throw new Error(`Duplicate ${label} id ${item.id}`)
    map.set(item.id, item)
  }
  return map
}

function assertCatalog(): void {
  const known = new Set<string>([
    ...callDetails.map((call) => call.session.id),
    ...liveFixtures.map((fixture) => fixture.call.session.id),
  ])
  for (const campaign of campaignFixtures) {
    for (const callId of campaign.gaps.related_call_ids) {
      if (!known.has(callId)) {
        throw new Error(`Campaign ${campaign.campaign.id} references missing call ${callId}`)
      }
    }
  }
}

assertCatalog()

const historyCalls = indexById(
  callDetails.map((call) => ({ ...call, id: call.session.id })),
  'history',
)
const liveById = indexById(
  liveFixtures.map((fixture) => ({ ...fixture, id: fixture.call.session.id })),
  'live',
)
const campaignById = indexById(
  campaignFixtures.map((fixture) => ({ ...fixture, id: fixture.campaign.id })),
  'campaign',
)

function detailAt(callId: string, nowMs: number): CallDetail | null {
  const history = historyCalls.get(callId)
  if (history) return history
  const live = liveById.get(callId)
  if (!live) return null
  return materializeLive(live, nowMs)
}

function liveCallsAt(nowMs: number): LiveCall[] {
  return liveFixtures
    .map((fixture) => toLiveCall(materializeLive(fixture, nowMs)))
    .sort((left, right) => Date.parse(left.session.started_at) - Date.parse(right.session.started_at))
}

function toCampaignSummary(fixture: CampaignFixture, liveCalls: LiveCall[]): CampaignSummary {
  let updatedMs = Date.parse(fixture.campaign.updated_at)
  for (const call of liveCalls) {
    if (call.gaps.campaign_id === fixture.campaign.id) {
      updatedMs = Math.max(updatedMs, Date.parse(call.session.started_at))
    }
  }
  return {
    campaign: {
      ...fixture.campaign,
      updated_at: new Date(updatedMs).toISOString(),
    },
    gaps: {
      classification: fixture.gaps.classification,
      call_count: fixture.gaps.call_count,
      active_call_count: liveCalls.filter((call) => call.gaps.campaign_id === fixture.campaign.id).length,
      activity: fixture.gaps.activity,
      shared_indicators: fixture.gaps.shared_indicators.slice(0, 3),
    },
  }
}

function toCampaignDetail(fixture: CampaignFixture, nowMs: number, liveCalls: LiveCall[]): CampaignDetail {
  const summary = toCampaignSummary(fixture, liveCalls)
  const related = fixture.gaps.related_call_ids.map((callId) => {
    const detail = detailAt(callId, nowMs)
    if (!detail) throw new Error(`Campaign ${fixture.campaign.id} references missing call ${callId}`)
    return toCallSummary(detail)
  })
  related.sort((left, right) => Date.parse(right.session.started_at) - Date.parse(left.session.started_at))
  return {
    campaign: summary.campaign,
    gaps: {
      ...fixture.gaps,
      active_call_count: summary.gaps.active_call_count,
    },
    related_calls: related,
  }
}

export const mockOpsDataPort: OpsDataPort = {
  async fetchLiveCalls(): Promise<LiveCall[]> {
    await delay()
    return liveCallsAt(Date.now())
  },

  async fetchCallHistory(): Promise<CallSummary[]> {
    await delay()
    return callDetails
      .map((call) => toCallSummary(call))
      .sort((left, right) => Date.parse(right.session.started_at) - Date.parse(left.session.started_at))
  },

  async fetchCallDetail(callId: string): Promise<CallDetail | null> {
    await delay()
    return detailAt(callId, Date.now())
  },

  async fetchCampaigns(): Promise<CampaignSummary[]> {
    await delay()
    const liveCalls = liveCallsAt(Date.now())
    return campaignFixtures
      .map((fixture) => toCampaignSummary(fixture, liveCalls))
      .sort((left, right) => Date.parse(right.campaign.updated_at) - Date.parse(left.campaign.updated_at))
  },

  async fetchCampaignDetail(campaignId: string): Promise<CampaignDetail | null> {
    await delay()
    const nowMs = Date.now()
    const fixture = campaignById.get(campaignId)
    if (!fixture) return null
    return toCampaignDetail(fixture, nowMs, liveCallsAt(nowMs))
  },

  async fetchSystemHealth() {
    await delay()
    return {
      ...systemHealthFixture,
      sampled_at: new Date().toISOString(),
      concurrency: {
        ...systemHealthFixture.concurrency,
        active_calls: liveFixtures.length,
      },
    }
  },

  async fetchReportIndex(): Promise<ReportIndexEntry[]> {
    await delay()
    return reportCatalog.index.map((entry) => ({ ...entry, available_formats: [...entry.available_formats] }))
  },

  async openReport(request: OpenReportRequest): Promise<OpenReportResult> {
    await delay()
    const entry = reportCatalog.index.find((item) => item.report_id === request.report_id)
    if (!entry) return { status: 'not_found', reportId: request.report_id }
    if (!entry.available_formats.includes(request.format)) {
      return { status: 'format_unavailable', reportId: request.report_id, format: request.format }
    }
    const render = reportCatalog.renders.find(
      (item) => item.report_id === request.report_id && item.format === request.format,
    )
    if (!render) return { status: 'format_unavailable', reportId: request.report_id, format: request.format }
    return {
      status: 'opened',
      report: {
        report_id: entry.report_id,
        package_id: entry.package_id,
        package_ids: [...entry.package_ids],
        kind: entry.kind,
        format: request.format,
        synthetic: entry.synthetic,
        primary_filename: primaryFilename(entry.report_id, request.format),
        parts: render.parts.map((part) => ({ ...part })),
      },
    }
  },
}
