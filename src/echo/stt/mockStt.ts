import { MOCK_LATENCY } from "../media.js";
import type { PcmFrame, TranscriptFinal, TranscriptPartial } from "../types.js";
import type { StreamingStt, SttSession } from "./provider.js";

export interface MockSttOptions {
  transcript: string;
  finalizeDelayMs?: number;
  msPerWord?: number;
  frameDurationMs?: number;
}

/**
 * Offline streaming STT. It does not recognize audio. While VAD reports voiced
 * frames it reveals the configured transcript word by word, then returns that
 * full transcript as the final hypothesis on endpoint.
 */
export function createMockStt(options: MockSttOptions): StreamingStt {
  const transcript = options.transcript.trim();
  if (!transcript) {
    throw new Error("Mock STT requires a non-empty transcript");
  }
  const finalizeDelayMs = options.finalizeDelayMs ?? MOCK_LATENCY.sttFinalizeMs;
  const msPerWord = options.msPerWord ?? MOCK_LATENCY.msPerWord;
  const frameDurationMs = options.frameDurationMs ?? 20;
  return {
    finalizeDelayMs,
    start() {
      return new MockSttSession(transcript, msPerWord, frameDurationMs);
    },
  };
}

class MockSttSession implements SttSession {
  private voicedMs = 0;
  private revealedWords = 0;
  private closed = false;
  private readonly words: string[];

  constructor(
    private readonly transcript: string,
    private readonly msPerWord: number,
    private readonly frameDurationMs: number,
  ) {
    this.words = transcript.split(/\s+/).filter((word) => word.length > 0);
  }

  push(frame: PcmFrame, voiced: boolean): TranscriptPartial[] {
    if (this.closed) {
      throw new Error("Mock STT session already received endpoint");
    }
    if (!voiced) {
      return [];
    }
    this.voicedMs += this.frameDurationMs;
    const due = Math.min(this.words.length, Math.floor(this.voicedMs / this.msPerWord));
    if (due <= this.revealedWords) {
      return [];
    }
    this.revealedWords = due;
    return [
      {
        type: "partial",
        text: this.words.slice(0, due).join(" "),
        audioTimeMs: frame.audioTimeMs,
      },
    ];
  }

  endpoint(audioTimeMs: number): TranscriptFinal {
    if (this.closed) {
      throw new Error("Mock STT session already received endpoint");
    }
    this.closed = true;
    return {
      type: "final",
      text: this.transcript,
      audioTimeMs,
    };
  }
}
