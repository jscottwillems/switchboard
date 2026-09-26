import { apiBaseUrl, operatorAuthHeaders } from '@/data/apiConfig'
import type {
  CallDetailResponse,
  CallListResponse,
  CallSession,
  CallSessionSummary,
  CampaignAttribution,
  ConversationTurn,
  IntelligenceFinding,
  MediaStream,
  TranscriptSegment,
} from '@switchboard/schemas'

const CALL_STATES = ['ringing', 'in_progress', 'completed', 'failed'] as const
const MEDIA_STATES = ['connecting', 'streaming', 'closed', 'failed'] as const
const SPEAKERS = ['caller', 'honeypot'] as const
const SOURCES = ['stt', 'tts_input'] as const
const FINDING_KINDS = [
  'callback_number',
  'pretext',
  'organization_name',
  'payment_method',
  'url',
  'person_name',
  'other',
] as const
const FINDING_STATUSES = ['proposed', 'accepted', 'rejected'] as const
const PAGE_LIMIT = 200
const MAX_PAGES = 20

export class CallsReadError extends Error {
  readonly code: string
  readonly status: number | null

  constructor(code: string, message: string, status: number | null = null) {
    super(message)
    this.name = 'CallsReadError'
    this.code = code
    this.status = status
  }
}

function fail(ctx: string, message: string): never {
  throw new CallsReadError('invalid_request', `${ctx}: ${message}`)
}

function record(value: unknown, ctx: string): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) fail(ctx, 'expected an object')
  return value as Record<string, unknown>
}

function array(value: unknown, ctx: string): unknown[] {
  if (!Array.isArray(value)) fail(ctx, 'expected an array')
  return value
}

function text(source: Record<string, unknown>, key: string, ctx: string, allowEmpty = false): string {
  const value = source[key]
  if (typeof value !== 'string') fail(ctx, `${key} must be a string`)
  if (!allowEmpty && value.length === 0) fail(ctx, `${key} must be a non-empty string`)
  return value
}

function nullableText(source: Record<string, unknown>, key: string, ctx: string): string | null {
  const value = source[key]
  if (value === null) return null
  if (typeof value !== 'string') fail(ctx, `${key} must be a string or null`)
  return value
}

function numberValue(source: Record<string, unknown>, key: string, ctx: string): number {
  const value = source[key]
  if (typeof value !== 'number' || Number.isNaN(value)) fail(ctx, `${key} must be a number`)
  return value
}

function score(source: Record<string, unknown>, key: string, ctx: string): number {
  const value = numberValue(source, key, ctx)
  if (value < 0 || value > 1) fail(ctx, `${key} must be 0..1`)
  return value
}

function nullableScore(source: Record<string, unknown>, key: string, ctx: string): number | null {
  const value = source[key]
  if (value === null) return null
  return score(source, key, ctx)
}

function booleanValue(source: Record<string, unknown>, key: string, ctx: string): boolean {
  const value = source[key]
  if (typeof value !== 'boolean') fail(ctx, `${key} must be a boolean`)
  return value
}

function oneOf<T extends string>(
  source: Record<string, unknown>,
  key: string,
  allowed: readonly T[],
  ctx: string,
): T {
  const value = text(source, key, ctx)
  if (!(allowed as readonly string[]).includes(value)) fail(ctx, `${key} has unexpected value ${value}`)
  return value as T
}

function stringList(value: unknown, ctx: string, minLength: number): string[] {
  const items = array(value, ctx).map((item, index) => {
    if (typeof item !== 'string' || item.length === 0) fail(ctx, `[${index}] must be a string`)
    return item
  })
  if (items.length < minLength) fail(ctx, `expected at least ${minLength} entries`)
  return items
}

function requireLayer(source: Record<string, unknown>, expected: string, ctx: string): void {
  const layer = text(source, 'record_layer', ctx)
  if (layer !== expected) fail(ctx, `record_layer must be ${expected}`)
}

function parseSummary(value: unknown, ctx: string): CallSessionSummary {
  const source = record(value, ctx)
  return {
    id: text(source, 'id', ctx),
    state: oneOf(source, 'state', CALL_STATES, ctx),
    caller_number_e164: text(source, 'caller_number_e164', ctx),
    called_number_e164: text(source, 'called_number_e164', ctx),
    started_at: text(source, 'started_at', ctx),
    ended_at: nullableText(source, 'ended_at', ctx),
  }
}

function parseList(value: unknown): CallListResponse {
  const source = record(value, 'CallListResponse')
  const next = source.next_cursor
  if (next !== null && (typeof next !== 'string' || next.length === 0)) {
    fail('CallListResponse', 'next_cursor must be a string or null')
  }
  return {
    items: array(source.items, 'CallListResponse.items').map((item, index) =>
      parseSummary(item, `CallListResponse.items[${index}]`),
    ),
    next_cursor: next,
  }
}

