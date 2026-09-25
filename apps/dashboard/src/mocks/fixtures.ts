import campaignDetailsJson from './campaign-details.json'
import callDetailsJson from './call-details.json'
import liveCallsJson from './live-calls.json'
import { parseCallDetails, parseCampaigns, parseLiveFixtures, parseSystemHealth } from './parse'
import systemHealthJson from './system-health.json'

export const callDetails = parseCallDetails(callDetailsJson)
export const liveFixtures = parseLiveFixtures(liveCallsJson)
export const campaignFixtures = parseCampaigns(campaignDetailsJson)
export const systemHealthFixture = parseSystemHealth(systemHealthJson)
