import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..', 'src', 'mocks')

const layers = new Set(['observation', 'interpretation', 'attribution'])
const callStates = new Set(['ringing', 'in_progress', 'completed', 'failed'])
const campaignStatuses = new Set(['hypothesized', 'corroborated', 'closed'])
const findingKinds = new Set([
  'callback_number',
  'pretext',
  'organization_name',
  'payment_method',
  'url',
  'person_name',
  'other',
])
const findingStatuses = new Set(['proposed', 'accepted', 'rejected'])
const speakers = new Set(['caller', 'honeypot'])
const sources = new Set(['stt', 'tts_input'])
const eventTypes = new Set([
  'telephony.call.received',
  'telephony.call.answered',
  'telephony.call.completed',
  'telephony.call.failed',
  'media.stream.started',
  'media.stream.stopped',
  'media.stream.failed',
  'speech.segment.partial',
  'speech.segment.final',
  'speech.synthesis.requested',
  'speech.synthesis.completed',
  'speech.synthesis.failed',
  'conversation.response.selected',
  'conversation.turn.recorded',
  'intelligence.finding.proposed',
  'campaign.opened',
  'campaign.attribution.proposed',
])
const producers = new Set(['api', 'media_gateway', 'intelligence'])
const dialogue = new Set([
  'ringing',
  'greeting',
  'identity_probe',
  'pretext',
  'urgency',
  'payment_request',
  'compliance_stall',
  'extraction',
  'closing',
  'ended',
])
const uuidRe = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/

function load(name) {
  return JSON.parse(readFileSync(join(root, name), 'utf8'))
}

function fail(message) {
  throw new Error(message)
}

function expectEnum(value, allowed, ctx) {
  if (!allowed.has(value)) fail(`${ctx}: unexpected ${JSON.stringify(value)}`)
}

function expectScore(value, ctx) {
  if (typeof value !== 'number' || value < 0 || value > 1) fail(`${ctx}: score out of range`)
}

function expectUuid(value, ctx) {
  if (typeof value !== 'string' || !uuidRe.test(value)) fail(`${ctx}: expected uuid, got ${value}`)
}

const history = load('call-details.json')
const live = load('live-calls.json')
const campaigns = load('campaign-details.json')
const system = load('system-health.json')

if (!Array.isArray(history) || history.length < 8) fail('expected at least 8 history calls')
if (!Array.isArray(live) || live.length < 3) fail('expected at least 3 live calls')
if (!Array.isArray(campaigns) || campaigns.length < 2) fail('expected at least 2 campaigns')

const seenLayers = new Set()
const seenEvents = new Set()
const historyIds = new Set()

function checkFinding(item, ctx, segmentIds) {
  expectEnum(item.record_layer, layers, `${ctx} layer`)
  if (item.record_layer !== 'interpretation') fail(`${ctx}: findings are interpretations`)
  expectEnum(item.kind, findingKinds, `${ctx} kind`)
  expectEnum(item.status, findingStatuses, `${ctx} status`)
  expectScore(item.confidence, ctx)
  if (!Array.isArray(item.transcript_segment_ids) || item.transcript_segment_ids.length === 0) {
    fail(`${ctx}: transcript_segment_ids`)
  }
  for (const segmentId of item.transcript_segment_ids) {
    if (!segmentIds.has(segmentId)) fail(`${ctx}: missing segment ${segmentId}`)
  }
  seenLayers.add(item.record_layer)
}

