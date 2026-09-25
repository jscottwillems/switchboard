import { ECHO_MEDIA } from "../../src/echo/media.js";
import type { PcmFrame } from "../../src/echo/types.js";

export function sineFrame(sequence: number, sampleRateHz: number = ECHO_MEDIA.sampleRateHz): PcmFrame {
  const sampleCount = Math.round((sampleRateHz * ECHO_MEDIA.frameDurationMs) / 1000);
  const samples = new Int16Array(sampleCount);
  for (let i = 0; i < sampleCount; i += 1) {
    samples[i] = Math.round(Math.sin((2 * Math.PI * 180 * i) / sampleRateHz) * 8000);
  }
  return {
    sequence,
    audioTimeMs: sequence * ECHO_MEDIA.frameDurationMs,
    sampleRateHz,
    samples,
  };
}

export function silenceFrame(sequence: number, sampleRateHz: number = ECHO_MEDIA.sampleRateHz): PcmFrame {
  const sampleCount = Math.round((sampleRateHz * ECHO_MEDIA.frameDurationMs) / 1000);
  return {
    sequence,
    audioTimeMs: sequence * ECHO_MEDIA.frameDurationMs,
    sampleRateHz,
    samples: new Int16Array(sampleCount),
  };
}
