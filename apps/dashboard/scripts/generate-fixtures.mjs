import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const outDir = join(dirname(fileURLToPath(import.meta.url)), '..', 'src', 'mocks')

const IRS = 'camp_irs'
const MS = 'camp_ms'
const CHASE = 'camp_chase'
const IRS_NAME = 'IRS Warrant Wave'
const MS_NAME = 'Microsoft Defender Refund'
const CHASE_NAME = 'Chase Fraud Desk'

function minutes(mins, secs = 0) {
  return (mins * 60 + secs) * 1000
}

function cls(label, provenance, confidence) {
  return { label, provenance, confidence }
}

function pipeline(stt, llm, tts, sampledAt) {
  return {
    sampledAt,
    sttMs: stt,
    llmMs: llm,
    ttsMs: tts,
    e2eMs: stt + llm + tts + 40,
  }
}

function assertChain(id, transitions) {
  let previous = null
  let lastOffset = -1
  for (const transition of transitions) {
    if (transition.from !== previous) {
      throw new Error(`${id}: transition ${transition.to} does not follow ${previous}`)
    }
    if (transition.offsetMs < lastOffset) {
      throw new Error(`${id}: transitions are out of order`)
    }
    previous = transition.to
    lastOffset = transition.offsetMs
  }
}

function buildTranscript(id, turns) {
  return turns.map((turn, index) => ({
    id: `${id}_t${index + 1}`,
    speaker: turn.speaker,
    text: turn.text,
    offsetMs: turn.offsetMs,
    provenance: turn.provenance ?? 'observed',
  }))
}

function buildIntelligence(id, items) {
  return items.map((item, index) => ({
    id: `${id}_i${index + 1}`,
    kind: item.kind,
    label: item.label,
    value: item.value,
    provenance: item.provenance,
    basis: item.basis,
    confidence: item.confidence ?? null,
    evidenceTurnIds: (item.evidence ?? []).map((turnNumber) => `${id}_t${turnNumber}`),
  }))
}

function expandHistory(seed) {
  const startMs = Date.parse(seed.startedAt)
  const stamp = (offsetMs) => new Date(startMs + offsetMs).toISOString()
  const transcript = buildTranscript(seed.id, seed.transcript)
  for (const turn of transcript) {
    if (turn.offsetMs > seed.durationMs) {
      throw new Error(`${seed.id}: transcript extends past duration`)
    }
  }
  const intelligence = buildIntelligence(seed.id, seed.intelligence)
  assertChain(seed.id, seed.transitions)
  const stateTransitions = seed.transitions.map((item, index) => ({
    id: `${seed.id}_s${index + 1}`,
    at: stamp(item.offsetMs),
    offsetMs: item.offsetMs,
    from: item.from,
    to: item.to,
    reason: item.reason,
    provenance: item.provenance,
  }))
  const last = stateTransitions[stateTransitions.length - 1]
  if (!last) throw new Error(`${seed.id}: missing transitions`)
  if (seed.engagementDurationMs > seed.durationMs) {
    throw new Error(`${seed.id}: engagement exceeds duration`)
  }
  const observations = seed.observations.map((item, index) => ({
    id: `${seed.id}_o${index + 1}`,
    at: stamp(item.offsetMs),
    offsetMs: item.offsetMs,
    category: item.category,
    raw: item.raw,
    interpretation: item.interpretation,
  }))
  const extraEvents = seed.extraEvents ?? []
  const technicalEvents = [
    {
      id: `${seed.id}_e1`,
      at: stamp(0),
      offsetMs: 0,
      source: 'telephony',
      severity: 'info',
      message: 'Inbound leg answered',
      attributes: [
        { key: 'codec', value: 'PCMU' },
        { key: 'leg', value: 'honeypot' },
      ],
    },
    {
      id: `${seed.id}_e2`,
      at: stamp(650),
      offsetMs: 650,
      source: 'stt',
      severity: 'info',
      message: 'Streaming recognition started',
      attributes: [{ key: 'locale', value: 'en-US' }],
    },
    {
      id: `${seed.id}_e3`,
      at: stamp(2400),
      offsetMs: 2400,
      source: 'llm',
      severity: 'info',
      message: 'Stall persona reply committed',
      attributes: [{ key: 'persona', value: 'calm-stall' }],
    },
    ...extraEvents.map((item, index) => ({
      id: `${seed.id}_ex${index + 1}`,
      at: stamp(item.offsetMs),
      offsetMs: item.offsetMs,
      source: item.source,
      severity: item.severity,
      message: item.message,
      attributes: item.attributes ?? [],
    })),
    {
      id: `${seed.id}_e_end`,
      at: stamp(seed.durationMs),
      offsetMs: seed.durationMs,
      source: 'telephony',
      severity: seed.status === 'error' ? 'error' : 'info',
      message: seed.endEvent,
      attributes: [{ key: 'status', value: seed.status }],
    },
  ].sort((left, right) => left.offsetMs - right.offsetMs)
  const extraTimeline = seed.extraTimeline ?? []
  const timeline = [
    {
      id: `${seed.id}_l0`,
      at: stamp(0),
      offsetMs: 0,
      kind: 'telephony',
      title: 'Answered',
      detail: 'Honeypot leg connected.',
    },
    ...stateTransitions.map((item) => ({
      id: `${seed.id}_l_${item.id}`,
      at: item.at,
      offsetMs: item.offsetMs,
      kind: 'state',
      title: item.reason,
      detail: `${item.from ?? 'start'} → ${item.to}`,
    })),
    ...extraTimeline.map((item, index) => ({
      id: `${seed.id}_lx${index + 1}`,
      at: stamp(item.offsetMs),
      offsetMs: item.offsetMs,
      kind: item.kind,
      title: item.title,
      detail: item.detail,
    })),
    {
      id: `${seed.id}_lend`,
      at: stamp(seed.durationMs),
      offsetMs: seed.durationMs,
      kind: seed.status === 'error' ? 'error' : 'telephony',
      title: seed.endTitle,
      detail: seed.endEvent,
    },
  ].sort((left, right) => left.offsetMs - right.offsetMs || left.id.localeCompare(right.id))
  const keyIndicators = seed.keyIndicatorIndexes.map((index) => {
    const item = intelligence[index - 1]
    if (!item) throw new Error(`${seed.id}: bad key indicator index ${index}`)
    return item
  })
  return {
    id: seed.id,
    startedAt: new Date(startMs).toISOString(),
    endedAt: new Date(startMs + seed.durationMs).toISOString(),
    durationMs: seed.durationMs,
    engagementDurationMs: seed.engagementDurationMs,
    status: seed.status,
    callerNumberMasked: seed.callerNumberMasked,
    conversationState: last.to,
    stateProvenance: last.provenance,
    classification: seed.classification,
    campaignId: seed.campaignId,
    campaignName: seed.campaignName,
    keyIndicators,
    intelligence,
    pipeline: pipeline(seed.latency[0], seed.latency[1], seed.latency[2], stamp(seed.durationMs)),
    timeline,
    transcript,
    stateTransitions,
    observations,
    correlation: seed.correlation.map((item, index) => ({
      id: `${seed.id}_c${index + 1}`,
      campaignId: item.campaignId,
      campaignName: item.campaignName,
      score: item.score,
      summary: item.summary,
      explanation: item.explanation,
      provenance: item.provenance,
      matchedOn: item.matchedOn,
    })),
    technicalEvents,
  }
}

function expandLive(seed) {
  const transcript = buildTranscript(seed.id, seed.transcript)
  const intelligence = buildIntelligence(seed.id, seed.intelligence)
  assertChain(seed.id, seed.transitions)
  const last = seed.transitions[seed.transitions.length - 1]
  const keyIndicators = seed.keyIndicatorIndexes.map((index) => {
    const item = intelligence[index - 1]
    if (!item) throw new Error(`${seed.id}: bad key indicator index ${index}`)
    return item
  })
  const extraEvents = seed.extraEvents ?? []
  const extraTimeline = seed.extraTimeline ?? []
  const board = {
    id: seed.id,
    startedOffsetSec: seed.startedOffsetSec,
    callerNumberMasked: seed.callerNumberMasked,
    conversationState: last.to,
    stateProvenance: last.provenance,
    classification: seed.classification,
    campaignId: seed.campaignId,
    campaignName: seed.campaignName,
    transcript,
    intelligence,
    pipeline: {
      sttMs: seed.latency[0],
      llmMs: seed.latency[1],
      ttsMs: seed.latency[2],
      e2eMs: seed.latency[0] + seed.latency[1] + seed.latency[2] + 40,
    },
  }
  const extra = {
    id: seed.id,
    engagementDelayMs: seed.engagementDelayMs,
    keyIndicators,
    timeline: [
      {
        id: `${seed.id}_l0`,
        offsetMs: 0,
        kind: 'telephony',
        title: 'Answered',
        detail: 'Honeypot leg connected. Call is still up.',
      },
      ...seed.transitions.map((item, index) => ({
        id: `${seed.id}_l_s${index + 1}`,
        offsetMs: item.offsetMs,
        kind: 'state',
        title: item.reason,
        detail: `${item.from ?? 'start'} → ${item.to}`,
      })),
      ...extraTimeline.map((item, index) => ({
        id: `${seed.id}_lx${index + 1}`,
        offsetMs: item.offsetMs,
        kind: item.kind,
        title: item.title,
        detail: item.detail,
      })),
    ].sort((left, right) => left.offsetMs - right.offsetMs),
    stateTransitions: seed.transitions.map((item, index) => ({
      id: `${seed.id}_s${index + 1}`,
      offsetMs: item.offsetMs,
      from: item.from,
      to: item.to,
      reason: item.reason,
      provenance: item.provenance,
    })),
    observations: seed.observations.map((item, index) => ({
      id: `${seed.id}_o${index + 1}`,
      offsetMs: item.offsetMs,
      category: item.category,
      raw: item.raw,
      interpretation: item.interpretation,
    })),
    correlation: seed.correlation.map((item, index) => ({
      id: `${seed.id}_c${index + 1}`,
      campaignId: item.campaignId,
      campaignName: item.campaignName,
      score: item.score,
      summary: item.summary,
      explanation: item.explanation,
      provenance: item.provenance,
      matchedOn: item.matchedOn,
    })),
    technicalEvents: [
      {
        id: `${seed.id}_e1`,
        offsetMs: 0,
        source: 'telephony',
        severity: 'info',
        message: 'Inbound leg answered',
        attributes: [
          { key: 'codec', value: 'PCMU' },
          { key: 'leg', value: 'honeypot' },
        ],
      },
      {
        id: `${seed.id}_e2`,
        offsetMs: 650,
        source: 'stt',
        severity: 'info',
        message: 'Streaming recognition started',
        attributes: [{ key: 'locale', value: 'en-US' }],
      },
      {
        id: `${seed.id}_e3`,
        offsetMs: 2400,
        source: 'llm',
        severity: 'info',
        message: 'Stall persona reply committed',
        attributes: [{ key: 'persona', value: 'calm-stall' }],
      },
      ...extraEvents.map((item, index) => ({
        id: `${seed.id}_ex${index + 1}`,
        offsetMs: item.offsetMs,
        source: item.source,
        severity: item.severity,
        message: item.message,
        attributes: item.attributes ?? [],
      })),
    ].sort((left, right) => left.offsetMs - right.offsetMs),
  }
  return { board, extra }
}