function checkCall(call, ctx) {
  const session = call.session
  expectUuid(session.id, ctx)
  expectEnum(session.record_layer, layers, `${ctx} session layer`)
  expectEnum(session.state, callStates, `${ctx} state`)
  if (!session.caller_number_e164?.startsWith('+')) fail(`${ctx}: caller_number_e164`)
  if (session.called_number_e164 !== '+15550001001') fail(`${ctx}: called number`)
  if (session.carrier !== 'mock') fail(`${ctx}: carrier`)
  seenLayers.add(session.record_layer)
  const segmentIds = new Set()
  for (const segment of call.transcript) {
    expectEnum(segment.record_layer, layers, segment.id)
    if (segment.record_layer !== 'observation') fail(`${segment.id}: transcript layer`)
    expectEnum(segment.speaker, speakers, segment.id)
    expectEnum(segment.source, sources, segment.id)
    if (segment.speaker === 'honeypot' && segment.stt_confidence !== null) fail(`${segment.id}: tts stt_confidence`)
    if (segment.speaker === 'caller') expectScore(segment.stt_confidence, segment.id)
    segmentIds.add(segment.id)
    seenLayers.add('observation')
  }
  for (const turn of call.turns) {
    if (turn.record_layer !== 'interpretation') fail(`${turn.id}: turn layer`)
    expectScore(turn.confidence, turn.id)
    seenLayers.add('interpretation')
  }
  const findingIds = new Set()
  for (const item of call.findings) {
    checkFinding(item, item.id, segmentIds)
    findingIds.add(item.id)
  }
  for (const id of call.gaps.key_finding_ids) {
    if (!findingIds.has(id)) fail(`${ctx}: key finding ${id} missing`)
  }
  for (const row of call.attributions) {
    if (row.record_layer !== 'attribution') fail(`${row.id}: attribution layer`)
    expectScore(row.confidence, row.id)
    if (!row.supporting_finding_ids?.length) fail(`${row.id}: supporting findings`)
    for (const findingId of row.supporting_finding_ids) {
      if (!findingIds.has(findingId)) fail(`${row.id}: missing finding ${findingId}`)
    }
    seenLayers.add('attribution')
  }
  if (call.gaps.campaign_id && call.attributions.length === 0) fail(`${ctx}: campaign without attribution`)
  if (!call.gaps.campaign_id && call.attributions.length !== 0) fail(`${ctx}: attribution without campaign`)
  expectEnum(call.gaps.conversation_state, dialogue, ctx)
  expectEnum(call.gaps.conversation_state_record_layer, layers, ctx)
  let previous = null
  for (const transition of call.gaps.state_transitions) {
    if (transition.from !== previous) fail(`${ctx}: broken dialogue chain`)
    expectEnum(transition.to, dialogue, transition.id)
    expectEnum(transition.record_layer, layers, transition.id)
    previous = transition.to
  }
  const last = call.gaps.state_transitions.at(-1)
  if (!last || last.to !== call.gaps.conversation_state) fail(`${ctx}: dialogue does not match last transition`)
  if (last.record_layer !== call.gaps.conversation_state_record_layer) fail(`${ctx}: dialogue layer`)
  for (const event of call.events) {
    expectEnum(event.event_type, eventTypes, event.event_id)
    expectEnum(event.producer, producers, event.event_id)
    if (event.event_version !== 1) fail(`${event.event_id}: event_version`)
    if (event.call_session_id !== session.id) fail(`${event.event_id}: call_session_id`)
    seenEvents.add(event.event_type)
  }
  for (const read of call.gaps.paired_reads) {
    if (read.raw.record_layer !== 'observation') fail(`${read.id}: raw layer`)
    if (read.interpretation && read.interpretation.record_layer !== 'interpretation') fail(`${read.id}: interpretation layer`)
  }
}

for (const call of history) {
  if (historyIds.has(call.session.id)) fail(`duplicate history id ${call.session.id}`)
  historyIds.add(call.session.id)
  if (call.session.state === 'in_progress' || call.session.state === 'ringing' || call.session.ended_at === null) {
    fail(`${call.session.external_call_id}: history call should be finished`)
  }
  checkCall(call, call.session.external_call_id)
  const started = Date.parse(call.session.started_at)
  const ended = Date.parse(call.session.ended_at)
  if (ended - started !== call.gaps.duration_ms) fail(`${call.session.external_call_id}: duration mismatch`)
  if (call.gaps.engagement_duration_ms > call.gaps.duration_ms) fail(`${call.session.external_call_id}: engagement`)
}

const liveIds = new Set()
for (const fixture of live) {
  const id = fixture.call.session.id
  if (liveIds.has(id)) fail(`duplicate live id ${id}`)
  liveIds.add(id)
  if (fixture.started_offset_sec >= 0) fail(`${id}: live offset should be in the past`)
  if (fixture.call.session.state !== 'in_progress') fail(`${id}: live state`)
  checkCall(fixture.call, fixture.call.session.external_call_id)
}

for (const layer of layers) {
  if (!seenLayers.has(layer)) fail(`fixtures never use record_layer ${layer}`)
}
for (const required of ['telephony.call.answered', 'telephony.call.completed', 'speech.segment.final', 'conversation.response.selected']) {
  if (!seenEvents.has(required)) fail(`fixtures never emit ${required}`)
}

const knownCalls = new Set([...historyIds, ...liveIds])
for (const item of campaigns) {
  const campaign = item.campaign
  expectUuid(campaign.id, campaign.label)
  expectEnum(campaign.record_layer, layers, campaign.id)
  if (campaign.record_layer !== 'attribution') fail(`${campaign.id}: campaign layer`)
  expectEnum(campaign.status, campaignStatuses, campaign.id)
  const activitySum = item.gaps.activity.reduce((total, bucket) => total + bucket.count, 0)
  if (activitySum !== item.gaps.call_count) fail(`${campaign.id}: activity sum ${activitySum} != call_count`)
  for (const callId of item.gaps.related_call_ids) {
    if (!knownCalls.has(callId)) fail(`${campaign.id} missing related call ${callId}`)
  }
  const related = new Set(item.gaps.related_call_ids)
  for (const similarity of item.gaps.similarity) {
    if (!related.has(similarity.call_id)) fail(`${campaign.id}: similarity ${similarity.external_call_id} is not linked`)
    expectScore(similarity.score, similarity.call_id)
    expectEnum(similarity.record_layer, layers, similarity.call_id)
  }
  if (item.gaps.timeline[0]?.event_type !== 'campaign.opened') fail(`${campaign.id}: timeline should open with campaign.opened`)
  for (const entry of item.gaps.timeline.slice(1)) {
    if (entry.event_type !== 'campaign.attribution.proposed') fail(`${entry.id}: expected campaign.attribution.proposed`)
  }
}

