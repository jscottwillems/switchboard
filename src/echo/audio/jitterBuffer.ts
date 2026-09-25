import { ECHO_MEDIA } from "../media.js";
import { copyFrame, silenceFrame } from "./pcm.js";
import type { PcmFrame } from "../types.js";

/**
 * Holds inbound frames and releases the oldest once `targetFrames` are queued.
 * Missing sequence numbers are replaced with silence rather than stalling.
 */
export class JitterBuffer {
  private readonly pending: PcmFrame[] = [];
  private nextSequence = 0;

  constructor(
    private readonly targetFrames = ECHO_MEDIA.jitterFrames,
    private readonly sampleRateHz = ECHO_MEDIA.sampleRateHz,
    private readonly frameDurationMs = ECHO_MEDIA.frameDurationMs,
  ) {}

  push(frame: PcmFrame): PcmFrame[] {
    this.pending.push(copyFrame(frame));
    this.pending.sort((left, right) => left.sequence - right.sequence);
    return this.release(false);
  }

  flush(): PcmFrame[] {
    return this.release(true);
  }

  private release(flush: boolean): PcmFrame[] {
    const released: PcmFrame[] = [];
    while (this.pending.length > 0 && (flush || this.pending.length >= this.targetFrames)) {
      const next = this.pending[0];
      if (!next) {
        break;
      }
      if (next.sequence > this.nextSequence) {
        released.push(
          silenceFrame(this.nextSequence, this.nextSequence * this.frameDurationMs, this.sampleRateHz),
        );
        this.nextSequence += 1;
        continue;
      }
      if (next.sequence < this.nextSequence) {
        this.pending.shift();
        continue;
      }
      this.pending.shift();
      released.push(next);
      this.nextSequence += 1;
      if (!flush && this.pending.length < this.targetFrames) {
        break;
      }
    }
    return released;
  }
}
