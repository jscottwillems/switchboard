import { ECHO_MEDIA } from "../media.js";
import { frameRms } from "../audio/pcm.js";
import type { PcmFrame } from "../types.js";
import { SilenceDetector } from "./silence.js";

export type VadEvent =
  | { type: "speech_start"; audioTimeMs: number }
  | { type: "speech_end"; audioTimeMs: number };

export interface VadObservation {
  voiced: boolean;
  event: VadEvent | null;
}

export class EnergyVad {
  private phase: "idle" | "onset" | "speech" = "idle";
  private onsetFrames = 0;
  private onsetAudioTimeMs = 0;
  private lastSpeechAudioTimeMs = 0;
  private readonly silence: SilenceDetector;

  constructor(
    private readonly threshold: number = ECHO_MEDIA.vadRmsThreshold,
    private readonly startFrames: number = ECHO_MEDIA.speechStartFrames,
    silenceMs: number = ECHO_MEDIA.silenceToEndpointMs,
    frameMs: number = ECHO_MEDIA.frameDurationMs,
  ) {
    this.silence = new SilenceDetector(silenceMs, frameMs);
  }

  push(frame: PcmFrame): VadObservation {
    const voiced = frameRms(frame.samples) >= this.threshold;
    if (this.phase === "idle" || this.phase === "onset") {
      return this.observeOnset(frame, voiced);
    }
    return this.observeSpeech(frame, voiced);
  }

  /** End an open utterance when the inbound stream closes. */
  forceEndpoint(): VadEvent | null {
    if (this.phase !== "speech") {
      this.reset();
      return null;
    }
    const event: VadEvent = { type: "speech_end", audioTimeMs: this.lastSpeechAudioTimeMs };
    this.reset();
    return event;
  }

  reset(): void {
    this.phase = "idle";
    this.onsetFrames = 0;
    this.silence.reset();
  }

  private observeOnset(frame: PcmFrame, voiced: boolean): VadObservation {
    if (!voiced) {
      this.phase = "idle";
      this.onsetFrames = 0;
      return { voiced, event: null };
    }
    if (this.onsetFrames === 0) {
      this.onsetAudioTimeMs = frame.audioTimeMs;
    }
    this.onsetFrames += 1;
    this.phase = "onset";
    if (this.onsetFrames < this.startFrames) {
      return { voiced, event: null };
    }
    this.phase = "speech";
    this.silence.reset();
    this.lastSpeechAudioTimeMs = frame.audioTimeMs;
    return { voiced, event: { type: "speech_start", audioTimeMs: this.onsetAudioTimeMs } };
  }

  private observeSpeech(frame: PcmFrame, voiced: boolean): VadObservation {
    if (voiced) {
      this.silence.observe(true);
      this.lastSpeechAudioTimeMs = frame.audioTimeMs;
      return { voiced, event: null };
    }
    const ended = this.silence.observe(false);
    if (!ended) {
      return { voiced: false, event: null };
    }
    const event: VadEvent = { type: "speech_end", audioTimeMs: this.lastSpeechAudioTimeMs };
    this.phase = "idle";
    this.onsetFrames = 0;
    this.silence.reset();
    return { voiced: false, event };
  }
}