function observed(text) {
  return { text, provenance: 'observed' }
}

function inferred(text) {
  return { text, provenance: 'inferred' }
}

function unverified(text) {
  return { text, provenance: 'unverified' }
}

const historySeeds = [
  {
    id: 'call_h01',
    startedAt: '2026-09-25T14:02:00.000Z',
    durationMs: minutes(18, 12),
    engagementDurationMs: minutes(14, 40),
    status: 'completed',
    callerNumberMasked: '+1 (202) 555-0148',
    classification: cls('irs_impersonation', 'inferred', 0.93),
    campaignId: IRS,
    campaignName: IRS_NAME,
    latency: [420, 890, 300],
    endTitle: 'Caller released the line',
    endEvent: 'Caller ended the call after the honeypot promised to call back with the cards.',
    keyIndicatorIndexes: [1, 4, 6],
    transcript: [
      { offsetMs: 0, speaker: 'honeypot', text: 'Hello?' },
      { offsetMs: 11000, speaker: 'caller', text: 'This is Officer Michael Brennan with the IRS Criminal Investigation Division. Am I speaking with the taxpayer?' },
      { offsetMs: 28000, speaker: 'honeypot', text: 'What case number should I write down?' },
      { offsetMs: 36000, speaker: 'caller', text: 'Case 44-IRS-2291. A federal warrant is already in your name for tax irregularities.' },
      { offsetMs: 70000, speaker: 'honeypot', text: 'I have not received a letter. Who signs that warrant?' },
      { offsetMs: 82000, speaker: 'caller', text: 'Local law enforcement is being dispatched unless this is settled today. Do not hang up.' },
      { offsetMs: 140000, speaker: 'honeypot', text: 'Settled how? Say it once, slowly.' },
      { offsetMs: 152000, speaker: 'caller', text: 'You will buy government payment cards for eight thousand four hundred dollars and read me the codes.' },
      { offsetMs: 420000, speaker: 'honeypot', text: 'I have to walk to a store. I will call this number back.' },
      { offsetMs: 440000, speaker: 'caller', text: 'You cannot call back. Stay on this recorded line. I will wait ten minutes.' },
      { offsetMs: 980000, speaker: 'honeypot', text: 'I am stepping away with the handset. If this drops I will redial.' },
      { offsetMs: 1000000, speaker: 'caller', text: 'Do not speak to the local IRS office. They are not cleared on case 44-IRS-2291.' },
    ],
    transitions: [
      { offsetMs: 200, from: null, to: 'greeting', reason: 'Honeypot answered with a short hello.', provenance: 'observed' },
      { offsetMs: 11000, from: 'greeting', to: 'identity_probe', reason: 'Caller claimed an IRS officer role and asked for the taxpayer.', provenance: 'inferred' },
      { offsetMs: 36000, from: 'identity_probe', to: 'pretext', reason: 'Caller introduced a case number and a warrant story.', provenance: 'inferred' },
      { offsetMs: 82000, from: 'pretext', to: 'urgency', reason: 'Caller threatened same-day dispatch if the line drops.', provenance: 'inferred' },
      { offsetMs: 152000, from: 'urgency', to: 'payment_request', reason: 'Caller named payment cards and an amount.', provenance: 'inferred' },
      { offsetMs: 980000, from: 'payment_request', to: 'closing', reason: 'Honeypot moved to leave the line and the caller allowed a short close.', provenance: 'inferred' },
    ],
    extraTimeline: [
      { offsetMs: 152000, kind: 'intel', title: 'Payment amount captured', detail: 'Caller stated $8,400 in government payment cards.' },
    ],
    extraEvents: [
      { offsetMs: 150000, source: 'llm', severity: 'info', message: 'State proposal payment_request accepted', attributes: [{ key: 'confidence', value: '0.93' }] },
    ],
    observations: [
      {
        offsetMs: 36000,
        category: 'script',
        raw: observed('Caller said "IRS Criminal Investigation Division" and case 44-IRS-2291.'),
        interpretation: inferred('Warrant-and-case-number opening matches the IRS Warrant Wave script.'),
      },
      {
        offsetMs: 82000,
        category: 'threat',
        raw: observed('Caller said local law enforcement is being dispatched unless this is settled today.'),
        interpretation: inferred('The dispatch line is pressure to keep the target from hanging up, not a verified enforcement action.'),
      },
      {
        offsetMs: 152000,
        category: 'payment',
        raw: observed('Caller instructed the target to buy government payment cards for $8,400 and read the codes.'),
        interpretation: inferred('Gift-card codes are the cash-out path for this wave.'),
      },
      {
        offsetMs: 1000000,
        category: 'callback',
        raw: observed('Caller said not to contact the local IRS office.'),
        interpretation: null,
      },
    ],
    intelligence: [
      { kind: 'script_phrase', label: 'Criminal Investigation Division', value: 'IRS Criminal Investigation Division', provenance: 'observed', basis: 'raw', evidence: [2] },
      { kind: 'entity', label: 'Case number', value: '44-IRS-2291', provenance: 'observed', basis: 'raw', evidence: [4, 12] },
      { kind: 'amount', label: 'Card demand', value: '$8,400 in payment cards', provenance: 'observed', basis: 'raw', evidence: [8] },
      { kind: 'tactic', label: 'Dispatch threat', value: 'Same-day law-enforcement dispatch unless the target stays on the line', provenance: 'inferred', basis: 'derived', confidence: 0.9, evidence: [6] },
      { kind: 'tactic', label: 'Gift-card cash-out', value: 'Read-back of retail payment-card codes', provenance: 'inferred', basis: 'derived', confidence: 0.92, evidence: [8] },
      { kind: 'entity', label: 'Officer name', value: 'Michael Brennan is a spoken name with no roster match', provenance: 'unverified', basis: 'derived', evidence: [2] },
    ],
    correlation: [
      {
        campaignId: IRS,
        campaignName: IRS_NAME,
        score: 0.92,
        summary: 'Strong match to IRS Warrant Wave.',
        explanation: 'Observed case-number pattern 44-IRS-####, the Criminal Investigation Division line, and a payment-card code read-back line up with the wave. The officer name is still unverified and was not required for the match.',
        provenance: 'inferred',
        matchedOn: [
          { label: 'Criminal Investigation Division', provenance: 'observed' },
          { label: 'Case 44-IRS-2291', provenance: 'observed' },
          { label: 'Payment-card code read-back', provenance: 'inferred' },
        ],
      },
      {
        campaignId: CHASE,
        campaignName: CHASE_NAME,
        score: 0.28,
        summary: 'Chase Fraud Desk rejected.',
        explanation: 'Both scripts push same-day payment, but this call never mentions a bank, Zelle, or a one-time code. Shared urgency is not enough.',
        provenance: 'inferred',
        matchedOn: [{ label: 'Same-day payment pressure', provenance: 'inferred' }],
      },
    ],
  },
  {
    id: 'call_h02',
    startedAt: '2026-09-25T11:40:00.000Z',
    durationMs: minutes(6, 5),
    engagementDurationMs: minutes(2, 10),
    status: 'abandoned',
    callerNumberMasked: '+1 (202) 555-0160',
    classification: cls('irs_impersonation', 'inferred', 0.81),
    campaignId: IRS,
    campaignName: IRS_NAME,
    latency: [510, 700, 280],
    endTitle: 'Caller hung up',
    endEvent: 'Caller disconnected after the honeypot asked for a badge number.',
    keyIndicatorIndexes: [1, 3, 4],
    transcript: [
      { offsetMs: 0, speaker: 'honeypot', text: 'Hello?' },
      { offsetMs: 8000, speaker: 'caller', text: 'IRS Criminal Investigation Division. There is a warrant with your name on it. Do not leave the phone.' },
      { offsetMs: 22000, speaker: 'honeypot', text: 'Which office, and what is the badge number?' },
      { offsetMs: 30000, speaker: 'caller', text: 'I do not give badge numbers on an unsecured line. The warrant executes if you stall.' },
      { offsetMs: 70000, speaker: 'honeypot', text: 'Then read the case number the way it is printed.' },
      { offsetMs: 78000, speaker: 'caller', text: 'You are refusing to cooperate. I am releasing this line.' },
    ],
    transitions: [
      { offsetMs: 200, from: null, to: 'greeting', reason: 'Honeypot answered.', provenance: 'observed' },
      { offsetMs: 8000, from: 'greeting', to: 'pretext', reason: 'Caller opened with a warrant claim and an IRS division name.', provenance: 'inferred' },
      { offsetMs: 30000, from: 'pretext', to: 'urgency', reason: 'Caller said the warrant executes if the target stalls.', provenance: 'inferred' },
    ],
    extraTimeline: [
      { offsetMs: 350000, kind: 'telephony', title: 'Caller disconnect', detail: 'Far end released after refusing the badge challenge.' },
    ],
    extraEvents: [
      { offsetMs: 350000, source: 'telephony', severity: 'info', message: 'Far end BYE after the badge challenge', attributes: [{ key: 'cause', value: 'normal-clearing' }] },
    ],
    observations: [
      {
        offsetMs: 8000,
        category: 'script',
        raw: observed('Caller said "IRS Criminal Investigation Division" and that a warrant is in the target name.'),
        interpretation: inferred('Opening matches IRS Warrant Wave even without a case number.'),
      },
      {
        offsetMs: 30000,
        category: 'identity',
        raw: observed('Caller refused to give a badge number and called the line unsecured.'),
        interpretation: null,
      },
    ],
    intelligence: [
      { kind: 'script_phrase', label: 'Criminal Investigation Division', value: 'IRS Criminal Investigation Division', provenance: 'observed', basis: 'raw', evidence: [2] },
      { kind: 'tactic', label: 'Warrant opener', value: 'Warrant named before any case identifier', provenance: 'observed', basis: 'raw', evidence: [2] },
      { kind: 'tactic', label: 'Stall penalty', value: 'Caller claims delay causes the warrant to execute', provenance: 'inferred', basis: 'derived', confidence: 0.77, evidence: [4] },
      { kind: 'callback', label: 'Badge withheld', value: 'No badge number was spoken', provenance: 'unverified', basis: 'raw', evidence: [4] },
    ],
    correlation: [
      {
        campaignId: IRS,
        campaignName: IRS_NAME,
        score: 0.74,
        summary: 'Partial IRS Warrant Wave match.',
        explanation: 'The division name and warrant opener were observed. The call died before a case number or payment path, so the score stays below the full-script matches.',
        provenance: 'inferred',
        matchedOn: [
          { label: 'Criminal Investigation Division', provenance: 'observed' },
          { label: 'Warrant opener', provenance: 'observed' },
        ],
      },
    ],
  },
  {
    id: 'call_h03',
    startedAt: '2026-09-24T16:18:00.000Z',
    durationMs: minutes(22, 40),
    engagementDurationMs: minutes(19, 5),
    status: 'completed',
    callerNumberMasked: '+1 (888) 555-0133',
    classification: cls('tech_support', 'inferred', 0.9),
    campaignId: MS,
    campaignName: MS_NAME,
    latency: [390, 760, 340],
    endTitle: 'Caller released after tool instructions',
    endEvent: 'Caller ended the call after describing an AnyDesk session the honeypot did not join.',
    keyIndicatorIndexes: [1, 3, 5],
    transcript: [
      { offsetMs: 0, speaker: 'honeypot', text: 'Hello?' },
      { offsetMs: 9000, speaker: 'caller', text: 'This is Microsoft Support. Your computer reported a virus and a refund of three hundred ninety-nine dollars is waiting.' },
      { offsetMs: 26000, speaker: 'honeypot', text: 'How did Microsoft get this phone number?' },
      { offsetMs: 34000, speaker: 'caller', text: 'The alert came from your Windows license. Do not shut the computer down or the refund is cancelled.' },
      { offsetMs: 90000, speaker: 'honeypot', text: 'I am not in front of that machine. What exactly is on the screen?' },
      { offsetMs: 102000, speaker: 'caller', text: 'A Microsoft Defender pop-up. We have to connect with AnyDesk so I can confirm the refund.' },
      { offsetMs: 400000, speaker: 'honeypot', text: 'Read the AnyDesk address slowly. I am writing, not clicking.' },
      { offsetMs: 412000, speaker: 'caller', text: 'The address is on your screen, nine digits. Tell me when the green connect button is up. Do not close Defender.' },
    ],
    transitions: [
      { offsetMs: 200, from: null, to: 'greeting', reason: 'Honeypot answered.', provenance: 'observed' },
      { offsetMs: 9000, from: 'greeting', to: 'pretext', reason: 'Caller claimed Microsoft Support and a pending refund.', provenance: 'inferred' },
      { offsetMs: 34000, from: 'pretext', to: 'urgency', reason: 'Caller said shutting down cancels the refund.', provenance: 'inferred' },
      { offsetMs: 102000, from: 'urgency', to: 'extraction', reason: 'Caller named AnyDesk and asked for a remote session.', provenance: 'inferred' },
    ],
    extraTimeline: [
      { offsetMs: 102000, kind: 'intel', title: 'Remote tool named', detail: 'Caller asked for AnyDesk. Honeypot did not connect.' },
    ],
    extraEvents: [
      { offsetMs: 102000, source: 'orchestrator', severity: 'info', message: 'Remote-control request flagged; honeypot stayed off the tool', attributes: [{ key: 'tool', value: 'AnyDesk' }] },
    ],
    observations: [
      {
        offsetMs: 9000,
        category: 'script',
        raw: observed('Caller said "This is Microsoft Support" and that a $399 refund is waiting.'),
        interpretation: inferred('Refund-for-virus opening matches Microsoft Defender Refund.'),
      },
      {
        offsetMs: 102000,
        category: 'tooling',
        raw: observed('Caller told the target to connect with AnyDesk and not to close Defender.'),
        interpretation: inferred('The refund story is cover for a remote-access session.'),
      },
      {
        offsetMs: 412000,
        category: 'tooling',
        raw: unverified('Caller referred to a nine-digit address. Individual digits were not locked by STT.'),
        interpretation: inferred('An AnyDesk address was requested even though the digits are unverified.'),
      },
    ],
    intelligence: [
      { kind: 'script_phrase', label: 'Microsoft Support opener', value: 'This is Microsoft Support', provenance: 'observed', basis: 'raw', evidence: [2] },
      { kind: 'amount', label: 'Refund lure', value: '$399 refund', provenance: 'observed', basis: 'raw', evidence: [2] },
      { kind: 'tactic', label: 'Do not shut down', value: 'Shutdown would cancel the refund', provenance: 'inferred', basis: 'derived', confidence: 0.86, evidence: [4] },
      { kind: 'entity', label: 'Remote tool', value: 'AnyDesk', provenance: 'observed', basis: 'raw', evidence: [6] },
      { kind: 'callback', label: 'AnyDesk address', value: 'Nine-digit address requested; digits not confirmed', provenance: 'unverified', basis: 'raw', evidence: [8] },
    ],
    correlation: [
      {
        campaignId: MS,
        campaignName: MS_NAME,
        score: 0.94,
        summary: 'Microsoft Defender Refund match.',
        explanation: 'Observed Microsoft Support opener, $399 refund, Defender pop-up, and an AnyDesk request. The address digits stayed unverified and were not required.',
        provenance: 'inferred',
        matchedOn: [
          { label: 'Microsoft Support opener', provenance: 'observed' },
          { label: '$399 refund', provenance: 'observed' },
          { label: 'AnyDesk', provenance: 'observed' },
        ],
      },
    ],
  },
  {
    id: 'call_h04',
    startedAt: '2026-09-24T09:12:00.000Z',
    durationMs: minutes(9, 18),
    engagementDurationMs: minutes(7, 2),
    status: 'abandoned',
    callerNumberMasked: '+1 (888) 555-0177',
    classification: cls('tech_support', 'inferred', 0.72),
    campaignId: MS,
    campaignName: MS_NAME,
    latency: [450, 640, 310],
    endTitle: 'Caller hung up during the stall',
    endEvent: 'Caller disconnected while the honeypot claimed to be walking to the computer.',
    keyIndicatorIndexes: [1, 2, 3],
    transcript: [
      { offsetMs: 0, speaker: 'honeypot', text: 'Hello?' },
      { offsetMs: 7000, speaker: 'caller', text: 'Microsoft Support calling about a refund on your Defender subscription. A virus report is open.' },
      { offsetMs: 20000, speaker: 'honeypot', text: 'I am in another room from that computer. You will have to wait.' },
      { offsetMs: 28000, speaker: 'caller', text: 'Do not shut it down while you walk. The refund window is closing this hour.' },
      { offsetMs: 240000, speaker: 'honeypot', text: 'I am still walking over. Stay on the line.' },
      { offsetMs: 255000, speaker: 'caller', text: 'I cannot hold for people who will not sit at the machine. Goodbye.' },
    ],
    transitions: [
      { offsetMs: 200, from: null, to: 'greeting', reason: 'Honeypot answered.', provenance: 'observed' },
      { offsetMs: 7000, from: 'greeting', to: 'pretext', reason: 'Caller claimed Microsoft Support and a Defender refund.', provenance: 'inferred' },
      { offsetMs: 28000, from: 'pretext', to: 'urgency', reason: 'Caller put an hour-long deadline on the refund.', provenance: 'inferred' },
      { offsetMs: 240000, from: 'urgency', to: 'compliance_stall', reason: 'Honeypot kept the caller waiting away from the computer.', provenance: 'observed' },
    ],
    extraEvents: [],
    observations: [
      {
        offsetMs: 7000,
        category: 'script',
        raw: observed('Caller said Microsoft Support and a Defender subscription refund, plus an open virus report.'),
        interpretation: inferred('Likely the same refund wave, earlier in the script, before a remote tool is named.'),
      },
      {
        offsetMs: 255000,
        category: 'other',
        raw: observed('Caller refused to hold while the target was away from the computer.'),
        interpretation: null,
      },
    ],
    intelligence: [
      { kind: 'script_phrase', label: 'Microsoft Support opener', value: 'Microsoft Support calling about a refund', provenance: 'observed', basis: 'raw', evidence: [2] },
      { kind: 'tactic', label: 'Refund deadline', value: 'Refund window closing within the hour', provenance: 'inferred', basis: 'derived', confidence: 0.7, evidence: [4] },
      { kind: 'entity', label: 'Product name', value: 'Microsoft Defender', provenance: 'observed', basis: 'raw', evidence: [2] },
    ],
    correlation: [
      {
        campaignId: MS,
        campaignName: MS_NAME,
        score: 0.71,
        summary: 'Early Microsoft Defender Refund match.',
        explanation: 'Defender and the refund opener were observed. No remote tool was named before the caller abandoned, so this is a partial script.',
        provenance: 'inferred',
        matchedOn: [
          { label: 'Microsoft Support opener', provenance: 'observed' },
          { label: 'Microsoft Defender', provenance: 'observed' },
        ],
      },
    ],
  },
  {
    id: 'call_h05',
    startedAt: '2026-09-23T19:48:00.000Z',
    durationMs: minutes(14, 33),
    engagementDurationMs: minutes(12, 11),
    status: 'completed',
    callerNumberMasked: '+1 (800) 555-0119',
    classification: cls('bank_fraud', 'inferred', 0.95),
    campaignId: CHASE,
    campaignName: CHASE_NAME,
    latency: [360, 810, 290],
    endTitle: 'Caller released after the code refusal',
    endEvent: 'Caller ended the call when the honeypot would not read a one-time code.',
    keyIndicatorIndexes: [1, 3, 4],
    transcript: [
      { offsetMs: 0, speaker: 'honeypot', text: 'Hello?' },
      { offsetMs: 6000, speaker: 'caller', text: 'This is the Chase fraud department. We detected a Zelle transfer of two thousand four hundred dollars.' },
      { offsetMs: 18000, speaker: 'honeypot', text: 'I do not remember a Zelle payment. Which department are you with?' },
      { offsetMs: 26000, speaker: 'caller', text: 'Fraud desk. We can reverse it if you read the one-time code we just texted. Do not call the number on your card.' },
      { offsetMs: 80000, speaker: 'honeypot', text: 'I am not going to read a code out loud. What is the alternative?' },
      { offsetMs: 92000, speaker: 'caller', text: 'Then we move the rest of the balance into a safe account that is already open in your name. I still need the code and the last four of the debit card.' },
      { offsetMs: 700000, speaker: 'honeypot', text: 'I will not give the last four or the code. You can note that I refused.' },
      { offsetMs: 712000, speaker: 'caller', text: 'Then the Zelle payment will post. This was your notice.' },
    ],
    transitions: [
      { offsetMs: 200, from: null, to: 'greeting', reason: 'Honeypot answered.', provenance: 'observed' },
      { offsetMs: 6000, from: 'greeting', to: 'pretext', reason: 'Caller claimed the Chase fraud department and a Zelle debit.', provenance: 'inferred' },
      { offsetMs: 26000, from: 'pretext', to: 'payment_request', reason: 'Caller asked for a one-time code and warned against the number on the card.', provenance: 'inferred' },
      { offsetMs: 92000, from: 'payment_request', to: 'extraction', reason: 'Caller asked for the code plus the last four, tied to a safe account.', provenance: 'inferred' },
    ],
    extraTimeline: [
      { offsetMs: 92000, kind: 'intel', title: 'Safe-account ask', detail: 'Caller wanted a code and the last four moved into a safe account.' },
    ],
    extraEvents: [
      { offsetMs: 26000, source: 'orchestrator', severity: 'warn', message: 'One-time-code request detected; persona instructed to refuse', attributes: [{ key: 'policy', value: 'no-otp-readback' }] },
    ],
    observations: [
      {
        offsetMs: 6000,
        category: 'script',
        raw: observed('Caller said "Chase fraud department" and a Zelle transfer of $2,400.'),
        interpretation: inferred('This is the Chase Fraud Desk opener.'),
      },
      {
        offsetMs: 26000,
        category: 'payment',
        raw: observed('Caller asked for a texted one-time code and said not to use the number on the card.'),
        interpretation: inferred('Isolating the target from the real bank is part of the script.'),
      },
      {
        offsetMs: 92000,
        category: 'payment',
        raw: observed('Caller said the remaining balance would move to a safe account and asked for the last four.'),
        interpretation: inferred('Safe account is a mule handoff, not a Chase product the honeypot can see.'),
      },
    ],
    intelligence: [
      { kind: 'script_phrase', label: 'Chase fraud department', value: 'This is the Chase fraud department', provenance: 'observed', basis: 'raw', evidence: [2] },
      { kind: 'amount', label: 'Zelle amount', value: '$2,400 Zelle transfer', provenance: 'observed', basis: 'raw', evidence: [2] },
      { kind: 'indicator', label: 'OTP read-back', value: 'Caller asked the target to read a one-time code', provenance: 'observed', basis: 'raw', evidence: [4] },
      { kind: 'tactic', label: 'Safe account', value: 'Remaining balance moved to a safe account in the target name', provenance: 'inferred', basis: 'derived', confidence: 0.91, evidence: [6] },
      { kind: 'entity', label: 'Last four', value: 'Debit last four requested and refused', provenance: 'observed', basis: 'raw', evidence: [6, 7] },
    ],
    correlation: [
      {
        campaignId: CHASE,
        campaignName: CHASE_NAME,
        score: 0.96,
        summary: 'Chase Fraud Desk match.',
        explanation: 'Observed Chase fraud opener, $2,400 Zelle, OTP read-back, and a safe-account handoff. The honeypot refused the code, which did not change the match.',
        provenance: 'inferred',
        matchedOn: [
          { label: 'Chase fraud department', provenance: 'observed' },
          { label: '$2,400 Zelle', provenance: 'observed' },
          { label: 'Safe account', provenance: 'inferred' },
        ],
      },
    ],
  },
  {
    id: 'call_h06',
    startedAt: '2026-09-23T13:02:00.000Z',
    durationMs: minutes(3, 48),
    engagementDurationMs: minutes(1, 20),
    status: 'abandoned',
    callerNumberMasked: '+1 (800) 555-0182',
    classification: cls('bank_fraud', 'inferred', 0.64),
    campaignId: CHASE,
    campaignName: CHASE_NAME,
    latency: [700, 540, 260],
    endTitle: 'Caller hung up',
    endEvent: 'Caller disconnected when asked to wait while the honeypot dialed the number on the card.',
    keyIndicatorIndexes: [1, 2, 3],
    transcript: [
      { offsetMs: 0, speaker: 'honeypot', text: 'Hello?' },
      { offsetMs: 5000, speaker: 'caller', text: 'Chase fraud department. We locked a suspicious Zelle transfer. I need you to verify the account.' },
      { offsetMs: 16000, speaker: 'honeypot', text: 'I am going to call the number printed on the card while you wait.' },
      { offsetMs: 24000, speaker: 'caller', text: 'Do not call that number. Those agents cannot see this case. I will have to drop the line.' },
    ],
    transitions: [
      { offsetMs: 200, from: null, to: 'greeting', reason: 'Honeypot answered.', provenance: 'observed' },
      { offsetMs: 5000, from: 'greeting', to: 'identity_probe', reason: 'Caller claimed Chase fraud and started an account verification.', provenance: 'inferred' },
    ],
    extraEvents: [
      { offsetMs: 20000, source: 'stt', severity: 'warn', message: 'Elevated partial latency on the caller channel', attributes: [{ key: 'partial_ms', value: '700' }] },
    ],
    observations: [
      {
        offsetMs: 5000,
        category: 'identity',
        raw: observed('Caller said Chase fraud department and a locked Zelle transfer.'),
        interpretation: inferred('Short opener is consistent with Chase Fraud Desk but ended before payment instructions.'),
      },
      {
        offsetMs: 24000,
        category: 'callback',
        raw: observed('Caller said not to call the number on the card.'),
        interpretation: null,
      },
    ],
    intelligence: [
      { kind: 'script_phrase', label: 'Chase fraud department', value: 'Chase fraud department', provenance: 'observed', basis: 'raw', evidence: [2] },
      { kind: 'indicator', label: 'Zelle mention', value: 'Suspicious Zelle transfer, amount not stated', provenance: 'observed', basis: 'raw', evidence: [2] },
      { kind: 'tactic', label: 'Isolate from the bank', value: 'Caller forbade using the number on the card', provenance: 'unverified', basis: 'derived', evidence: [4] },
    ],
    correlation: [
      {
        campaignId: CHASE,
        campaignName: CHASE_NAME,
        score: 0.62,
        summary: 'Thin Chase Fraud Desk match.',
        explanation: 'The fraud-department name and a Zelle mention were observed. Amount, OTP, and safe-account lines never arrived. Score is above the link threshold and below a full script.',
        provenance: 'inferred',
        matchedOn: [
          { label: 'Chase fraud department', provenance: 'observed' },
          { label: 'Zelle mention', provenance: 'observed' },
        ],
      },
    ],
  },
  {
    id: 'call_h07',
    startedAt: '2026-09-22T08:31:00.000Z',
    durationMs: minutes(11, 5),
    engagementDurationMs: minutes(8, 40),
    status: 'completed',
    callerNumberMasked: '+1 (312) 555-0166',
    classification: cls('utility_shutoff', 'inferred', 0.67),
    campaignId: null,
    campaignName: null,
    latency: [480, 600, 300],
    endTitle: 'Caller released',
    endEvent: 'Caller ended the call after the honeypot refused a same-day prepaid card.',
    keyIndicatorIndexes: [1, 2, 3],
    transcript: [
      { offsetMs: 0, speaker: 'honeypot', text: 'Hello?' },
      { offsetMs: 8000, speaker: 'caller', text: 'This is Peoples Energy collections. Your service shuts off at 6 PM today unless the past-due balance is paid.' },
      { offsetMs: 22000, speaker: 'honeypot', text: 'What address is the shutoff for, and what is the balance?' },
      { offsetMs: 30000, speaker: 'caller', text: 'The balance is two hundred eighty-six dollars. Pay with a prepaid card at the pharmacy and read me the number. We cannot take a card over a recorded line otherwise.' },
      { offsetMs: 120000, speaker: 'honeypot', text: 'I pay the utility on the website. I am not buying a card.' },
      { offsetMs: 132000, speaker: 'caller', text: 'The website will not post before the truck rolls. This is the only path left today.' },
    ],
    transitions: [
      { offsetMs: 200, from: null, to: 'greeting', reason: 'Honeypot answered.', provenance: 'observed' },
      { offsetMs: 8000, from: 'greeting', to: 'pretext', reason: 'Caller claimed a utility collections desk and a same-day shutoff.', provenance: 'inferred' },
      { offsetMs: 30000, from: 'pretext', to: 'payment_request', reason: 'Caller demanded a prepaid card and a number read-back.', provenance: 'inferred' },
    ],
    extraEvents: [],
    observations: [
      {
        offsetMs: 8000,
        category: 'threat',
        raw: observed('Caller said Peoples Energy will shut off service at 6 PM today.'),
        interpretation: inferred('Same-day shutoff is the pressure line. No campaign shares this opener.'),
      },
      {
        offsetMs: 30000,
        category: 'payment',
        raw: observed('Caller asked for a $286 prepaid card purchased at a pharmacy.'),
        interpretation: inferred('Prepaid-card read-back is a cash-out, similar in method to gift cards but not the same script.'),
      },
    ],
    intelligence: [
      { kind: 'entity', label: 'Claimed utility', value: 'Peoples Energy collections', provenance: 'observed', basis: 'raw', evidence: [2] },
      { kind: 'amount', label: 'Past-due demand', value: '$286 prepaid card', provenance: 'observed', basis: 'raw', evidence: [4] },
      { kind: 'tactic', label: 'Same-day shutoff', value: 'Service ends at 6 PM unless the card is read back', provenance: 'inferred', basis: 'derived', confidence: 0.66, evidence: [2, 6] },
      { kind: 'script_phrase', label: 'Campaign phrase match', value: 'No shared phrase with IRS, Microsoft, or Chase waves', provenance: 'unverified', basis: 'derived', evidence: [] },
    ],
    correlation: [
      {
        campaignId: null,
        campaignName: null,
        score: 0.22,
        summary: 'No campaign cleared the match threshold.',
        explanation: 'Shutoff threat and a prepaid card were observed. Phrases do not overlap IRS Warrant Wave, Microsoft Defender Refund, or Chase Fraud Desk. Left unlinked on purpose.',
        provenance: 'inferred',
        matchedOn: [],
      },
    ],
  },
  {
    id: 'call_h08',
    startedAt: '2026-09-21T15:44:00.000Z',
    durationMs: minutes(16, 22),
    engagementDurationMs: minutes(13, 50),
    status: 'completed',
    callerNumberMasked: '+1 (202) 555-0104',
    classification: cls('irs_impersonation', 'inferred', 0.88),
    campaignId: IRS,
    campaignName: IRS_NAME,
    latency: [410, 850, 320],
    endTitle: 'Caller released',
    endEvent: 'Caller ended the call after restating the payment-card instructions.',
    keyIndicatorIndexes: [1, 2, 4],
    transcript: [
      { offsetMs: 0, speaker: 'honeypot', text: 'Hello?' },
      { offsetMs: 10000, speaker: 'caller', text: 'Officer Dana Shah, IRS Criminal Investigation Division. Case 44-IRS-1880 is in warrant status.' },
      { offsetMs: 26000, speaker: 'honeypot', text: 'Spell the officer name and repeat the case number.' },
      { offsetMs: 34000, speaker: 'caller', text: 'Shah, S-H-A-H. The case is 44-IRS-1880. Settlement today is six thousand two hundred in payment cards.' },
      { offsetMs: 90000, speaker: 'honeypot', text: 'I do not have those cards in the house.' },
      { offsetMs: 98000, speaker: 'caller', text: 'Then you go to the retailer we approve and you stay on this phone the entire time. Hanging up executes the warrant.' },
    ],
    transitions: [
      { offsetMs: 200, from: null, to: 'greeting', reason: 'Honeypot answered.', provenance: 'observed' },
      { offsetMs: 10000, from: 'greeting', to: 'identity_probe', reason: 'Caller gave an officer name, division, and case number.', provenance: 'inferred' },
      { offsetMs: 34000, from: 'identity_probe', to: 'payment_request', reason: 'Caller named a payment-card settlement amount.', provenance: 'inferred' },
      { offsetMs: 98000, from: 'payment_request', to: 'urgency', reason: 'Caller said hanging up executes the warrant.', provenance: 'inferred' },
    ],
    extraEvents: [],
    observations: [
      {
        offsetMs: 10000,
        category: 'script',
        raw: observed('Caller said IRS Criminal Investigation Division and case 44-IRS-1880.'),
        interpretation: inferred('Same case-number pattern as IRS Warrant Wave with a different suffix.'),
      },
      {
        offsetMs: 34000,
        category: 'payment',
        raw: observed('Settlement stated as $6,200 in payment cards.'),
        interpretation: inferred('Amount changed from other calls in the wave; the card path did not.'),
      },
      {
        offsetMs: 34000,
        category: 'identity',
        raw: observed('Caller spelled the name Dana Shah.'),
        interpretation: unverified('The spelled name is still only a claim. No roster check has been run.'),
      },
    ],
    intelligence: [
      { kind: 'script_phrase', label: 'Criminal Investigation Division', value: 'IRS Criminal Investigation Division', provenance: 'observed', basis: 'raw', evidence: [2] },
      { kind: 'entity', label: 'Case number', value: '44-IRS-1880', provenance: 'observed', basis: 'raw', evidence: [2, 4] },
      { kind: 'amount', label: 'Card demand', value: '$6,200 in payment cards', provenance: 'observed', basis: 'raw', evidence: [4] },
      { kind: 'entity', label: 'Officer name', value: 'Dana Shah, spelled on the call, roster not checked', provenance: 'unverified', basis: 'raw', evidence: [4] },
      { kind: 'tactic', label: 'Hang-up penalty', value: 'Hanging up is described as executing the warrant', provenance: 'inferred', basis: 'derived', confidence: 0.84, evidence: [6] },
    ],
    correlation: [
      {
        campaignId: IRS,
        campaignName: IRS_NAME,
        score: 0.9,
        summary: 'IRS Warrant Wave match with a new case suffix.',
        explanation: 'Observed 44-IRS-#### and the division line. The officer name is unverified raw speech and was not used as a required indicator.',
        provenance: 'inferred',
        matchedOn: [
          { label: '44-IRS-1880', provenance: 'observed' },
          { label: 'Criminal Investigation Division', provenance: 'observed' },
          { label: 'Payment cards', provenance: 'observed' },
        ],
      },
    ],
  },
  {
    id: 'call_h09',
    startedAt: '2026-09-20T21:06:00.000Z',
    durationMs: minutes(27, 14),
    engagementDurationMs: minutes(24, 0),
    status: 'completed',
    callerNumberMasked: '+1 (415) 555-0190',
    classification: cls('romance', 'unverified', null),
    campaignId: null,
    campaignName: null,
    latency: [530, 920, 350],
    endTitle: 'Caller released',
    endEvent: 'Caller ended the call after the honeypot declined a wire.',
    keyIndicatorIndexes: [1, 2, 3],
    transcript: [
      { offsetMs: 0, speaker: 'honeypot', text: 'Hello?' },
      { offsetMs: 12000, speaker: 'caller', text: 'It is David. My flight is cancelled and customs will not release the bag unless I pay a fee tonight.' },
      { offsetMs: 28000, speaker: 'honeypot', text: 'David who? Where are you calling from?' },
      { offsetMs: 36000, speaker: 'caller', text: 'You know my voice. I am at the airport. I need you to wire eight hundred dollars to the officer here or they hold me overnight.' },
      { offsetMs: 50000, speaker: 'caller', text: '[unclear] ... Western Union ... the name on the slip ...', provenance: 'unverified' },
      { offsetMs: 80000, speaker: 'honeypot', text: 'I am not sending a wire to someone I cannot place. Repeat the full name and the city.' },
      { offsetMs: 90000, speaker: 'caller', text: 'There is no time for a quiz. If you trusted me you would already be at the counter.' },
    ],
    transitions: [
      { offsetMs: 200, from: null, to: 'greeting', reason: 'Honeypot answered.', provenance: 'observed' },
      { offsetMs: 12000, from: 'greeting', to: 'pretext', reason: 'Caller used a first name and an airport-fee story.', provenance: 'unverified' },
      { offsetMs: 36000, from: 'pretext', to: 'payment_request', reason: 'Caller asked for an $800 wire.', provenance: 'inferred' },
    ],
    extraEvents: [
      { offsetMs: 50000, source: 'stt', severity: 'warn', message: 'Caller turn held as unverified; confidence below the commit line', attributes: [{ key: 'confidence', value: '0.38' }] },
    ],
    extraTimeline: [
      { offsetMs: 50000, kind: 'transcript', title: 'Low-confidence turn', detail: 'A possible Western Union mention was not committed as observed text.' },
    ],
    observations: [
      {
        offsetMs: 12000,
        category: 'script',
        raw: observed('Caller said "It is David" and that customs needs a fee tonight.'),
        interpretation: unverified('Could be a romance or acquaintance wire script. No prior relationship is on file, so the framing is not confirmed.'),
      },
      {
        offsetMs: 36000,
        category: 'payment',
        raw: observed('Caller asked for an $800 wire to an officer at the airport.'),
        interpretation: inferred('The payment ask is clear even though the relationship claim is not.'),
      },
      {
        offsetMs: 50000,
        category: 'payment',
        raw: unverified('STT captured fragments that may include Western Union and a name on a slip.'),
        interpretation: null,
      },
    ],
    intelligence: [
      { kind: 'entity', label: 'Spoken name', value: 'David, no surname', provenance: 'observed', basis: 'raw', evidence: [2] },
      { kind: 'amount', label: 'Wire ask', value: '$800 wire', provenance: 'observed', basis: 'raw', evidence: [4] },
      { kind: 'tactic', label: 'Airport hold', value: 'Customs-fee story used to force a same-night wire', provenance: 'unverified', basis: 'derived', evidence: [2, 4] },
      { kind: 'indicator', label: 'Possible wire desk', value: 'Western Union fragments, not committed', provenance: 'unverified', basis: 'raw', evidence: [5] },
    ],
    correlation: [
      {
        campaignId: null,
        campaignName: null,
        score: 0.18,
        summary: 'Left unlinked. Classification is unverified.',
        explanation: 'The wire ask was observed. The personal relationship and the Western Union wording were not. Nothing in the open campaigns uses an airport-fee pretext, so no campaign id was attached.',
        provenance: 'unverified',
        matchedOn: [{ label: '$800 wire', provenance: 'observed' }],
      },
    ],
  },
  {
    id: 'call_h10',
    startedAt: '2026-09-19T10:22:00.000Z',
    durationMs: minutes(8, 2),
    engagementDurationMs: minutes(5, 30),
    status: 'error',
    callerNumberMasked: '+1 (888) 555-0128',
    classification: cls('tech_support', 'inferred', 0.76),
    campaignId: MS,
    campaignName: MS_NAME,
    latency: [460, 680, 1200],
    endTitle: 'TTS fault ended the leg',
    endEvent: 'Playback socket closed before the stall line finished. Telephony cleared the leg.',
    keyIndicatorIndexes: [1, 2, 3],
    transcript: [
      { offsetMs: 0, speaker: 'honeypot', text: 'Hello?' },
      { offsetMs: 8000, speaker: 'caller', text: 'Microsoft Support. We flagged a virus on the licensed PC and a refund is pending if you stay connected.' },
      { offsetMs: 20000, speaker: 'honeypot', text: 'Which refund, and which computer name?' },
      { offsetMs: 28000, speaker: 'caller', text: 'Defender issued it. Do not shut the computer down. I will tell you when to open the remote window.' },
      { offsetMs: 300000, speaker: 'honeypot', text: 'I am writing this down. Start again from the refund amount.' },
    ],
    transitions: [
      { offsetMs: 200, from: null, to: 'greeting', reason: 'Honeypot answered.', provenance: 'observed' },
      { offsetMs: 8000, from: 'greeting', to: 'pretext', reason: 'Caller claimed Microsoft Support, a virus, and a refund.', provenance: 'inferred' },
    ],
    extraEvents: [
      {
        offsetMs: 310000,
        source: 'tts',
        severity: 'error',
        message: 'Playback socket closed before the stall line finished',
        attributes: [
          { key: 'code', value: 'TTS_UNDERRUN' },
          { key: 'utterance', value: 'refund-amount-replay' },
        ],
      },
    ],
    extraTimeline: [
      { offsetMs: 310000, kind: 'error', title: 'TTS underrun', detail: 'Playback died mid prompt. The caller was still in the pretext.' },
    ],
    observations: [
      {
        offsetMs: 8000,
        category: 'script',
        raw: observed('Caller said Microsoft Support, a flagged virus, and a pending refund.'),
        interpretation: inferred('Matches the Microsoft Defender Refund opener. The call died before a tool name or amount.'),
      },
      {
        offsetMs: 310000,
        category: 'other',
        raw: observed('TTS playback socket closed with TTS_UNDERRUN.'),
        interpretation: inferred('The leg ended because of the pipeline, not because the caller hung up.'),
      },
    ],
    intelligence: [
      { kind: 'script_phrase', label: 'Microsoft Support opener', value: 'Microsoft Support', provenance: 'observed', basis: 'raw', evidence: [2] },
      { kind: 'tactic', label: 'Do not shut down', value: 'Caller said not to shut the computer down', provenance: 'observed', basis: 'raw', evidence: [4] },
      { kind: 'indicator', label: 'Remote window pending', value: 'Caller said they would instruct a remote window later', provenance: 'unverified', basis: 'derived', evidence: [4] },
      { kind: 'amount', label: 'Refund amount', value: 'Amount was requested by the honeypot and never spoken', provenance: 'unverified', basis: 'raw', evidence: [5] },
    ],
    correlation: [
      {
        campaignId: MS,
        campaignName: MS_NAME,
        score: 0.73,
        summary: 'Microsoft Defender Refund match, cut short by a TTS fault.',
        explanation: 'Observed Microsoft Support and the do-not-shut-down line. Remote tool and amount never arrived because playback failed.',
        provenance: 'inferred',
        matchedOn: [
          { label: 'Microsoft Support opener', provenance: 'observed' },
          { label: 'Do not shut down', provenance: 'observed' },
        ],
      },
    ],
  },
]

