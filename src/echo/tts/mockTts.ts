import { framesFromSamples } from "../audio/pcm.js";
import { ECHO_MEDIA, MOCK_LATENCY } from "../media.js";
import type { PcmFrame } from "../types.js";
import type { TtsProvider } from "./provider.js";

export interface MockTtsOptions {
  firstByteDelayMs?: number;
}

/** Deterministic local synthesizer. No network and no system TTS binary. */
export function createMockTts(options: MockTtsOptions = {}): TtsProvider {
  const firstByteDelayMs = options.firstByteDelayMs ?? MOCK_LATENCY.ttsFirstByteMs;
  return {
    firstByteDelayMs,
    synthesize(text: string, signal: AbortSignal): Iterable<PcmFrame> {
      return synthesizeFrames(text, signal);
    },
  };
}

function* synthesizeFrames(text: string, signal: AbortSignal): Iterable<PcmFrame> {
  const frames = framesFromSamples(synthSamples(text), ECHO_MEDIA.sampleRateHz);
  for (const frame of frames) {
    if (signal.aborted) {
      return;
    }
    yield frame;
  }
}

function synthSamples(text: string): Int16Array {
  const pieces: Float64Array[] = [];
  const characters = Array.from(text);
  for (let index = 0; index < characters.length; index += 1) {
    pieces.push(synthCharacter(characters[index] ?? " ", index));
  }
  const total = pieces.reduce((sum, piece) => sum + piece.length, 0);
  const merged = new Float64Array(total);
  let offset = 0;
  for (const piece of pieces) {
    merged.set(piece, offset);
    offset += piece.length;
  }
  let peak = 0;
  for (const value of merged) {
    peak = Math.max(peak, Math.abs(value));
  }
  const scale = peak > 0 ? 9000 / peak : 0;
  const pcm = new Int16Array(merged.length);
  for (let i = 0; i < merged.length; i += 1) {
    const sample = (merged[i] ?? 0) * scale;
    pcm[i] = Math.max(-32768, Math.min(32767, Math.round(sample)));
  }
  return pcm;
}

function synthCharacter(character: string, index: number): Float64Array {
  if (character.trim() === "") {
    return new Float64Array(Math.round(ECHO_MEDIA.sampleRateHz * 0.045));
  }
  const count = Math.round(ECHO_MEDIA.sampleRateHz * 0.068);
  const output = new Float64Array(count);
  const lower = character.toLowerCase();
  const voiced = "aeiou".includes(lower);
  const formant = formantFor(lower);
  const fundamental = 118 + (index % 5) * 7;
  let phase = 0;
  for (let i = 0; i < count; i += 1) {
    const envelope = Math.sin((Math.PI * i) / count);
    if (voiced) {
      phase += (2 * Math.PI * fundamental) / ECHO_MEDIA.sampleRateHz;
      const voice = Math.sin(phase) + 0.35 * Math.sin(2 * phase);
      const first = Math.sin((2 * Math.PI * formant[0] * i) / ECHO_MEDIA.sampleRateHz);
      const second = Math.sin((2 * Math.PI * formant[1] * i) / ECHO_MEDIA.sampleRateHz);
      output[i] = envelope * (0.72 * voice + 0.18 * first + 0.1 * second);
    } else {
      output[i] = envelope * hashNoise(index, i) * 0.45;
    }
  }
  return output;
}

function formantFor(character: string): readonly [number, number] {
  switch (character) {
    case "a":
      return [700, 1200];
    case "e":
      return [400, 2200];
    case "i":
      return [300, 2700];
    case "o":
      return [500, 900];
    case "u":
      return [350, 700];
    default:
      return [520, 1500];
  }
}

function hashNoise(index: number, sampleIndex: number): number {
  const value = Math.sin(index * 12.9898 + sampleIndex * 78.233) * 43758.5453;
  return (value - Math.floor(value)) * 2 - 1;
}
