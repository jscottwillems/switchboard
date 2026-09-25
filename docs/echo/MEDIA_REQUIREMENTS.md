# ECHO media requirements (draft)

Private ECHO draft. This is not `docs/API_CONTRACTS.md`. ATLAS owns the shared contract docs. Publish this section there only after the ATLAS bootstrap is on main. Do not attach this pipeline to BELL from this draft.

ECHO does not own call signaling, provider sockets, or dialogue. BELL would terminate the carrier or provider and hand ECHO PCM. LOKI would choose what to say. The types under `src/echo` are the current TypeScript embodiment of this draft. Threshold numbers live in `src/echo/media.ts` (`ECHO_MEDIA`).

Pipeline this slice implements:

incoming audio → normalization → jitter buffer → energy VAD → silence endpoint → streaming STT → utterance final → conversation decision (LOKI stand-in) → TTS → outbound frame queue.

## Inbound audio (BELL → ECHO)

| Property | Requirement |
| --- | --- |
| Codec | Linear PCM, signed 16-bit, little-endian (`pcm_s16le`). If the carrier sends G.711 μ-law or A-law, BELL decodes it before the handoff. ECHO does not accept Opus, G.722, or raw μ-law. |
| Sample rate | **16000 Hz** preferred. **8000 Hz** is accepted and linearly upsampled to 16000 Hz. Any other rate is rejected. |
| Channels | 1 (mono). BELL downmixes stereo before the handoff. A stereo WAV used in local tests is downmixed by ECHO only at the file reader. |
| Frame duration | 20 ms. |
| Frame size | 320 samples / **640 bytes** at 16000 Hz. 160 samples / **320 bytes** at 8000 Hz. |
| Endianness | Little-endian. For sample `n`, byte `2n` is the low byte and byte `2n+1` is the high byte. |
| Chunking | One frame per handoff, in order. Each frame carries a monotonic `sequence` (`uint32`, starting at 0 for the stream) and `audioTimeMs` (capture time of the first sample, milliseconds from stream start). |
| Levels | Int16 full scale. Silence should sit under the VAD threshold (RMS below 400). Typical decoded speech peaks of a few thousand to about 12000 are fine. Do not send float32 samples. |
| Stream end | BELL sends an explicit end-of-stream after the last frame. ECHO flushes the jitter buffer and, if the caller is still mid-utterance, forces an endpoint. |

ECHO reframes a byte stream only when a local fixture is not already cut into 20 ms frames. The supported handoff is one 20 ms frame per message.

## Jitter

ECHO keeps a 3-frame (60 ms) jitter buffer. The oldest frame is released once three frames are queued, so VAD sees a frame 60 ms after its capture time (40 ms until the buffer first fills, plus the 20 ms newest frame). On sequence gaps, ECHO inserts 20 ms of silence for each missing sequence and continues. It does not wait forever for a late packet. BELL should not add another buffering stage on top of this.

## Voice activity, silence, and timeouts

- Speech onset: RMS at or above **400**, confirmed across **2** consecutive 20 ms frames (40 ms).
- Speech end: **500 ms** of trailing audio under that threshold. The speech-end timestamp is the last voiced frame, not the silence that tripped the endpoint.
- Maximum utterance: **15000 ms** of voiced audio in one turn. ECHO then endpoints even if the caller has not gone silent.

## Outbound audio (ECHO → BELL)

Same PCM contract: `pcm_s16le`, 16000 Hz, mono, 20 ms frames (640 bytes). `sequence` restarts at 0 for each turn. `audioTimeMs` is the offset within that turn, not the inbound capture clock.

ECHO writes frames into an outbound buffer as TTS produces them. A future BELL adapter would pull or receive that buffer. Frames already handed off are in flight. Frames still in ECHO's buffer are queued.

## Barge-in cancel

When ECHO detects caller speech while a reply is still queued or playing, ECHO aborts TTS and emits:

```json
{
  "type": "outbound.cancel",
  "turnId": "turn-1",
  "reason": "barge_in",
  "dropQueuedFrames": true,
  "droppedFrames": 0
}
```

Expected BELL behavior once attached:

- Drop every outbound frame for that `turnId` that has not started playing.
- The single in-flight 20 ms frame may finish.
- Do not send any later frame from that turn.
- Apply the cancel within 20 ms of receiving it.
- `droppedFrames` is how many frames ECHO removed from its own buffer. BELL still drops its own queue when `dropQueuedFrames` is true, regardless of that count.

ECHO also clears its outbound queue and stops pulling TTS frames for that turn. Audio already pulled by the sink is not clawed back.

## Streaming transcript and decision

ECHO emits partial transcripts while speech is voiced and one final transcript at endpoint. This slice's STT is a local mock (`StreamingStt` in `src/echo/stt/provider.ts`) that reveals a configured transcript in time with voiced frames. A live provider replaces that adapter. No API key is required for the sample path.

After the final transcript, ECHO calls the conversation adapter:

```json
{ "turnId": "turn-1", "finalTranscript": "Hi, I need to reschedule my appointment for Thursday." }
```

The adapter returns `{ "text": "..." }`. This slice uses a fixed reply (`createFixedReply`). That stand-in is the LOKI boundary. ECHO does not choose dialogue.

## Metrics

ECHO records these on a pipeline clock (inbound audio time, plus delay declared by a local mock). A live provider should leave its declared delay at 0 so the same fields measure real elapsed time. The hook is `MetricHook` on the pipeline; the sample writes `artifacts/sample_call_metrics.json`.

| Metric | Meaning |
| --- | --- |
| `speech_start_detected` | Onset confirmed. `audioTimeMs` is the first voiced frame. `valueMs` is confirmation lag, including the jitter buffer. |
| `speech_end_detected` | Endpoint. `audioTimeMs` is the last voiced frame. `valueMs` is how much later ECHO noticed (trailing silence or timeout, plus jitter). |
| `partial_transcript_latency` | Speech start → first partial transcript. |
| `final_transcript_latency` | Speech end → final transcript. |
| `agent_decision_latency` | Time inside the conversation decision adapter. |
| `tts_first_byte_latency` | TTS start → first outbound PCM frame. |
| `first_audio_latency` | Speech end → first outbound frame in ECHO's buffer. |
| `full_turn_latency` | Speech start → the outbound buffer holds the full reply. |

Point events may repeat if the caller barges in and starts another turn. Latency metrics are once per completed reply.

## Fixture

`tests/audio/sample_call.wav` is 16000 Hz mono `pcm_s16le` with leading and trailing silence. `tests/audio/sample_call.json` holds the expected transcript and the fixed reply.

From the repo root:

```bash
npm install
npm test
npm run sample
```

`npm run sample` writes `artifacts/sample_call_response.wav` and `artifacts/sample_call_metrics.json`.
