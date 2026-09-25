import type { MetricEvent, MetricName } from "../types.js";

export type MetricHook = (event: MetricEvent) => void;

export class MetricRecorder {
  readonly events: MetricEvent[] = [];

  constructor(private readonly hook?: MetricHook) {}

  record(event: MetricEvent): void {
    assertKnownMetric(event.name);
    this.events.push(event);
    this.hook?.(event);
  }
}

function assertKnownMetric(name: MetricName): void {
  switch (name) {
    case "speech_start_detected":
    case "speech_end_detected":
    case "partial_transcript_latency":
    case "final_transcript_latency":
    case "agent_decision_latency":
    case "tts_first_byte_latency":
    case "first_audio_latency":
    case "full_turn_latency":
      return;
    default: {
      const unexpected: never = name;
      throw new Error(`Unknown metric ${String(unexpected)}`);
    }
  }
}
