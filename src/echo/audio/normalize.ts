import { ECHO_MEDIA } from "../media.js";
import type { PcmFrame } from "../types.js";

export function normalizeSamples(samples: Int16Array, sampleRateHz: number, channels: number): Int16Array {
  const mono = downmixToMono(samples, channels);
  if (sampleRateHz === ECHO_MEDIA.sampleRateHz) {
    return mono;
  }
  if (sampleRateHz === 8000) {
    return upsampleLinear2x(mono);
  }
  throw new Error(
    `Unsupported sample rate ${sampleRateHz}. ECHO accepts ${ECHO_MEDIA.acceptedSampleRatesHz.join(" or ")} Hz.`,
  );
}

export function normalizeFrame(frame: PcmFrame): PcmFrame {
  if (frame.sampleRateHz === ECHO_MEDIA.sampleRateHz && frame.samples.length === ECHO_MEDIA.samplesPerFrame) {
    return frame;
  }
  if (frame.sampleRateHz === 8000 && frame.samples.length === 160) {
    return {
      sequence: frame.sequence,
      audioTimeMs: frame.audioTimeMs,
      sampleRateHz: ECHO_MEDIA.sampleRateHz,
      samples: upsampleLinear2x(frame.samples),
    };
  }
  throw new Error(
    `Unsupported frame: ${frame.sampleRateHz} Hz, ${frame.samples.length} samples. Expected 20 ms at 8000 or 16000 Hz.`,
  );
}

function downmixToMono(samples: Int16Array, channels: number): Int16Array {
  if (channels === 1) {
    return samples;
  }
  if (channels !== 2) {
    throw new Error(`Unsupported channel count ${channels}. ECHO accepts mono PCM.`);
  }
  if (samples.length % 2 !== 0) {
    throw new Error("Stereo PCM length must be even");
  }
  const frames = samples.length / 2;
  const mono = new Int16Array(frames);
  for (let i = 0; i < frames; i += 1) {
    const left = samples[i * 2] ?? 0;
    const right = samples[i * 2 + 1] ?? 0;
    mono[i] = Math.round((left + right) / 2);
  }
  return mono;
}

function upsampleLinear2x(input: Int16Array): Int16Array {
  if (input.length === 0) {
    return new Int16Array(0);
  }
  const output = new Int16Array(input.length * 2);
  for (let i = 0; i < input.length; i += 1) {
    const current = input[i] ?? 0;
    const next = input[i + 1] ?? current;
    output[i * 2] = current;
    output[i * 2 + 1] = Math.round((current + next) / 2);
  }
  return output;
}
