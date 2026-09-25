import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { frameRms } from "../../src/echo/audio/pcm.js";
import { readWav } from "../../src/echo/audio/wav.js";
import { main } from "../../src/echo/cli.js";
import { createFixedReply } from "../../src/echo/conversation/fixedReply.js";
import { ECHO_MEDIA, MOCK_LATENCY } from "../../src/echo/media.js";
import { createSpeechPipeline } from "../../src/echo/pipeline/speechPipeline.js";
import { readSampleMetadata, runSampleCall } from "../../src/echo/pipeline/runSample.js";
import { createMockStt } from "../../src/echo/stt/mockStt.js";
import { createMockTts } from "../../src/echo/tts/mockTts.js";
import type { MetricEvent, MetricName } from "../../src/echo/types.js";
import { silenceFrame, sineFrame } from "./helpers.js";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");

const METRIC_NAMES: readonly MetricName[] = [
  "speech_start_detected",
  "speech_end_detected",
  "partial_transcript_latency",
  "final_transcript_latency",
  "agent_decision_latency",
  "tts_first_byte_latency",
  "first_audio_latency",
  "full_turn_latency",
];

test("sample call runs offline from audio to reply audio", () => {
  const metadata = readSampleMetadata(path.join(root, "tests/audio/sample_call.json"));
  const seen: MetricEvent[] = [];
  const result = runSampleCall({
    wavPath: path.join(root, "tests/audio/sample_call.wav"),
    metadataPath: path.join(root, "tests/audio/sample_call.json"),
    metricHook(event) {
      seen.push(event);
    },
  });

  assert.equal(result.transcript, metadata.utterance.transcript);
  assert.equal(result.replyText, metadata.fixedReply);
  assert.equal(result.endpointReason, "silence");
  assert.equal(result.cancels.length, 0);
  assert.ok(result.partials.length > 0);
  for (const partial of result.partials) {
    assert.ok(result.transcript.startsWith(partial), `partial "${partial}" is not a prefix`);
  }
  assert.deepEqual(seen, result.metrics);

  const names = result.metrics.map((metric) => metric.name);
  for (const name of METRIC_NAMES) {
    assert.equal(names.filter((candidate) => candidate === name).length, 1, name);
  }

  const speechStart = metric(result.metrics, "speech_start_detected");
  const speechEnd = metric(result.metrics, "speech_end_detected");
  const partial = metric(result.metrics, "partial_transcript_latency");
  const finalLatency = metric(result.metrics, "final_transcript_latency");
  const decision = metric(result.metrics, "agent_decision_latency");
  const firstByte = metric(result.metrics, "tts_first_byte_latency");
  const firstAudio = metric(result.metrics, "first_audio_latency");
  const fullTurn = metric(result.metrics, "full_turn_latency");

  assert.ok(speechStart.atMs < partial.atMs);
  assert.ok(partial.atMs < speechEnd.atMs);
  assert.equal(finalLatency.valueMs, MOCK_LATENCY.sttFinalizeMs);
  assert.equal(decision.valueMs, MOCK_LATENCY.decisionMs);
  assert.equal(firstByte.valueMs, MOCK_LATENCY.ttsFirstByteMs);
  assert.equal(firstAudio.valueMs, finalLatency.valueMs + decision.valueMs + firstByte.valueMs);
  assert.ok(fullTurn.valueMs > firstAudio.valueMs);
  assert.ok(speechStart.valueMs >= ECHO_MEDIA.jitterDelayMs);
  assert.ok(speechEnd.valueMs >= ECHO_MEDIA.silenceToEndpointMs);

  assert.ok(result.outbound.length > 10);
  assert.equal(result.outbound[0]?.sampleRateHz, ECHO_MEDIA.sampleRateHz);
  assert.equal(result.outbound[0]?.samples.length, ECHO_MEDIA.samplesPerFrame);
  const loud = result.outbound.some((frame) => frameRms(frame.samples) > 500);
  assert.equal(loud, true);
});