const liveSeeds = [
  {
    id: 'call_live_irs',
    startedOffsetSec: -252,
    engagementDelayMs: 11000,
    callerNumberMasked: '+1 (202) 555-0142',
    classification: cls('irs_impersonation', 'inferred', 0.84),
    campaignId: IRS,
    campaignName: IRS_NAME,
    latency: [380, 640, 290],
    keyIndicatorIndexes: [1, 3, 5],
    transcript: [
      { offsetMs: 0, speaker: 'honeypot', text: 'Hello?' },
      { offsetMs: 8000, speaker: 'caller', text: 'This is Officer Michael Brennan with the IRS Criminal Investigation Division. Am I speaking with the taxpayer of record?' },
      { offsetMs: 20000, speaker: 'honeypot', text: 'Who is this regarding? I want a case number before we continue.' },
      { offsetMs: 28000, speaker: 'caller', text: 'There is a federal warrant in your name. Notices were mailed. Stay on the line.' },
      { offsetMs: 55000, speaker: 'honeypot', text: 'I have not seen a notice. What happens if I hang up?' },
      { offsetMs: 64000, speaker: 'caller', text: 'Local law enforcement is already tasked. You settle this today or they arrive.' },
      { offsetMs: 110000, speaker: 'caller', text: '[unclear] ... payment cards ... read the codes before they expire.', provenance: 'unverified' },
      { offsetMs: 140000, speaker: 'honeypot', text: 'Repeat that last part. I did not catch the amount.' },
    ],
    transitions: [
      { offsetMs: 200, from: null, to: 'greeting', reason: 'Honeypot answered.', provenance: 'observed' },
      { offsetMs: 8000, from: 'greeting', to: 'identity_probe', reason: 'Caller claimed an IRS officer role.', provenance: 'inferred' },
      { offsetMs: 28000, from: 'identity_probe', to: 'pretext', reason: 'Caller introduced a warrant without a case number.', provenance: 'inferred' },
      { offsetMs: 64000, from: 'pretext', to: 'urgency', reason: 'Caller said law enforcement is already tasked.', provenance: 'inferred' },
      { offsetMs: 110000, from: 'urgency', to: 'payment_request', reason: 'A payment-card instruction was only partly recognized.', provenance: 'unverified' },
    ],
    extraTimeline: [
      { offsetMs: 110000, kind: 'transcript', title: 'Unverified payment line', detail: 'STT did not commit the card wording. State moved anyway and is marked unverified.' },
    ],
    extraEvents: [
      { offsetMs: 110000, source: 'stt', severity: 'warn', message: 'Partial transcript below the commit threshold', attributes: [{ key: 'confidence', value: '0.41' }] },
    ],
    observations: [
      {
        offsetMs: 8000,
        category: 'script',
        raw: observed('Caller said Officer Michael Brennan and IRS Criminal Investigation Division.'),
        interpretation: inferred('Division line matches IRS Warrant Wave. The officer name is a repeat of call_h01 and still unchecked.'),
      },
      {
        offsetMs: 64000,
        category: 'threat',
        raw: observed('Caller said local law enforcement is already tasked.'),
        interpretation: inferred('Dispatch pressure is the wave\'s hang-up deterrent.'),
      },
      {
        offsetMs: 110000,
        category: 'payment',
        raw: unverified('Fragments sound like payment cards and reading codes before they expire.'),
        interpretation: unverified('If the fragments are right, this is the gift-card ask. It is not strong enough to treat as observed.'),
      },
    ],
    intelligence: [
      { kind: 'script_phrase', label: 'Criminal Investigation Division', value: 'IRS Criminal Investigation Division', provenance: 'observed', basis: 'raw', evidence: [2] },
      { kind: 'entity', label: 'Officer name', value: 'Michael Brennan, same spoken name as call_h01', provenance: 'observed', basis: 'raw', evidence: [2] },
      { kind: 'tactic', label: 'Dispatch pressure', value: 'Law enforcement described as already tasked', provenance: 'inferred', basis: 'derived', confidence: 0.8, evidence: [6] },
      { kind: 'entity', label: 'Roster check', value: 'Michael Brennan has not been checked against a roster', provenance: 'unverified', basis: 'derived', evidence: [2] },
      { kind: 'script_phrase', label: 'Possible card read-back', value: 'Payment-card wording not committed by STT', provenance: 'unverified', basis: 'raw', evidence: [7] },
    ],
    correlation: [
      {
        campaignId: IRS,
        campaignName: IRS_NAME,
        score: 0.86,
        summary: 'Live match to IRS Warrant Wave.',
        explanation: 'Observed division line and the same officer name as a linked call. The payment-card turn is unverified, so the score is below the completed-call matches that captured an amount.',
        provenance: 'inferred',
        matchedOn: [
          { label: 'Criminal Investigation Division', provenance: 'observed' },
          { label: 'Officer name repeat', provenance: 'observed' },
          { label: 'Possible card read-back', provenance: 'unverified' },
        ],
      },
    ],
  },
  {
    id: 'call_live_ms',
    startedOffsetSec: -96,
    engagementDelayMs: 5000,
    callerNumberMasked: '+1 (888) 555-0199',
    classification: cls('tech_support', 'inferred', 0.78),
    campaignId: MS,
    campaignName: MS_NAME,
    latency: [410, 560, 270],
    keyIndicatorIndexes: [1, 3, 4],
    transcript: [
      { offsetMs: 0, speaker: 'honeypot', text: 'Hello?' },
      { offsetMs: 5000, speaker: 'caller', text: 'Hello, this is Microsoft Support. Your computer reported a critical virus and a refund of three hundred ninety-nine dollars is pending.' },
      { offsetMs: 18000, speaker: 'honeypot', text: 'Microsoft the company? How did you get this number?' },
      { offsetMs: 26000, speaker: 'caller', text: 'We received an alert from your Windows license. Do not shut the computer down or you will lose the refund.' },
      { offsetMs: 48000, speaker: 'honeypot', text: 'I am not in front of that computer. What alert?' },
      { offsetMs: 56000, speaker: 'caller', text: 'The pop-up is from Microsoft Defender. We need to connect and confirm the refund before the window closes.' },
    ],
    transitions: [
      { offsetMs: 200, from: null, to: 'greeting', reason: 'Honeypot answered.', provenance: 'observed' },
      { offsetMs: 5000, from: 'greeting', to: 'pretext', reason: 'Caller claimed Microsoft Support and a $399 refund.', provenance: 'inferred' },
    ],
    extraTimeline: [
      { offsetMs: 56000, kind: 'intel', title: 'Defender named, tool not named', detail: 'Caller mentioned a connection and did not name AnyDesk or another tool yet.' },
    ],
    extraEvents: [],
    observations: [
      {
        offsetMs: 5000,
        category: 'script',
        raw: observed('Caller said "this is Microsoft Support" and a $399 refund is pending.'),
        interpretation: inferred('Opener matches Microsoft Defender Refund.'),
      },
      {
        offsetMs: 56000,
        category: 'tooling',
        raw: observed('Caller said the pop-up is from Microsoft Defender and that they need to connect.'),
        interpretation: unverified('A remote tool is likely next. None has been named on this call.'),
      },
    ],
    intelligence: [
      { kind: 'script_phrase', label: 'Microsoft Support opener', value: 'This is Microsoft Support', provenance: 'observed', basis: 'raw', evidence: [2] },
      { kind: 'amount', label: 'Refund lure', value: '$399 refund', provenance: 'observed', basis: 'raw', evidence: [2] },
      { kind: 'tactic', label: 'Do not shut down', value: 'Shutdown would lose the refund', provenance: 'inferred', basis: 'derived', confidence: 0.83, evidence: [4] },
      { kind: 'indicator', label: 'Remote tool not named', value: 'Caller said "connect" without naming a product', provenance: 'unverified', basis: 'derived', evidence: [6] },
    ],
    correlation: [
      {
        campaignId: MS,
        campaignName: MS_NAME,
        score: 0.8,
        summary: 'Live Microsoft Defender Refund match, still in the opener.',
        explanation: 'Observed Microsoft Support, the $399 figure, and Defender. The remote-tool step has not happened, so the score trails call_h03.',
        provenance: 'inferred',
        matchedOn: [
          { label: 'Microsoft Support opener', provenance: 'observed' },
          { label: '$399 refund', provenance: 'observed' },
          { label: 'Microsoft Defender', provenance: 'observed' },
        ],
      },
    ],
  },
  {
    id: 'call_live_chase',
    startedOffsetSec: -680,
    engagementDelayMs: 6000,
    callerNumberMasked: '+1 (800) 555-0174',
    classification: cls('bank_fraud', 'inferred', 0.94),
    campaignId: CHASE,
    campaignName: CHASE_NAME,
    latency: [350, 710, 305],
    keyIndicatorIndexes: [1, 4, 5],
    transcript: [
      { offsetMs: 0, speaker: 'honeypot', text: 'Hello?' },
      { offsetMs: 4000, speaker: 'caller', text: 'This is the Chase fraud department. We detected a Zelle transfer of two thousand four hundred dollars from your account.' },
      { offsetMs: 16000, speaker: 'honeypot', text: 'I do not remember sending a Zelle transfer. Who am I speaking with?' },
      { offsetMs: 24000, speaker: 'caller', text: 'Fraud desk, badge four four one. The payment is reversible if you verify the one-time code we texted.' },
      { offsetMs: 48000, speaker: 'honeypot', text: 'I have not looked at my phone. What happens after the code?' },
      { offsetMs: 56000, speaker: 'caller', text: 'We move the remaining balance into a safe account in your name and reverse the Zelle. I need the code and the last four of the debit card.' },
      { offsetMs: 300000, speaker: 'honeypot', text: 'I am writing that down. Say the amount again, and do not ask me to read a code yet.' },
      { offsetMs: 312000, speaker: 'caller', text: 'Two thousand four hundred dollars, Zelle, pending. The safe account is already open on our side. Do not call the branch.' },
    ],
    transitions: [
      { offsetMs: 200, from: null, to: 'greeting', reason: 'Honeypot answered.', provenance: 'observed' },
      { offsetMs: 4000, from: 'greeting', to: 'pretext', reason: 'Caller claimed Chase fraud and a $2,400 Zelle debit.', provenance: 'inferred' },
      { offsetMs: 24000, from: 'pretext', to: 'payment_request', reason: 'Caller asked the target to verify a one-time code.', provenance: 'inferred' },
    ],
    extraTimeline: [
      { offsetMs: 56000, kind: 'intel', title: 'Safe account and last four', detail: 'Caller tied the reversal to a safe account plus the debit last four.' },
    ],
    extraEvents: [
      { offsetMs: 24000, source: 'orchestrator', severity: 'warn', message: 'One-time-code request detected; persona instructed to stall', attributes: [{ key: 'policy', value: 'no-otp-readback' }] },
    ],
    observations: [
      {
        offsetMs: 4000,
        category: 'script',
        raw: observed('Caller said "Chase fraud department" and a Zelle transfer of $2,400.'),
        interpretation: inferred('Full opener for Chase Fraud Desk.'),
      },
      {
        offsetMs: 24000,
        category: 'identity',
        raw: unverified('Caller said badge four four one. The digits were clear enough to record and have not been checked.'),
        interpretation: null,
      },
      {
        offsetMs: 56000,
        category: 'payment',
        raw: observed('Caller asked for a one-time code and the last four, and described a safe account.'),
        interpretation: inferred('Safe-account language is the mule handoff used on call_h05.'),
      },
    ],
    intelligence: [
      { kind: 'script_phrase', label: 'Chase fraud department', value: 'This is the Chase fraud department', provenance: 'observed', basis: 'raw', evidence: [2] },
      { kind: 'amount', label: 'Zelle amount', value: '$2,400 Zelle transfer', provenance: 'observed', basis: 'raw', evidence: [2, 8] },
      { kind: 'indicator', label: 'OTP read-back', value: 'Caller asked the target to verify a one-time code', provenance: 'observed', basis: 'raw', evidence: [4] },
      { kind: 'tactic', label: 'Safe account', value: 'Remaining balance moved to a safe account already open on their side', provenance: 'inferred', basis: 'derived', confidence: 0.93, evidence: [6, 8] },
      { kind: 'entity', label: 'Badge 441', value: 'Spoken badge 441, not checked', provenance: 'unverified', basis: 'raw', evidence: [4] },
    ],
    correlation: [
      {
        campaignId: CHASE,
        campaignName: CHASE_NAME,
        score: 0.95,
        summary: 'Live Chase Fraud Desk match.',
        explanation: 'Observed Chase opener, $2,400 Zelle, and an OTP ask. Safe-account wording matches call_h05. Badge 441 is unverified and was not required for the score.',
        provenance: 'inferred',
        matchedOn: [
          { label: 'Chase fraud department', provenance: 'observed' },
          { label: '$2,400 Zelle', provenance: 'observed' },
          { label: 'Safe account', provenance: 'inferred' },
          { label: 'Badge 441', provenance: 'unverified' },
        ],
      },
    ],
  },
]

