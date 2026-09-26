import assert from 'node:assert/strict'

import { detailFromResponse, liveFromDetail, summaryFromListItem } from '../src/data/mapCall.ts'

const nowMs = Date.parse('2026-09-25T21:00:00Z')

const summary = summaryFromListItem(
  {
    id: '6c0d5a2e-0000-5000-8000-000000000001',
    state: 'completed',
    caller_number_e164: '+15551212000',
    called_number_e164: '+15550001001',
    started_at: '2026-09-25T20:00:00Z',
    ended_at: '2026-09-25T20:00:10Z',
  },
  nowMs,
)

assert.equal(summary.session.record_layer, 'observation')
assert.equal(summary.session.external_call_id, '')
assert.equal(summary.session.state, 'completed')
assert.equal(summary.gaps.duration_ms, 10_000)
assert.equal(summary.gaps.engagement_duration_ms, null)
assert.equal(summary.gaps.campaign_id, null)
assert.equal(summary.gaps.conversation_state, null)
assert.equal(summary.gaps.classification.label, 'unknown')
assert.equal(summary.key_findings.length, 0)

const detail = detailFromResponse(
  {
    session: {
      record_layer: 'observation',
      id: '6c0d5a2e-0000-5000-8000-000000000002',
      operator_number_id: null,
      external_call_id: 'demo-1',
      carrier: 'mock',
      caller_number_e164: '+15551212000',
      called_number_e164: '+15550001001',
      state: 'completed',
      started_at: '2026-09-25T20:00:00.000Z',
      answered_at: '2026-09-25T20:00:02.000Z',
      ended_at: '2026-09-25T20:00:10.000Z',
      end_reason: 'hangup',
    },
    media_streams: [],
    transcript: [
      {
        record_layer: 'observation',
        id: 'seg-1',
        call_session_id: '6c0d5a2e-0000-5000-8000-000000000002',
        media_stream_id: 'stream-1',
        sequence: 1,
        speaker: 'honeypot',
        source: 'tts_input',
        text: 'Could you repeat that?',
        language: null,
        start_offset_ms: 100,
        end_offset_ms: 200,
        is_final: true,
        stt_confidence: null,
        provider: 'mock-tts',
        created_at: '2026-09-25T20:00:04.000Z',
      },
      {
        record_layer: 'observation',
        id: 'seg-0',
        call_session_id: '6c0d5a2e-0000-5000-8000-000000000002',
        media_stream_id: 'stream-1',
        sequence: 0,
        speaker: 'caller',
        source: 'stt',
        text: 'call me at +15557654321',
        language: 'en',
        start_offset_ms: 0,
        end_offset_ms: 80,
        is_final: true,
        stt_confidence: 0.5,
        provider: 'mock-stt',
        created_at: '2026-09-25T20:00:03.000Z',
      },
    ],
    turns: [
      {
        record_layer: 'interpretation',
        id: 'turn-0',
        call_session_id: '6c0d5a2e-0000-5000-8000-000000000002',
        turn_index: 0,
        speaker: 'caller',
        text: 'call me at +15557654321',
        transcript_segment_ids: ['seg-0'],
        strategy_id: null,
        confidence: 1,
        created_at: '2026-09-25T20:00:03.000Z',
      },
    ],
    findings: [
      {
        record_layer: 'interpretation',
        id: 'find-1',
        call_session_id: '6c0d5a2e-0000-5000-8000-000000000002',
        kind: 'callback_number',
        value: '+15557654321',
        raw_quote: 'call me at +15557654321',
        transcript_segment_ids: ['seg-0'],
        extractor: 'e164',
        extractor_version: '0.1.0',
        confidence: 1,
        status: 'proposed',
        created_at: '2026-09-25T20:00:05.000Z',
      },
    ],
    attributions: [
      {
        record_layer: 'attribution',
        id: 'attr-1',
        campaign_id: 'camp-1',
        call_session_id: '6c0d5a2e-0000-5000-8000-000000000002',
        supporting_finding_ids: ['find-1'],
        method: 'exact-callback',
        method_version: '1',
        confidence: 0.3,
        rationale: 'shared callback number',
        created_at: '2026-09-25T20:00:06.000Z',
      },
    ],
  },
  nowMs,
)

assert.equal(detail.transcript[0]?.id, 'seg-0')
assert.equal(detail.transcript[0]?.record_layer, 'observation')
assert.equal(detail.transcript[0]?.stt_confidence, 0.5)
assert.equal(detail.turns[0]?.record_layer, 'interpretation')
assert.equal(detail.findings[0]?.record_layer, 'interpretation')
assert.equal(detail.findings[0]?.kind, 'callback_number')
assert.equal(detail.findings[0]?.confidence, 1)
assert.deepEqual(detail.findings[0]?.transcript_segment_ids, ['seg-0'])
assert.equal(detail.attributions[0]?.record_layer, 'attribution')
assert.equal(detail.gaps.campaign_id, 'camp-1')
assert.equal(detail.gaps.campaign_label, null)
assert.equal(detail.events.length, 0)
assert.equal(detail.gaps.duration_ms, 10_000)
assert.equal(detail.gaps.engagement_duration_ms, 8_000)
assert.equal(detail.gaps.pipeline, null)
assert.notEqual(detail.transcript[0]?.record_layer, detail.findings[0]?.record_layer)

const live = liveFromDetail(detail)
assert.equal(live.session.state, 'completed')
assert.equal(live.findings[0]?.kind, 'callback_number')
assert.equal(live.transcript[0]?.record_layer, 'observation')
assert.equal(live.findings[0]?.record_layer, 'interpretation')

console.log('mapCall checks passed')
