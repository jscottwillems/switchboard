import type { CallDetail, CallSummary, CampaignDetail, CampaignSummary, LiveCall, SystemHealth } from '@/types/models'
import type { OpenReportRequest, OpenReportResult, ReportIndexEntry } from '@/types/reports'

/**
 * The only data surface stores are allowed to use.
 * Replace the binding in src/data/client.ts with an HTTP adapter.
 * Call and campaign methods should then return the read models in docs/API_CONTRACTS.md.
 * Gap fields documented in docs/FRONTEND_DATA_REQUIREMENTS.md have no route yet.
 */
export interface OpsDataPort {
  /** Live board. No GET /v1/live in 0.1.0. Mock filters in-progress sessions. */
  fetchLiveCalls(): Promise<LiveCall[]>
  /** Stand-in for GET /v1/calls. Includes gap fields the list columns need. */
  fetchCallHistory(): Promise<CallSummary[]>
  /** Stand-in for GET /v1/calls/{id}. Null stands in for 404 call_not_found. */
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
