import campaignDetailsJson from './campaign-details.json'
import callDetailsJson from './call-details.json'
import liveCallsJson from './live-calls.json'
import liveExtrasJson from './live-detail-extras.json'
import { parseCallDetails, parseCampaigns, parseLiveCalls, parseLiveExtras, parseSystemHealth } from './parse'
import systemHealthJson from './system-health.json'

export const callDetails = parseCallDetails(callDetailsJson)
export const liveCallFixtures = parseLiveCalls(liveCallsJson)
export const liveDetailExtras = parseLiveExtras(liveExtrasJson)
export const campaignFixtures = parseCampaigns(campaignDetailsJson)
export const systemHealthFixture = parseSystemHealth(systemHealthJson)