function buckets(rows) {
  return rows.map(([day, hour, count]) => ({ day, hour, count }))
}

const irsActivity = buckets([
  ['2026-09-19', 14, 2],
  ['2026-09-19', 15, 3],
  ['2026-09-21', 15, 4],
  ['2026-09-21', 16, 2],
  ['2026-09-22', 13, 1],
  ['2026-09-22', 14, 3],
  ['2026-09-23', 14, 2],
  ['2026-09-23', 15, 2],
  ['2026-09-24', 13, 2],
  ['2026-09-24', 15, 1],
  ['2026-09-25', 11, 1],
  ['2026-09-25', 14, 2],
  ['2026-09-25', 20, 1],
])

const msActivity = buckets([
  ['2026-09-19', 10, 3],
  ['2026-09-20', 9, 2],
  ['2026-09-20', 10, 2],
  ['2026-09-21', 9, 1],
  ['2026-09-22', 11, 2],
  ['2026-09-23', 16, 1],
  ['2026-09-24', 9, 2],
  ['2026-09-24', 16, 3],
  ['2026-09-25', 15, 1],
  ['2026-09-25', 20, 1],
])

const chaseActivity = buckets([
  ['2026-09-20', 19, 2],
  ['2026-09-21', 20, 1],
  ['2026-09-22', 18, 2],
  ['2026-09-22', 19, 1],
  ['2026-09-23', 13, 1],
  ['2026-09-23', 19, 3],
  ['2026-09-24', 18, 2],
  ['2026-09-24', 21, 1],
  ['2026-09-25', 20, 2],
])