const services = new Set(['api', 'media_gateway', 'intelligence', 'dashboard'])
if (!Array.isArray(system.services) || system.services.length !== 4) fail('system services')
for (const service of system.services) {
  expectEnum(service.service, services, 'service')
  if (service.status !== 'ok') fail(`${service.service}: HealthResponse status`)
}
if (system.concurrency.active_calls !== live.length) fail('active_calls should match the live fixture count')
for (const provider of system.providers) {
  expectEnum(provider.role, new Set(['telephony', 'stt', 'tts', 'selector']), provider.id)
  expectEnum(provider.status, new Set(['ok', 'degraded', 'down']), provider.id)
}
if (typeof system.latency.select_ms !== 'number') fail('latency.select_ms')

const catalog = load('report-catalog.json')
const reportFormats = new Set(['json', 'markdown', 'pdf_ready', 'csv', 'campaign_summary'])
const reportKinds = new Set(['single_call', 'multi_call_campaign', 'technical_incident', 'machine_readable_json'])
const factClasses = new Set([
  'reported_caller_metadata',
  'spoken_identifier',
  'raw_observation',
  'confirmed_observation',
  'derived_interpretation',
  'derived_association',
])
const requiredReports = [
  'syn-pkg-call-001__single_call',
  'syn-pkg-campaign-001__multi_call_campaign',
  'syn-pkg-incident-001__technical_incident',
  'syn-export-synthetic-001__machine_readable_json',
]
if (!catalog || !Array.isArray(catalog.index) || !Array.isArray(catalog.renders)) fail('report catalog shape')
const reportIds = new Set(catalog.index.map((entry) => entry.report_id))
for (const reportId of requiredReports) {
  if (!reportIds.has(reportId)) fail(`missing report ${reportId}`)
}
function primaryName(reportId, format) {
  if (format === 'json') return `${reportId}.json`
  if (format === 'markdown') return `${reportId}.md`
  if (format === 'pdf_ready') return `${reportId}.html`
  if (format === 'csv') return 'calls.csv'
  if (format === 'campaign_summary') return `${reportId}.campaign_summary.json`
  fail(`unknown format ${format}`)
}
const seenFacts = new Set()
for (const entry of catalog.index) {
  expectEnum(entry.kind, reportKinds, entry.report_id)
  if (!Array.isArray(entry.available_formats) || entry.available_formats.length === 0) fail(`${entry.report_id} formats`)
  if (entry.kind === 'machine_readable_json') {
    if (entry.available_formats.length !== 1 || entry.available_formats[0] !== 'json') {
      fail(`${entry.report_id} must offer json only`)
    }
  } else {
    for (const format of reportFormats) {
      if (!entry.available_formats.includes(format)) fail(`${entry.report_id} missing ${format}`)
    }
  }
  for (const format of entry.available_formats) {
    expectEnum(format, reportFormats, entry.report_id)
    const render = catalog.renders.find((item) => item.report_id === entry.report_id && item.format === format)
    if (!render) fail(`missing render ${entry.report_id} ${format}`)
    const names = render.parts.map((part) => part.filename)
    if (new Set(names).size !== names.length) fail(`${entry.report_id} ${format} duplicate filename`)
    const primary = primaryName(entry.report_id, format)
    if (!names.includes(primary)) fail(`${entry.report_id} ${format} missing ${primary}`)
    if (format !== 'csv' && render.parts.length !== 1) fail(`${entry.report_id} ${format} should have one part`)
    for (const part of render.parts) {
      if (!part.body || !part.content_type) fail(`${part.filename} empty part`)
      if (!String(part.content_type).includes('json')) continue
      const parsed = JSON.parse(part.body)
      const stack = [parsed]
      while (stack.length) {
        const current = stack.pop()
        if (!current || typeof current !== 'object') continue
        if (Array.isArray(current)) {
          stack.push(...current)
          continue
        }
        if (typeof current.fact_class === 'string') seenFacts.add(current.fact_class)
        stack.push(...Object.values(current))
      }
    }
  }
}
for (const factClass of factClasses) {
  if (!seenFacts.has(factClass)) fail(`report JSON never uses fact class ${factClass}`)
}

console.log(`fixtures ok: ${history.length} history, ${live.length} live, ${campaigns.length} campaigns, ${catalog.index.length} reports`)
