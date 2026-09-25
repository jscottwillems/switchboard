import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..', 'src', 'mocks')

const provenance = new Set(['observed', 'inferred', 'unverified'])
const basis = new Set(['raw', 'derived'])
const classifications = new Set([
  'irs_impersonation',
  'tech_support',
  'bank_fraud',
  'romance',
  'utility_shutoff',
  'unknown',
])
const states = new Set([
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
const callStatuses = new Set(['active', 'completed', 'abandoned', 'error'])
const kinds = new Set(['indicator', 'entity', 'script_phrase', 'tactic', 'amount', 'callback'])
const categories = new Set(['payment', 'identity', 'threat', 'tooling', 'script', 'callback', 'other'])
const speakers = new Set(['caller', 'honeypot'])
const timelineKinds = new Set(['telephony', 'state', 'intel', 'transcript', 'error'])
const sources = new Set(['telephony', 'stt', 'tts', 'llm', 'orchestrator'])
const severities = new Set(['info', 'warn', 'error'])

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
  if (typeof value !== 'number' || value < 0 || value > 1) fail(`${ctx}: score/confidence out of range`)
}

function checkIntelligence(item, ctx, turnIds) {
  if (!item || typeof item.id !== 'string') fail(`${ctx}: intelligence missing id`)
  expectEnum(item.kind, kinds, `${ctx} kind`)
  expectEnum(item.provenance, provenance, `${ctx} provenance`)
  expectEnum(item.basis, basis, `${ctx} basis`)
  if (typeof item.label !== 'string' || typeof item.value !== 'string') fail(`${ctx}: label/value`)
  if (item.confidence !== null) expectScore(item.confidence, ctx)
  if (!Array.isArray(item.evidenceTurnIds)) fail(`${ctx}: evidenceTurnIds`)
  for (const turnId of item.evidenceTurnIds) {
    if (turnIds && !turnIds.has(turnId)) fail(`${ctx}: evidence turn ${turnId} missing`)
  }
}

function checkClassification(value, ctx) {
  expectEnum(value?.label, classifications, `${ctx} classification`)
  expectEnum(value?.provenance, provenance, `${ctx} classification provenance`)
  if (value.confidence !== null) expectScore(value.confidence, `${ctx} classification`)
}

const history = load('call-details.json')
const live = load('live-calls.json')
const extras = load('live-detail-extras.json')
const campaigns = load('campaign-details.json')
const system = load('system-health.json')

if (!Array.isArray(history) || history.length < 8) fail('expected at least 8 history calls')
if (!Array.isArray(live) || live.length < 3) fail('expected at least 3 live calls')
if (!Array.isArray(campaigns) || campaigns.length < 2) fail('expected at least 2 campaigns')

const seenProvenance = new Set()
const seenBasis = new Set()
const historyIds = new Set()

for (const call of history) {
  if (historyIds.has(call.id)) fail(`duplicate history id ${call.id}`)
  historyIds.add(call.id)
  if (call.status === 'active' || call.endedAt === null) fail(`${call.id}: history call should be finished`)
  expectEnum(call.status, callStatuses, call.id)
  expectEnum(call.conversationState, states, call.id)
  expectEnum(call.stateProvenance, provenance, call.id)
  checkClassification(call.classification, call.id)
  if (call.engagementDurationMs > call.durationMs) fail(`${call.id}: engagement > duration`)
  const started = Date.parse(call.startedAt)
  const ended = Date.parse(call.endedAt)
  if (ended - started !== call.durationMs) fail(`${call.id}: duration does not match timestamps`)
  const turnIds = new Set(call.transcript.map((turn) => turn.id))
  for (const turn of call.transcript) {
    expectEnum(turn.speaker, speakers, turn.id)
    expectEnum(turn.provenance, provenance, turn.id)
    seenProvenance.add(turn.provenance)
    if (turn.offsetMs > call.durationMs) fail(`${turn.id}: past end of call`)
  }
  let previous = null
  for (const transition of call.stateTransitions) {
    if (transition.from !== previous) fail(`${call.id}: broken transition chain`)
    expectEnum(transition.to, states, transition.id)
    expectEnum(transition.provenance, provenance, transition.id)
    seenProvenance.add(transition.provenance)
    previous = transition.to
  }
  const last = call.stateTransitions[call.stateTransitions.length - 1]
  if (!last || last.to !== call.conversationState || last.provenance !== call.stateProvenance) {
    fail(`${call.id}: committed state does not match the last transition`)
  }
  const intelIds = new Set()
  for (const item of call.intelligence) {
    checkIntelligence(item, item.id, turnIds)
    intelIds.add(item.id)
    seenProvenance.add(item.provenance)
    seenBasis.add(item.basis)
  }
  for (const item of call.keyIndicators) {
    if (!intelIds.has(item.id)) fail(`${call.id}: key indicator ${item.id} is not in intelligence`)
  }
  for (const observation of call.observations) {
    expectEnum(observation.category, categories, observation.id)
    expectEnum(observation.raw?.provenance, provenance, `${observation.id} raw`)
    seenProvenance.add(observation.raw.provenance)
    if (observation.interpretation) {
      expectEnum(observation.interpretation.provenance, provenance, `${observation.id} interpretation`)
      seenProvenance.add(observation.interpretation.provenance)
    }
  }
  for (const entry of call.timeline) expectEnum(entry.kind, timelineKinds, entry.id)
  for (const event of call.technicalEvents) {
    expectEnum(event.source, sources, event.id)
    expectEnum(event.severity, severities, event.id)
  }
  for (const reason of call.correlation) {
    expectEnum(reason.provenance, provenance, reason.id)
    expectScore(reason.score, reason.id)
    for (const match of reason.matchedOn) expectEnum(match.provenance, provenance, reason.id)
  }
}

const liveIds = new Set(live.map((call) => call.id))
const extraIds = new Set(extras.map((extra) => extra.id))
if (liveIds.size !== live.length) fail('duplicate live id')
for (const id of liveIds) {
  if (!extraIds.has(id)) fail(`missing live extra ${id}`)
}
for (const call of live) {
  if (call.startedOffsetSec >= 0) fail(`${call.id}: live offset should be in the past`)
  checkClassification(call.classification, call.id)
  expectEnum(call.conversationState, states, call.id)
  const turnIds = new Set(call.transcript.map((turn) => turn.id))
  for (const item of call.intelligence) {
    checkIntelligence(item, item.id, turnIds)
    seenProvenance.add(item.provenance)
    seenBasis.add(item.basis)
  }
}

for (const provenanceValue of provenance) {
  if (!seenProvenance.has(provenanceValue)) fail(`fixtures never use provenance ${provenanceValue}`)
}
for (const basisValue of basis) {
  if (!seenBasis.has(basisValue)) fail(`fixtures never use basis ${basisValue}`)
}

const knownCalls = new Set([...historyIds, ...liveIds])
for (const campaign of campaigns) {
  const activitySum = campaign.activity.reduce((total, bucket) => total + bucket.count, 0)
  if (activitySum !== campaign.callCount) fail(`${campaign.id}: activity sum ${activitySum} != callCount`)
  for (const bucket of campaign.activity) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(bucket.day)) fail(`${campaign.id}: bad day`)
    if (bucket.hour < 0 || bucket.hour > 23) fail(`${campaign.id}: bad hour`)
  }
  for (const callId of campaign.relatedCallIds) {
    if (!knownCalls.has(callId)) fail(`${campaign.id} missing related call ${callId}`)
  }
  const related = new Set(campaign.relatedCallIds)
  for (const item of campaign.similarity) {
    if (!related.has(item.callId)) fail(`${campaign.id}: similarity ${item.callId} is not linked`)
    expectScore(item.score, item.callId)
    expectEnum(item.provenance, provenance, item.callId)
  }
  for (const item of [...campaign.commonScriptPhrases, ...campaign.sharedIndicators]) {
    checkIntelligence(item, item.id, null)
    seenProvenance.add(item.provenance)
    seenBasis.add(item.basis)
  }
  for (const call of history) {
    if (!related.has(call.id)) continue
    const when = new Date(call.startedAt)
    const day = when.toISOString().slice(0, 10)
    const hour = when.getUTCHours()
    const bucket = campaign.activity.find((item) => item.day === day && item.hour === hour)
    if (!bucket || bucket.count < 1) fail(`${campaign.id}: no activity bucket for ${call.id}`)
  }
}

if (!Array.isArray(system.providers) || system.providers.length < 3) fail('system providers')
if (system.concurrency.activeCalls !== live.length) fail('system activeCalls should match the live fixture count')
for (const provider of system.providers) {
  expectEnum(provider.role, new Set(['telephony', 'stt', 'tts', 'llm']), provider.id)
  expectEnum(provider.status, new Set(['ok', 'degraded', 'down']), provider.id)
}

console.log(`fixtures ok: ${history.length} history, ${live.length} live, ${campaigns.length} campaigns`)