function sumCounts(activity) {
  return activity.reduce((total, bucket) => total + bucket.count, 0)
}

const campaigns = [
  {
    id: IRS,
    name: IRS_NAME,
    status: 'active',
    classification: cls('irs_impersonation', 'inferred', 0.9),
    firstSeenAt: '2026-09-19T14:12:00.000Z',
    lastSeenAt: '2026-09-25T20:05:00.000Z',
    callCount: sumCounts(irsActivity),
    summary: 'Callers pose as IRS Criminal Investigation Division officers, cite a 44-IRS case number, and push retail payment-card codes under a warrant threat. Officer names repeat and are not on a checked roster.',
    relatedCallIds: ['call_live_irs', 'call_h01', 'call_h02', 'call_h08'],
    timeline: [
      { id: 'camp_irs_tl1', at: '2026-09-19T14:12:00.000Z', title: 'Wave opened', detail: 'First calls with the Criminal Investigation Division line and a 44-IRS case pattern.' },
      { id: 'camp_irs_tl2', at: '2026-09-21T15:44:00.000Z', title: 'Second officer name', detail: 'Dana Shah spelled on call_h08. Case suffix 1880. Payment path unchanged.' },
      { id: 'camp_irs_tl3', at: '2026-09-25T11:40:00.000Z', title: 'Badge challenge drop', detail: 'call_h02 abandoned when the honeypot asked for a badge number.' },
      { id: 'camp_irs_tl4', at: '2026-09-25T14:20:00.000Z', title: 'Full script captured', detail: 'call_h01 reached an $8,400 card read-back and a warning not to call a local IRS office.' },
    ],
    commonScriptPhrases: [
      { id: 'camp_irs_p1', kind: 'script_phrase', label: 'Division line', value: 'IRS Criminal Investigation Division', provenance: 'observed', basis: 'raw', confidence: null, evidenceTurnIds: [] },
      { id: 'camp_irs_p2', kind: 'script_phrase', label: 'Case pattern', value: 'Case 44-IRS-####', provenance: 'observed', basis: 'raw', confidence: null, evidenceTurnIds: [] },
      { id: 'camp_irs_p3', kind: 'script_phrase', label: 'Hang-up penalty', value: 'Hanging up executes the warrant or brings dispatch', provenance: 'inferred', basis: 'derived', confidence: 0.87, evidenceTurnIds: [] },
      { id: 'camp_irs_p4', kind: 'script_phrase', label: 'Card wording', value: 'Government payment cards, codes read back on the call', provenance: 'unverified', basis: 'derived', confidence: null, evidenceTurnIds: [] },
    ],
    sharedIndicators: [
      { id: 'camp_irs_s1', kind: 'indicator', label: 'Spoofed DC calling number', value: '+1 (202) 555-01xx on linked calls', provenance: 'observed', basis: 'raw', confidence: null, evidenceTurnIds: [] },
      { id: 'camp_irs_s2', kind: 'tactic', label: 'Warrant pressure', value: 'A federal warrant is named before any document is offered', provenance: 'inferred', basis: 'derived', confidence: 0.89, evidenceTurnIds: [] },
      { id: 'camp_irs_s3', kind: 'entity', label: 'Repeated officer name', value: 'Michael Brennan appears on more than one call and is not roster-checked', provenance: 'unverified', basis: 'derived', confidence: null, evidenceTurnIds: [] },
      { id: 'camp_irs_s4', kind: 'amount', label: 'Card amounts', value: 'Spoken demands include $8,400 and $6,200', provenance: 'observed', basis: 'raw', confidence: null, evidenceTurnIds: [] },
    ],
    similarity: [
      { callId: 'call_h01', score: 0.92, explanation: 'Full script: division line, 44-IRS-2291, dispatch threat, and an $8,400 card read-back.', provenance: 'inferred' },
      { callId: 'call_h08', score: 0.9, explanation: 'Same case pattern with suffix 1880 and a $6,200 card demand. Officer name differs.', provenance: 'inferred' },
      { callId: 'call_live_irs', score: 0.86, explanation: 'Live call repeats the Brennan name and division line. The card ask is only an unverified STT fragment.', provenance: 'inferred' },
      { callId: 'call_h02', score: 0.74, explanation: 'Warrant opener only. Caller dropped when asked for a badge number, before a case id or amount.', provenance: 'inferred' },
    ],
    activity: irsActivity,
  },
  {
    id: MS,
    name: MS_NAME,
    status: 'active',
    classification: cls('tech_support', 'inferred', 0.86),
    firstSeenAt: '2026-09-19T10:22:00.000Z',
    lastSeenAt: '2026-09-25T19:40:00.000Z',
    callCount: sumCounts(msActivity),
    summary: 'Callers claim Microsoft Support, warn that shutting down cancels a $399 Defender refund, and move toward a remote session. AnyDesk was named on one completed call.',
    relatedCallIds: ['call_live_ms', 'call_h03', 'call_h04', 'call_h10'],
    timeline: [
      { id: 'camp_ms_tl1', at: '2026-09-19T10:22:00.000Z', title: 'First refund opener', detail: 'call_h10 matched the opener and then died on a TTS underrun.' },
      { id: 'camp_ms_tl2', at: '2026-09-24T09:12:00.000Z', title: 'Stall drop', detail: 'call_h04 abandoned while the honeypot stayed away from the computer.' },
      { id: 'camp_ms_tl3', at: '2026-09-24T16:18:00.000Z', title: 'AnyDesk named', detail: 'call_h03 asked for an AnyDesk session. The honeypot did not connect. Digits were not committed.' },
      { id: 'camp_ms_tl4', at: '2026-09-25T19:50:00.000Z', title: 'Live opener', detail: 'A new call is in pretext with the $399 refund and no tool name yet.' },
    ],
    commonScriptPhrases: [
      { id: 'camp_ms_p1', kind: 'script_phrase', label: 'Support opener', value: 'This is Microsoft Support', provenance: 'observed', basis: 'raw', confidence: null, evidenceTurnIds: [] },
      { id: 'camp_ms_p2', kind: 'script_phrase', label: 'Refund lure', value: 'A $399 refund is pending or waiting', provenance: 'observed', basis: 'raw', confidence: null, evidenceTurnIds: [] },
      { id: 'camp_ms_p3', kind: 'script_phrase', label: 'Shutdown warning', value: 'Do not shut the computer down', provenance: 'inferred', basis: 'derived', confidence: 0.85, evidenceTurnIds: [] },
      { id: 'camp_ms_p4', kind: 'script_phrase', label: 'Remote session', value: 'Connect with a remote tool to confirm the refund', provenance: 'unverified', basis: 'derived', confidence: null, evidenceTurnIds: [] },
    ],
    sharedIndicators: [
      { id: 'camp_ms_s1', kind: 'indicator', label: 'Toll-free caller id', value: '+1 (888) 555-01xx on linked calls', provenance: 'observed', basis: 'raw', confidence: null, evidenceTurnIds: [] },
      { id: 'camp_ms_s2', kind: 'entity', label: 'Product lure', value: 'Microsoft Defender pop-up or subscription', provenance: 'observed', basis: 'raw', confidence: null, evidenceTurnIds: [] },
      { id: 'camp_ms_s3', kind: 'tactic', label: 'Refund keeps the line up', value: 'The refund is the reason given for not ending the call', provenance: 'inferred', basis: 'derived', confidence: 0.84, evidenceTurnIds: [] },
      { id: 'camp_ms_s4', kind: 'entity', label: 'AnyDesk address', value: 'Nine digits were requested once and not confirmed', provenance: 'unverified', basis: 'raw', confidence: null, evidenceTurnIds: [] },
    ],
    similarity: [
      { callId: 'call_h03', score: 0.94, explanation: 'Full path through Defender and an AnyDesk request. Address digits remain unverified.', provenance: 'inferred' },
      { callId: 'call_live_ms', score: 0.8, explanation: 'Live opener with the $399 refund and Defender. No tool name yet.', provenance: 'inferred' },
      { callId: 'call_h10', score: 0.73, explanation: 'Same opener, ended by TTS_UNDERRUN before a tool or amount.', provenance: 'inferred' },
      { callId: 'call_h04', score: 0.71, explanation: 'Defender refund and a one-hour deadline. Caller left during the walk-to-the-PC stall.', provenance: 'inferred' },
    ],
    activity: msActivity,
  },
  {
    id: CHASE,
    name: CHASE_NAME,
    status: 'active',
    classification: cls('bank_fraud', 'inferred', 0.93),
    firstSeenAt: '2026-09-20T19:05:00.000Z',
    lastSeenAt: '2026-09-25T20:10:00.000Z',
    callCount: sumCounts(chaseActivity),
    summary: 'Callers impersonate a Chase fraud desk, cite a $2,400 Zelle transfer, and ask for a one-time code plus the debit last four so funds can move to a safe account.',
    relatedCallIds: ['call_live_chase', 'call_h05', 'call_h06'],
    timeline: [
      { id: 'camp_chase_tl1', at: '2026-09-20T19:05:00.000Z', title: 'Evening cluster started', detail: 'First Zelle-reversal calls, concentrated after 18:00 UTC.' },
      { id: 'camp_chase_tl2', at: '2026-09-23T13:02:00.000Z', title: 'Card-number challenge', detail: 'call_h06 died when the honeypot moved to dial the number on the card.' },
      { id: 'camp_chase_tl3', at: '2026-09-23T19:48:00.000Z', title: 'Safe account captured', detail: 'call_h05 recorded the OTP ask and the safe-account handoff. The honeypot refused the code.' },
      { id: 'camp_chase_tl4', at: '2026-09-25T20:00:00.000Z', title: 'Live replay', detail: 'An active call repeats the $2,400 Zelle script and badge 441, which is not checked.' },
    ],
    commonScriptPhrases: [
      { id: 'camp_chase_p1', kind: 'script_phrase', label: 'Desk opener', value: 'This is the Chase fraud department', provenance: 'observed', basis: 'raw', confidence: null, evidenceTurnIds: [] },
      { id: 'camp_chase_p2', kind: 'script_phrase', label: 'Zelle debit', value: 'We detected a Zelle transfer', provenance: 'observed', basis: 'raw', confidence: null, evidenceTurnIds: [] },
      { id: 'camp_chase_p3', kind: 'script_phrase', label: 'Safe account', value: 'Move the remaining balance into a safe account in your name', provenance: 'inferred', basis: 'derived', confidence: 0.92, evidenceTurnIds: [] },
      { id: 'camp_chase_p4', kind: 'script_phrase', label: 'Badge claim', value: 'Fraud desk badge number spoken on some calls', provenance: 'unverified', basis: 'raw', confidence: null, evidenceTurnIds: [] },
    ],
    sharedIndicators: [
      { id: 'camp_chase_s1', kind: 'amount', label: 'Zelle figure', value: '$2,400 on calls that reach the amount', provenance: 'observed', basis: 'raw', confidence: null, evidenceTurnIds: [] },
      { id: 'camp_chase_s2', kind: 'indicator', label: 'OTP ask', value: 'Target is told to read a texted one-time code', provenance: 'observed', basis: 'raw', confidence: null, evidenceTurnIds: [] },
      { id: 'camp_chase_s3', kind: 'tactic', label: 'Mule handoff', value: 'Safe account is treated as the reversal path', provenance: 'inferred', basis: 'derived', confidence: 0.9, evidenceTurnIds: [] },
      { id: 'camp_chase_s4', kind: 'entity', label: 'Badge 441', value: 'Spoken on the live call, not checked', provenance: 'unverified', basis: 'raw', confidence: null, evidenceTurnIds: [] },
      { id: 'camp_chase_s5', kind: 'tactic', label: 'Avoid the real bank', value: 'Caller says not to use the number on the card or the branch', provenance: 'observed', basis: 'raw', confidence: null, evidenceTurnIds: [] },
    ],
    similarity: [
      { callId: 'call_h05', score: 0.96, explanation: 'Completed path: Zelle amount, OTP refusal, and the safe-account sentence.', provenance: 'inferred' },
      { callId: 'call_live_chase', score: 0.95, explanation: 'Live call repeats the $2,400 script. Badge 441 is unverified raw speech.', provenance: 'inferred' },
      { callId: 'call_h06', score: 0.62, explanation: 'Opener only. No amount. Caller left when the honeypot turned to the number on the card.', provenance: 'inferred' },
    ],
    activity: chaseActivity,
  },
]

