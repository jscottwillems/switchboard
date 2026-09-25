import { ECHO_MEDIA } from "../media.js";
import type { PcmFrame } from "../types.js";

export function frameRms(samples: Int16Array): number {
  if (samples.length === 0) {
    return 0;
  }
  let sum = 0;
  for (let i = 0; i < samples.length; i += 1) {
    const sample = samples[i] ?? 0;
    sum += sample * sample;
  }
  return Math.sqrt(sum / samples.length);
}

export function decodePcmS16le(bytes: Uint8Array): Int16Array {
  if (bytes.byteLength % 2 !== 0) {
    throw new Error(`PCM byte length must be even, received ${bytes.byteLength}`);
  }
  const samples = new Int16Array(bytes.byteLength / 2);
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  for (let i = 0; i < samples.length; i += 1) {
    samples[i] = view.getInt16(i * 2, true);
  }
  return samples;
}

export function encodePcmS16le(samples: Int16Array): Uint8Array {
  const bytes = new Uint8Array(samples.length * 2);
  const view = new DataView(bytes.buffer);
  for (let i = 0; i < samples.length; i += 1) {
    view.setInt16(i * 2, samples[i] ?? 0, true);
  }
  return bytes;
}

export function copyFrame(frame: PcmFrame): PcmFrame {
  return {
    sequence: frame.sequence,
    audioTimeMs: frame.audioTimeMs,
    sampleRateHz: frame.sampleRateHz,
    samples: new Int16Array(frame.samples),
  };
}

export function silenceFrame(sequence: number, audioTimeMs: number, sampleRateHz: number): PcmFrame {
  const samplesPerFrame = Math.round((sampleRateHz * ECHO_MEDIA.frameDurationMs) / 1000);
  return {
    sequence,
    audioTimeMs,
    sampleRateHz,
    samples: new Int16Array(samplesPerFrame),
  };
}

export function framesFromSamples(
  samples: Int16Array,
  sampleRateHz: number,
  frameDurationMs = ECHO_MEDIA.frameDurationMs,
): PcmFrame[] {
  const frameSamples = Math.round((sampleRateHz * frameDurationMs) / 1000);
  if (frameSamples <= 0) {
    throw new Error(`Invalid frame size for ${sampleRateHz} Hz and ${frameDurationMs} ms`);
  }
  const frames: PcmFrame[] = [];
  let sequence = 0;
  for (let offset = 0; offset < samples.length; offset += frameSamples) {
    const slice = new Int16Array(frameSamples);
    const available = Math.min(frameSamples, samples.length - offset);
    slice.set(samples.subarray(offset, offset + available));
    frames.push({
      sequence,
      audioTimeMs: sequence * frameDurationMs,
      sampleRateHz,
      samples: slice,
    });
    sequence += 1;
  }
  return frames;
}

export function concatFrames(frames: readonly PcmFrame[]): Int16Array {
  const first = frames[0];
  if (!first) {
    return new Int16Array(0);
  }
  const total = frames.reduce((sum, frame) => sum + frame.samples.length, 0);
  const merged = new Int16Array(total);
  let offset = 0;
  for (const frame of frames) {
    merged.set(frame.samples, offset);
    offset += frame.samples.length;
  }
  return merged;
}
