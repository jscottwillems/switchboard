import type { OpsDataPort } from '@/data/port'
import { detailFromResponse, liveFromDetail, summaryFromListItem } from '@/data/mapCall'
import { getCallDetail, listCallSummaries } from '@/data/readApi'
import type { CallState } from '@switchboard/schemas'
import { assertNever } from '@/lib/assertNever'
import type { CallDetail, CallSummary, LiveCall } from '@/types/models'

const DETAIL_CONCURRENCY = 6

function isInProgress(state: CallState): boolean {
  switch (state) {
    case 'in_progress':
      return true
    case 'ringing':
    case 'completed':
    case 'failed':
      return false
    default:
      return assertNever(state)
  }
}

async function mapLimited<T, R>(items: readonly T[], limit: number, mapItem: (item: T) => Promise<R>): Promise<R[]> {
  if (items.length === 0) return []
  const results: Array<R | undefined> = new Array(items.length)
  let next = 0
  async function worker(): Promise<void> {
    while (next < items.length) {
      const index = next
      next += 1
      const item = items[index]
      if (item === undefined) return
      results[index] = await mapItem(item)
    }
  }
  const workers = Array.from({ length: Math.min(limit, items.length) }, () => worker())
  await Promise.all(workers)
  return results.filter((item): item is R => item !== undefined)
}

/**
 * Call list, live board, and call detail use the read API.
 * Campaigns, system health, and reports stay on the mock port.
 */
export function createHttpOpsDataPort(mock: OpsDataPort): OpsDataPort {
  return {
    async fetchLiveCalls(): Promise<LiveCall[]> {
      const summaries = await listCallSummaries()
      const live = summaries.filter((item) => isInProgress(item.state))
      const details = await mapLimited(live, DETAIL_CONCURRENCY, async (item) => {
        const body = await getCallDetail(item.id)
        if (!body || !isInProgress(body.session.state)) return null
        return liveFromDetail(detailFromResponse(body, Date.now()))
      })
      return details
        .filter((item): item is LiveCall => item !== null)
        .sort((left, right) => Date.parse(left.session.started_at) - Date.parse(right.session.started_at))
    },

    async fetchCallHistory(): Promise<CallSummary[]> {
      const nowMs = Date.now()
      const summaries = await listCallSummaries()
      return summaries.map((item) => summaryFromListItem(item, nowMs))
    },

    async fetchCallDetail(callId: string): Promise<CallDetail | null> {
      const body = await getCallDetail(callId)
      if (!body) return null
      return detailFromResponse(body, Date.now())
    },

    fetchCampaigns: () => mock.fetchCampaigns(),
    fetchCampaignDetail: (campaignId: string) => mock.fetchCampaignDetail(campaignId),
    fetchSystemHealth: () => mock.fetchSystemHealth(),
    fetchReportIndex: () => mock.fetchReportIndex(),
    openReport: (request) => mock.openReport(request),
  }
}
