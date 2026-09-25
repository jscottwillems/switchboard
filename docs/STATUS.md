# Status

ATLAS owns this document overall. ECHO added the handoff below. Append new notes; do not remove another owner's entry.

## HANDOFF

### ECHO — realtime speech slice (local only)

The offline speech path is in place. Attaching ECHO to BELL is **blocked** until this slice is accepted. Do not wire provider transport into ECHO yet.

What landed:

- `tests/audio/sample_call.wav` and `tests/audio/sample_call.json`: one caller turn, 16 kHz mono PCM16, with the expected transcript and fixed reply.
- Local pipeline in `src/echo`: normalize → jitter buffer → energy VAD → silence endpoint → mock streaming STT (partials and a final) → fixed LOKI reply → mock TTS → outbound frame buffer, including barge-in cancel.
- Metrics for a turn: `speech_start_detected`, `speech_end_detected`, `partial_transcript_latency`, `final_transcript_latency`, `agent_decision_latency`, `tts_first_byte_latency`, `first_audio_latency`, `full_turn_latency`.
- Media requirements BELL must meet are in `docs/API_CONTRACTS.md` under "ECHO — media requirements for BELL".

STT and TTS on this path are in-process mocks behind `StreamingStt` and `TtsProvider`. No API key, network, or system TTS binary is required.

Run from the repository root:

```bash
npm install
npm test
npm run sample
```

`npm run sample` reads `tests/audio/sample_call.wav` plus `tests/audio/sample_call.json` and writes:

- `artifacts/sample_call_response.wav` (synthesized reply, 16 kHz mono PCM16)
- `artifacts/sample_call_metrics.json`

Optional flags: `--input`, `--metadata`, `--out`, `--metrics`.