const systemHealth = {
  sampledAt: '2026-09-25T20:15:00.000Z',
  providers: [
    { id: 'prov_voice', name: 'Northline Voice', role: 'telephony', status: 'ok', latencyMs: 42, detail: 'Inbound legs answering. No queue on the honeypot trunk.' },
    { id: 'prov_stt', name: 'Harbor STT', role: 'stt', status: 'degraded', latencyMs: 820, detail: 'Partials are late. Two turns in the last hour stayed under the commit threshold.' },
    { id: 'prov_tts', name: 'Keel TTS', role: 'tts', status: 'ok', latencyMs: 260, detail: 'Current playback is healthy. TTS_UNDERRUN on 19 Sep is closed.' },
    { id: 'prov_llm', name: 'Ledger LLM', role: 'llm', status: 'ok', latencyMs: 610, detail: 'Stall persona replies are inside the display budget.' },
  ],
  latency: { sttMs: 820, llmMs: 610, ttsMs: 260, e2eMs: 1730 },
  concurrency: { activeCalls: 3, capacity: 25, queueDepth: 0 },
  cost: {
    windowLabel: 'Last 24 hours',
    currency: 'USD',
    stt: 18.4,
    tts: 6.15,
    llm: 22.8,
    telephony: 11.05,
  },
  errors: [
    { id: 'err_tts_h10', at: '2026-09-19T10:27:10.000Z', source: 'Keel TTS', severity: 'error', message: 'TTS_UNDERRUN closed the playback socket on call_h10.' },
    { id: 'err_stt_live', at: '2026-09-25T20:11:40.000Z', source: 'Harbor STT', severity: 'warn', message: 'Unverified partial on call_live_irs at the payment-card turn.' },
    { id: 'err_stt_h09', at: '2026-09-20T21:06:50.000Z', source: 'Harbor STT', severity: 'warn', message: 'Western Union fragment on call_h09 was kept unverified.' },
  ],
}

const history = historySeeds.map(expandHistory)
const live = liveSeeds.map(expandLive)

mkdirSync(outDir, { recursive: true })
writeFileSync(join(outDir, 'call-details.json'), `${JSON.stringify(history, null, 2)}\n`)
writeFileSync(join(outDir, 'live-calls.json'), `${JSON.stringify(live.map((item) => item.board), null, 2)}\n`)
writeFileSync(join(outDir, 'live-detail-extras.json'), `${JSON.stringify(live.map((item) => item.extra), null, 2)}\n`)
writeFileSync(join(outDir, 'campaign-details.json'), `${JSON.stringify(campaigns, null, 2)}\n`)
writeFileSync(join(outDir, 'system-health.json'), `${JSON.stringify(systemHealth, null, 2)}\n`)

console.log(`Wrote fixtures to ${outDir}`)
console.log(`history=${history.length} live=${live.length} campaigns=${campaigns.length}`)
console.log(`call counts: irs=${sumCounts(irsActivity)} ms=${sumCounts(msActivity)} chase=${sumCounts(chaseActivity)}`)
