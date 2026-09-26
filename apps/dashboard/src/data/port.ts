import type { CallDetail, CallSummary, CampaignDetail, CampaignSummary, LiveCall, SystemHealth } from '@/types/models'
import type { OpenReportRequest, OpenReportResult, ReportIndexEntry } from '@/types/reports'

/**
 * The only data surface stores are allowed to use.
 * `src/data/client.ts` binds this port to the HTTP read API or the mock adapter.
 * Call methods follow docs/API_CONTRACTS.md. Gap fields stay off the wire.
 */
export interface OpsDataPort {
  /** In-progress rows from GET /v1/calls, with detail for transcript and findings. */
  fetchLiveCalls(): Promise<LiveCall[]>
  /** GET /v1/calls. Summary rows omit fields that are only on the detail session. */
  fetchCallHistory(): Promise<CallSummary[]>
  /** GET /v1/calls/{id}. Null stands in for 404 call_not_found. */
  fetchCallDetail(callId: string): Promise<CallDetail | null>
  /** Stand-in for GET /v1/campaigns. */
  fetchCampaigns(): Promise<CampaignSummary[]>
  /** Stand-in for GET /v1/campaigns/{id} plus gap fields. Null stands in for 404 campaign_not_found. */
  fetchCampaignDetail(campaignId: string): Promise<CampaignDetail | null>
  /** Process rows follow HealthResponse. The rest of the page is a gap. */
  fetchSystemHealth(): Promise<SystemHealth>
  /** Not in API_CONTRACTS. Mock of a future CLERK report index. */
  fetchReportIndex(): Promise<ReportIndexEntry[]>
  /** Not in API_CONTRACTS. Mock of opening a CLERK report. */
  openReport(request: OpenReportRequest): Promise<OpenReportResult>
}
