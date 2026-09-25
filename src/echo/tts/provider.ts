import type { PcmFrame } from "../types.js";

/**
 * Streaming text-to-speech. `firstByteDelayMs` is how a local mock models time
 * to the first PCM frame. A live provider leaves it at 0; the pipeline clock
 * then measures the real wait if the provider blocks or advances the clock.
 */
export interface TtsProvider {
  readonly firstByteDelayMs: number;
  synthesize(text: string, signal: AbortSignal): Iterable<PcmFrame>;
}
