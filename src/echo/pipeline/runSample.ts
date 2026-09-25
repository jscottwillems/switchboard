import { readFileSync } from "node:fs";

import { framesFromSamples } from "../audio/pcm.js";
import { normalizeSamples } from "../audio/normalize.js";
import { readWav } from "../audio/wav.js";
import { createFixedReply } from "../conversation/fixedReply.js";
import { ECHO_MEDIA } from "../media.js";
import type { MetricHook } from "../metrics/recorder.js";
import { createMockStt } from "../stt/mockStt.js";
import { createMockTts } from "../tts/mockTts.js";
import type { EndpointReason, MetricEvent, OutboundCancel, PcmFrame, SampleCallMetadata } from "../types.js";
import { createSpeechPipeline } from "./speechPipeline.js";

export interface SampleCallResult {
  transcript: string;
  replyText: string;
  partials: readonly string[];
  outbound: PcmFrame[];
  metrics: readonly MetricEvent[];
  cancels: readonly OutboundCancel[];
  endpointReason: EndpointReason | null;
  inputDurationMs: number;
}

export function runSampleCall(options: {
  wavPath: string;
  metadataPath: string;
  metricHook?: MetricHook;
}): SampleCallResult {
  const metadata = readSampleMetadata(options.metadataPath);
  const wav = readWav(new Uint8Array(readFileSync(options.wavPath)));
  const samples = normalizeSamples(wav.samples, wav.sampleRateHz, wav.channels);
  const frames = framesFromSamples(samples, ECHO_MEDIA.sampleRateHz);
  const pipeline = createSpeechPipeline({
    stt: createMockStt({ transcript: metadata.utterance.transcript }),
    tts: createMockTts(),
    decision: createFixedReply({ text: metadata.fixedReply }),
    ...(options.metricHook ? { metricHook: options.metricHook } : {}),
  });
  for (const frame of frames) {
    pipeline.ingest(frame);
  }
  pipeline.finish();
  const outbound = pipeline.drain();
  if (!pipeline.finalTranscript) {
    throw new Error("Sample call produced no final transcript. VAD did not endpoint on the fixture.");
  }
  return {
    transcript: pipeline.finalTranscript,
    replyText: pipeline.replyText,
    partials: pipeline.partials,
    outbound,
    metrics: pipeline.metrics,
    cancels: pipeline.cancels,
    endpointReason: pipeline.endpointReason,
    inputDurationMs: (samples.length / ECHO_MEDIA.sampleRateHz) * 1000,
  };
}

export function readSampleMetadata(metadataPath: string): SampleCallMetadata {
  const parsed: unknown = JSON.parse(readFileSync(metadataPath, "utf8"));
  if (!isSampleMetadata(parsed)) {
    throw new Error(`${metadataPath} must contain utterance.transcript and fixedReply strings`);
  }
  return parsed;
}

function isSampleMetadata(value: unknown): value is SampleCallMetadata {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const record = value as { utterance?: { transcript?: unknown }; fixedReply?: unknown };
  return (
    typeof record.fixedReply === "string" &&
    record.fixedReply.trim().length > 0 &&
    typeof record.utterance?.transcript === "string" &&
    record.utterance.transcript.trim().length > 0
  );
}
