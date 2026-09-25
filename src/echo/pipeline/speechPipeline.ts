import { normalizeFrame } from "../audio/normalize.js";
import { JitterBuffer } from "../audio/jitterBuffer.js";
import type { Clock } from "../clock.js";
import { createManualClock } from "../clock.js";
import type { ConversationDecision } from "../conversation/provider.js";
import { ECHO_MEDIA } from "../media.js";
import { MetricRecorder, type MetricHook } from "../metrics/recorder.js";
import type { StreamingStt, SttSession } from "../stt/provider.js";
import type { TtsProvider } from "../tts/provider.js";
import type {
  EndpointReason,
  MetricEvent,
  OutboundCancel,
  PcmFrame,
  TranscriptPartial,
} from "../types.js";
import { EnergyVad } from "../vad/energy.js";
import { OutboundQueue } from "./outboundQueue.js";

export interface SpeechPipelineOptions {
  stt: StreamingStt;
  tts: TtsProvider;
  decision: ConversationDecision;
  clock?: Clock;
  metricHook?: MetricHook;
  maxUtteranceMs?: number;
  vadThreshold?: number;
  silenceMs?: number;
}

export interface SpeechPipeline {
  ingest(frame: PcmFrame): void;
  finish(): void;
  drain(maxFrames?: number): PcmFrame[];
  readonly queuedFrameCount: number;
  readonly metrics: readonly MetricEvent[];
  readonly cancels: readonly OutboundCancel[];
  readonly partials: readonly string[];
  readonly finalTranscript: string;
  readonly replyText: string;
  readonly endpointReason: EndpointReason | null;
}

export function createSpeechPipeline(options: SpeechPipelineOptions): SpeechPipeline {
  return new SpeechPipelineEngine(options);
}

class SpeechPipelineEngine implements SpeechPipeline {
  private readonly stt: StreamingStt;
  private readonly tts: TtsProvider;
  private readonly decision: ConversationDecision;
  private readonly clock: Clock;
  private readonly maxUtteranceMs: number;
  private readonly recorder: MetricRecorder;
  private readonly jitter = new JitterBuffer();
  private readonly vad: EnergyVad;
  private readonly queue = new OutboundQueue();
  private readonly cancelLog: OutboundCancel[] = [];
  private readonly partialLog: string[] = [];

  private phase: "idle" | "listening" | "speaking" = "idle";
  private turnNumber = 0;
  private turnId = "";
  private session: SttSession | null = null;
  private abort: AbortController | null = null;
  private speechStartAt: number | null = null;
  private speechEndAt: number | null = null;
  private voicedMs = 0;
  private partialRecorded = false;
  private replyBuffered = false;
  private transcript = "";
  private reply = "";
  private endpoint: EndpointReason | null = null;

  constructor(options: SpeechPipelineOptions) {
    this.stt = options.stt;
    this.tts = options.tts;
    this.decision = options.decision;
    this.clock = options.clock ?? createManualClock();
    this.maxUtteranceMs = options.maxUtteranceMs ?? ECHO_MEDIA.maxUtteranceMs;
    this.recorder = new MetricRecorder(options.metricHook);
    this.vad = new EnergyVad(
      options.vadThreshold ?? ECHO_MEDIA.vadRmsThreshold,
      ECHO_MEDIA.speechStartFrames,
      options.silenceMs ?? ECHO_MEDIA.silenceToEndpointMs,
    );
  }

  get queuedFrameCount(): number {
    return this.queue.length;
  }

  get metrics(): readonly MetricEvent[] {
    return this.recorder.events;
  }

  get cancels(): readonly OutboundCancel[] {
    return this.cancelLog;
  }

  get partials(): readonly string[] {
    return this.partialLog;
  }

  get finalTranscript(): string {
    return this.transcript;
  }

  get replyText(): string {
    return this.reply;
  }

  get endpointReason(): EndpointReason | null {
    return this.endpoint;
  }

  ingest(frame: PcmFrame): void {
    const normalized = normalizeFrame(frame);
    for (const released of this.jitter.push(normalized)) {
      this.handle(released);
    }
  }

  finish(): void {
    for (const released of this.jitter.flush()) {
      this.handle(released);
    }
    if (this.phase !== "listening") {
      return;
    }
    const event = this.vad.forceEndpoint();
    if (event?.type === "speech_end") {
      this.endUtterance(event.audioTimeMs, "stream_end");
    }
  }

  drain(maxFrames?: number): PcmFrame[] {
    const frames = this.queue.drain(maxFrames ?? Number.POSITIVE_INFINITY);
    if (this.queue.length === 0 && this.replyBuffered && this.phase === "speaking") {
      this.phase = "idle";
      this.replyBuffered = false;
    }
    return frames;
  }

  private handle(frame: PcmFrame): void {
    this.clock.seek(frame.audioTimeMs + ECHO_MEDIA.jitterDelayMs);
    const observation = this.vad.push(frame);
    const event = observation.event;
    if (event) {
      switch (event.type) {
        case "speech_start":
          this.onSpeechStart(event.audioTimeMs);
          break;
        case "speech_end":
          this.endUtterance(event.audioTimeMs, "silence");
          break;
        default: {
          const unexpected: never = event;
          throw new Error(`Unhandled VAD event ${String(unexpected)}`);
        }
      }
    }
    if (this.phase !== "listening" || !this.session) {
      return;
    }
    const partials = this.session.push(frame, observation.voiced);
    this.notePartials(partials);
    if (!observation.voiced) {
      return;
    }
    this.voicedMs += ECHO_MEDIA.frameDurationMs;
    if (this.voicedMs >= this.maxUtteranceMs) {
      this.vad.reset();
      this.endUtterance(frame.audioTimeMs, "max_utterance");
    }
  }

