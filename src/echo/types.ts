export type MetricName =
  | "speech_start_detected"
  | "speech_end_detected"
  | "partial_transcript_latency"
  | "final_transcript_latency"
  | "agent_decision_latency"
  | "tts_first_byte_latency"
  | "first_audio_latency"
  | "full_turn_latency";

/**
 * Pipeline clock is milliseconds from the start of the inbound stream, plus
 * any delay a mock provider adds with `clock.advance`. It is not wall time.
 *
 * Detection events (`speech_start_detected`, `speech_end_detected`):
 * - `atMs` is when ECHO confirmed the event.
 * - `audioTimeMs` is the capture time of the onset, or of the last voiced
 *   frame for speech end.
 * - `valueMs` is the confirmation lag (`atMs - audioTimeMs`).
 *
 * Latency events:
 * - `partial_transcript_latency`: speech start → first partial.
 * - `final_transcript_latency`: speech end → final transcript.
 * - `agent_decision_latency`: time inside the conversation decision adapter.
 * - `tts_first_byte_latency`: TTS call → first outbound PCM frame.
 * - `first_audio_latency`: speech end → first outbound frame buffered.
 * - `full_turn_latency`: speech start → outbound buffer holds the full reply.
 */
export interface MetricEvent {
  name: MetricName;
  turnId: string;
  atMs: number;
  valueMs: number;
  audioTimeMs?: number;
}

export interface PcmFrame {
  /** Monotonic per inbound stream or per outbound turn, starting at 0. */
  sequence: number;
  /** Capture time of the first sample, milliseconds from stream start. */
  audioTimeMs: number;
  sampleRateHz: number;
  /** Signed 16-bit mono samples. On the wire these are little-endian bytes. */
  samples: Int16Array;
}

export interface TranscriptPartial {
  type: "partial";
  text: string;
  audioTimeMs: number;
}

export interface TranscriptFinal {
  type: "final";
  text: string;
  audioTimeMs: number;
}

export type TranscriptEvent = TranscriptPartial | TranscriptFinal;

export type EndpointReason = "silence" | "max_utterance" | "stream_end";

export interface OutboundCancel {
  type: "outbound.cancel";
  turnId: string;
  reason: "barge_in";
  /** BELL must drop every outbound frame it has not yet started playing. */
  dropQueuedFrames: true;
  /** How many frames ECHO dropped from its own buffer. Informational. */
  droppedFrames: number;
}

export interface DecisionInput {
  turnId: string;
  finalTranscript: string;
}

export interface DecisionResult {
  text: string;
}

export interface SampleCallMetadata {
  utterance: {
    transcript: string;
  };
  fixedReply: string;
}