test("cli writes the outbound wav and metrics", () => {
  const outPath = path.join(root, "artifacts/sample_call_response.wav");
  const metricsPath = path.join(root, "artifacts/sample_call_metrics.json");
  const code = main([
    "--input",
    path.join(root, "tests/audio/sample_call.wav"),
    "--metadata",
    path.join(root, "tests/audio/sample_call.json"),
    "--out",
    outPath,
    "--metrics",
    metricsPath,
  ]);
  assert.equal(code, 0);
  const wav = readWav(new Uint8Array(readFileSync(outPath)));
  assert.equal(wav.sampleRateHz, ECHO_MEDIA.sampleRateHz);
  assert.equal(wav.channels, 1);
  assert.ok(wav.samples.length > ECHO_MEDIA.sampleRateHz);
  const metrics = JSON.parse(readFileSync(metricsPath, "utf8")) as { metrics?: { name?: string }[] };
  const names = new Set((metrics.metrics ?? []).map((event) => event.name));
  for (const name of METRIC_NAMES) {
    assert.equal(names.has(name), true);
  }
});

test("caller speech during playback cancels queued outbound audio", () => {
  const pipeline = createSpeechPipeline({
    stt: createMockStt({ transcript: "Hello there" }),
    tts: createMockTts(),
    decision: createFixedReply({ text: "I can help you reschedule that appointment." }),
  });
  let sequence = 0;
  for (let i = 0; i < 40; i += 1) {
    pipeline.ingest(sineFrame(sequence));
    sequence += 1;
  }
  for (let i = 0; i < 40; i += 1) {
    pipeline.ingest(silenceFrame(sequence));
    sequence += 1;
  }
  pipeline.finish();
  const inFlight = pipeline.drain(2);
  const queued = pipeline.queuedFrameCount;
  assert.equal(inFlight.length, 2);
  assert.ok(queued > 0);

  for (let i = 0; i < 4; i += 1) {
    pipeline.ingest(sineFrame(sequence));
    sequence += 1;
  }

  assert.equal(pipeline.cancels.length, 1);
  const cancel = pipeline.cancels[0];
  assert.ok(cancel);
  assert.equal(cancel.type, "outbound.cancel");
  assert.equal(cancel.reason, "barge_in");
  assert.equal(cancel.dropQueuedFrames, true);
  assert.equal(cancel.droppedFrames, queued);
  assert.equal(pipeline.queuedFrameCount, 0);
  assert.equal(pipeline.drain().length, 0);
});

test("max utterance timeout endpoints without trailing silence", () => {
  const pipeline = createSpeechPipeline({
    stt: createMockStt({ transcript: "Hello there" }),
    tts: createMockTts(),
    decision: createFixedReply({ text: "Okay." }),
    maxUtteranceMs: 100,
  });
  let sequence = 0;
  while (!pipeline.finalTranscript && sequence < 30) {
    pipeline.ingest(sineFrame(sequence));
    sequence += 1;
  }
  assert.equal(pipeline.finalTranscript, "Hello there");
  assert.equal(pipeline.endpointReason, "max_utterance");
  assert.ok(sequence < 30);
});

test("silence does not invent a transcript", () => {
  const pipeline = createSpeechPipeline({
    stt: createMockStt({ transcript: "Hello there" }),
    tts: createMockTts(),
    decision: createFixedReply({ text: "Okay." }),
  });
  for (let i = 0; i < 40; i += 1) {
    pipeline.ingest(silenceFrame(i));
  }
  pipeline.finish();
  assert.equal(pipeline.finalTranscript, "");
  assert.equal(pipeline.metrics.length, 0);
  assert.equal(pipeline.drain().length, 0);
});

test("8 kHz inbound frames are normalized before VAD and STT", () => {
  const pipeline = createSpeechPipeline({
    stt: createMockStt({ transcript: "Hello there" }),
    tts: createMockTts(),
    decision: createFixedReply({ text: "Okay." }),
  });
  let sequence = 0;
  for (let i = 0; i < 40; i += 1) {
    pipeline.ingest(sineFrame(sequence, 8000));
    sequence += 1;
  }
  for (let i = 0; i < 40; i += 1) {
    pipeline.ingest(silenceFrame(sequence, 8000));
    sequence += 1;
  }
  pipeline.finish();
  assert.equal(pipeline.finalTranscript, "Hello there");
  assert.equal(pipeline.drain()[0]?.sampleRateHz, ECHO_MEDIA.sampleRateHz);
});

function metric(events: readonly MetricEvent[], name: MetricName): MetricEvent {
  const found = events.find((event) => event.name === name);
  assert.ok(found, name);
  return found;
}
