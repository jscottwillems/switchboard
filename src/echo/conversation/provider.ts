import type { DecisionInput, DecisionResult } from "../types.js";

/**
 * Boundary with LOKI. ECHO sends the final transcript and speaks whatever text
 * comes back. This slice does not choose dialogue.
 */
export interface ConversationDecision {
  readonly latencyMs: number;
  decide(input: DecisionInput): DecisionResult;
}
