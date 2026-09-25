import type { PcmFrame, TranscriptFinal, TranscriptPartial } from "../types.js";

export interface SttSession {
  push(frame: PcmFrame, voiced: boolean): TranscriptPartial[];
  endpoint(audioTimeMs: number): TranscriptFinal;
}

/**
 * Streaming speech-to-text. Implementations may be local mocks or network
 * providers. `finalizeDelayMs` is how a local mock models trailing recognition
 * time; a live provider leaves it at 0 and spends real time inside `endpoint`.
 */
export interface StreamingStt {
  readonly finalizeDelayMs: number;
  start(): SttSession;
}