function parseSession(value: unknown, ctx: string): CallSession {
  const source = record(value, ctx)
  requireLayer(source, 'observation', ctx)
  return {
    record_layer: 'observation',
    id: text(source, 'id', ctx),
    operator_number_id: nullableText(source, 'operator_number_id', ctx),
    external_call_id: text(source, 'external_call_id', ctx),
    carrier: text(source, 'carrier', ctx),
    caller_number_e164: text(source, 'caller_number_e164', ctx),
    called_number_e164: text(source, 'called_number_e164', ctx),
    state: oneOf(source, 'state', CALL_STATES, ctx),
    started_at: text(source, 'started_at', ctx),
    answered_at: nullableText(source, 'answered_at', ctx),
    ended_at: nullableText(source, 'ended_at', ctx),
    end_reason: nullableText(source, 'end_reason', ctx),
  }
}

function parseMedia(value: unknown, ctx: string): MediaStream {
  const source = record(value, ctx)
  requireLayer(source, 'observation', ctx)
  if (text(source, 'protocol', ctx) !== 'switchboard.media.v1') fail(ctx, 'protocol')
  const encoding = text(source, 'encoding', ctx)
  if (encoding !== 'audio/pcmu' && encoding !== 'audio/pcm') fail(ctx, 'encoding')
  return {
    record_layer: 'observation',
    id: text(source, 'id', ctx),
    call_session_id: text(source, 'call_session_id', ctx),
    external_stream_id: text(source, 'external_stream_id', ctx),
    protocol: 'switchboard.media.v1',
    encoding,
    sample_rate_hz: numberValue(source, 'sample_rate_hz', ctx),
    state: oneOf(source, 'state', MEDIA_STATES, ctx),
    started_at: text(source, 'started_at', ctx),
    ended_at: nullableText(source, 'ended_at', ctx),
  }
}

function parseSegment(value: unknown, ctx: string): TranscriptSegment {
  const source = record(value, ctx)
  requireLayer(source, 'observation', ctx)
  return {
    record_layer: 'observation',
    id: text(source, 'id', ctx),
    call_session_id: text(source, 'call_session_id', ctx),
    media_stream_id: text(source, 'media_stream_id', ctx),
    sequence: numberValue(source, 'sequence', ctx),
    speaker: oneOf(source, 'speaker', SPEAKERS, ctx),
    source: oneOf(source, 'source', SOURCES, ctx),
    text: text(source, 'text', ctx, true),
    language: nullableText(source, 'language', ctx),
    start_offset_ms: numberValue(source, 'start_offset_ms', ctx),
    end_offset_ms: numberValue(source, 'end_offset_ms', ctx),
    is_final: booleanValue(source, 'is_final', ctx),
    stt_confidence: nullableScore(source, 'stt_confidence', ctx),
    provider: text(source, 'provider', ctx),
    created_at: text(source, 'created_at', ctx),
  }
}

function parseTurn(value: unknown, ctx: string): ConversationTurn {
  const source = record(value, ctx)
  requireLayer(source, 'interpretation', ctx)
  return {
    record_layer: 'interpretation',
    id: text(source, 'id', ctx),
    call_session_id: text(source, 'call_session_id', ctx),
    turn_index: numberValue(source, 'turn_index', ctx),
    speaker: oneOf(source, 'speaker', SPEAKERS, ctx),
    text: text(source, 'text', ctx, true),
    transcript_segment_ids: stringList(source.transcript_segment_ids, `${ctx}.transcript_segment_ids`, 0),
    strategy_id: nullableText(source, 'strategy_id', ctx),
    confidence: score(source, 'confidence', ctx),
    created_at: text(source, 'created_at', ctx),
  }
}

function parseFinding(value: unknown, ctx: string): IntelligenceFinding {
  const source = record(value, ctx)
  requireLayer(source, 'interpretation', ctx)
  return {
    record_layer: 'interpretation',
    id: text(source, 'id', ctx),
    call_session_id: text(source, 'call_session_id', ctx),
    kind: oneOf(source, 'kind', FINDING_KINDS, ctx),
    value: text(source, 'value', ctx),
    raw_quote: text(source, 'raw_quote', ctx),
    transcript_segment_ids: stringList(source.transcript_segment_ids, `${ctx}.transcript_segment_ids`, 1),
    extractor: text(source, 'extractor', ctx),
    extractor_version: text(source, 'extractor_version', ctx),
    confidence: score(source, 'confidence', ctx),
    status: oneOf(source, 'status', FINDING_STATUSES, ctx),
    created_at: text(source, 'created_at', ctx),
  }
}

