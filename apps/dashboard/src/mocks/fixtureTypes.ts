import type { CallDetail, CampaignGaps, Campaign } from '@/types/models'

/** Live rows store a call whose timestamps are relative to the Unix epoch. The adapter shifts them. */
export interface LiveFixture {
  started_offset_sec: number
  engagement_delay_ms: number
  call: CallDetail
}

export interface CampaignFixture {
  campaign: Campaign
  gaps: Omit<CampaignGaps, 'active_call_count'>
}
