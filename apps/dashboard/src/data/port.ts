import type { CallDetail, CallSummary, CampaignDetail, CampaignSummary, LiveCall, SystemHealth } from '@/types/models'

/**
 * The only data surface stores are allowed to use.
 * A future HTTP or WebSocket adapter should implement this interface and
 * replace the binding in src/data/client.ts.
 */
export interface OpsDataPort {
  fetchLiveCalls(): Promise<LiveCall[]>
  fetchCallHistory(): Promise<CallSummary[]>
  fetchCallDetail(callId: string): Promise<CallDetail | null>
  fetchCampaigns(): Promise<CampaignSummary[]>
  fetchCampaignDetail(campaignId: string): Promise<CampaignDetail | null>
  fetchSystemHealth(): Promise<SystemHealth>
}