function parseAttribution(value: unknown, ctx: string): CampaignAttribution {
  const source = record(value, ctx)
  requireLayer(source, 'attribution', ctx)
  return {
    record_layer: 'attribution',
    id: text(source, 'id', ctx),
    campaign_id: text(source, 'campaign_id', ctx),
    call_session_id: text(source, 'call_session_id', ctx),
    supporting_finding_ids: stringList(source.supporting_finding_ids, `${ctx}.supporting_finding_ids`, 1),
    method: text(source, 'method', ctx),
    method_version: text(source, 'method_version', ctx),
    confidence: score(source, 'confidence', ctx),
    rationale: text(source, 'rationale', ctx),
    created_at: text(source, 'created_at', ctx),
  }
}

function parseDetail(value: unknown): CallDetailResponse {
  const source = record(value, 'CallDetailResponse')
  return {
    session: parseSession(source.session, 'CallDetailResponse.session'),
    media_streams: array(source.media_streams, 'CallDetailResponse.media_streams').map((item, index) =>
      parseMedia(item, `CallDetailResponse.media_streams[${index}]`),
    ),
    transcript: array(source.transcript, 'CallDetailResponse.transcript').map((item, index) =>
      parseSegment(item, `CallDetailResponse.transcript[${index}]`),
    ),
    turns: array(source.turns, 'CallDetailResponse.turns').map((item, index) =>
      parseTurn(item, `CallDetailResponse.turns[${index}]`),
    ),
    findings: array(source.findings, 'CallDetailResponse.findings').map((item, index) =>
      parseFinding(item, `CallDetailResponse.findings[${index}]`),
    ),
    attributions: array(source.attributions, 'CallDetailResponse.attributions').map((item, index) =>
      parseAttribution(item, `CallDetailResponse.attributions[${index}]`),
    ),
  }
}

interface ErrorBody {
  error: string
  message: string
}

async function readErrorBody(response: Response): Promise<ErrorBody> {
  try {
    const body: unknown = await response.json()
    const source = record(body, 'ErrorBody')
    const error = text(source, 'error', 'ErrorBody')
    const messageValue = source.message
    const message = typeof messageValue === 'string' && messageValue.length > 0 ? messageValue : error
    return { error, message }
  } catch {
    return { error: 'calls_unreachable', message: 'the read API did not respond.' }
  }
}

async function getJson(path: string): Promise<{ status: number; body: unknown }> {
  const url = `${apiBaseUrl()}${path}`
  let response: Response
  try {
    response = await fetch(url, {
      headers: { Accept: 'application/json', ...operatorAuthHeaders() },
    })
  } catch {
    throw new CallsReadError('calls_unreachable', 'calls_unreachable: the read API did not respond.')
  }
  if (response.status === 404) {
    const errorBody = await readErrorBody(response)
    if (errorBody.error === 'call_not_found') {
      throw new CallsReadError('call_not_found', errorBody.message, 404)
    }
    throw new CallsReadError(errorBody.error, `${errorBody.error}: ${errorBody.message}`, response.status)
  }
  if (!response.ok) {
    const errorBody = await readErrorBody(response)
    const code = errorBody.error === 'calls_unreachable' ? 'calls_unreachable' : errorBody.error
    throw new CallsReadError(code, `${code}: ${errorBody.message}`, response.status)
  }
  try {
    return { status: response.status, body: await response.json() }
  } catch {
    throw new CallsReadError('invalid_request', 'invalid_request: the read API returned a body that is not JSON.')
  }
}

export async function listCallSummaries(): Promise<CallSessionSummary[]> {
  const items: CallSessionSummary[] = []
  let cursor: string | null = null
  for (let page = 0; page < MAX_PAGES; page += 1) {
    const query = new URLSearchParams({ limit: String(PAGE_LIMIT) })
    if (cursor) query.set('cursor', cursor)
    const response = await getJson(`/v1/calls?${query.toString()}`)
    const parsed = parseList(response.body)
    items.push(...parsed.items)
    if (!parsed.next_cursor) return items
    cursor = parsed.next_cursor
  }
  throw new CallsReadError('invalid_request', 'invalid_request: the call list exceeded the dashboard page cap.')
}

export async function getCallDetail(callId: string): Promise<CallDetailResponse | null> {
  try {
    const response = await getJson(`/v1/calls/${encodeURIComponent(callId)}`)
    return parseDetail(response.body)
  } catch (caught) {
    if (caught instanceof CallsReadError && caught.code === 'call_not_found') return null
    throw caught
  }
}