  private onSpeechStart(audioTimeMs: number): void {
    if (this.phase === "speaking") {
      this.cancelBargeIn();
    }
    this.turnNumber += 1;
    this.turnId = `turn-${this.turnNumber}`;
    this.session = this.stt.start();
    this.phase = "listening";
    this.speechStartAt = this.clock.nowMs();
    this.speechEndAt = null;
    this.voicedMs = 0;
    this.partialRecorded = false;
    this.replyBuffered = false;
    this.recorder.record({
      name: "speech_start_detected",
      turnId: this.turnId,
      atMs: this.speechStartAt,
      valueMs: this.speechStartAt - audioTimeMs,
      audioTimeMs,
    });
  }

  private cancelBargeIn(): void {
    this.abort?.abort();
    const droppedFrames = this.queue.clear();
    this.cancelLog.push({
      type: "outbound.cancel",
      turnId: this.turnId,
      reason: "barge_in",
      dropQueuedFrames: true,
      droppedFrames,
    });
    this.phase = "idle";
    this.session = null;
    this.replyBuffered = false;
  }

  private endUtterance(audioTimeMs: number, reason: EndpointReason): void {
    if (this.phase !== "listening" || !this.session || this.speechStartAt === null) {
      return;
    }
    const speechEndAt = this.clock.nowMs();
    this.speechEndAt = speechEndAt;
    this.recorder.record({
      name: "speech_end_detected",
      turnId: this.turnId,
      atMs: speechEndAt,
      valueMs: speechEndAt - audioTimeMs,
      audioTimeMs,
    });
    this.phase = "speaking";
    this.produceReply(audioTimeMs, reason);
  }

  private produceReply(audioTimeMs: number, reason: EndpointReason): void {
    const session = this.session;
    const speechEndAt = this.speechEndAt;
    const speechStartAt = this.speechStartAt;
    if (!session || speechEndAt === null || speechStartAt === null) {
      return;
    }

    const finalTranscript = session.endpoint(audioTimeMs);
    if (this.stt.finalizeDelayMs > 0) {
      this.clock.advance(this.stt.finalizeDelayMs);
    }
    this.recorder.record({
      name: "final_transcript_latency",
      turnId: this.turnId,
      atMs: this.clock.nowMs(),
      valueMs: this.clock.nowMs() - speechEndAt,
    });

    const decisionStarted = this.clock.nowMs();
    const decision = this.decision.decide({
      turnId: this.turnId,
      finalTranscript: finalTranscript.text,
    });
    if (this.decision.latencyMs > 0) {
      this.clock.advance(this.decision.latencyMs);
    }
    this.recorder.record({
      name: "agent_decision_latency",
      turnId: this.turnId,
      atMs: this.clock.nowMs(),
      valueMs: this.clock.nowMs() - decisionStarted,
    });

    this.abort = new AbortController();
    const ttsStarted = this.clock.nowMs();
    const frames = this.tts.synthesize(decision.text, this.abort.signal)[Symbol.iterator]();
    if (this.tts.firstByteDelayMs > 0) {
      this.clock.advance(this.tts.firstByteDelayMs);
    }
    const first = frames.next();
    if (first.done || !first.value) {
      throw new Error("TTS produced no audio for the reply");
    }
    const firstByteAt = this.clock.nowMs();
    this.recorder.record({
      name: "tts_first_byte_latency",
      turnId: this.turnId,
      atMs: firstByteAt,
      valueMs: firstByteAt - ttsStarted,
    });
    this.recorder.record({
      name: "first_audio_latency",
      turnId: this.turnId,
      atMs: firstByteAt,
      valueMs: firstByteAt - speechEndAt,
    });
    this.enqueueOutbound(first.value, 0);
    let sequence = 1;
    while (!this.abort.signal.aborted) {
      const next = frames.next();
      if (next.done || !next.value) {
        break;
      }
      this.enqueueOutbound(next.value, sequence);
      sequence += 1;
    }
    if (this.abort.signal.aborted) {
      return;
    }
    this.recorder.record({
      name: "full_turn_latency",
      turnId: this.turnId,
      atMs: this.clock.nowMs(),
      valueMs: this.clock.nowMs() - speechStartAt,
    });
    this.transcript = finalTranscript.text;
    this.reply = decision.text;
    this.endpoint = reason;
    this.session = null;
    this.replyBuffered = true;
  }

  private enqueueOutbound(frame: PcmFrame, sequence: number): void {
    this.queue.enqueue({
      sequence,
      audioTimeMs: sequence * ECHO_MEDIA.frameDurationMs,
      sampleRateHz: frame.sampleRateHz,
      samples: frame.samples,
    });
  }

  private notePartials(partials: readonly TranscriptPartial[]): void {
    for (const partial of partials) {
      this.partialLog.push(partial.text);
      if (this.partialRecorded || this.speechStartAt === null) {
        continue;
      }
      this.partialRecorded = true;
      this.recorder.record({
        name: "partial_transcript_latency",
        turnId: this.turnId,
        atMs: this.clock.nowMs(),
        valueMs: this.clock.nowMs() - this.speechStartAt,
        audioTimeMs: partial.audioTimeMs,
      });
    }
  }
}
