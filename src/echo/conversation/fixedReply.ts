import { MOCK_LATENCY } from "../media.js";
import type { ConversationDecision } from "./provider.js";

export interface FixedReplyOptions {
  text: string;
  latencyMs?: number;
}

/**
 * Stand-in for LOKI. The reply text is fixed for this slice; the transcript is
 * accepted so a later adapter can use it without changing the pipeline.
 */
export function createFixedReply(options: FixedReplyOptions): ConversationDecision {
  const text = options.text.trim();
  if (!text) {
    throw new Error("Fixed reply requires non-empty text");
  }
  const latencyMs = options.latencyMs ?? MOCK_LATENCY.decisionMs;
  return {
    latencyMs,
    decide(input) {
      if (!input.turnId) {
        throw new Error("Conversation decision requires a turn id");
      }
      return { text };
    },
  };
}
