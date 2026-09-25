import type { PcmFrame } from "../types.js";

/** Frames synthesized but not yet handed to the outbound sink (BELL, later). */
export class OutboundQueue {
  private frames: PcmFrame[] = [];

  get length(): number {
    return this.frames.length;
  }

  enqueue(frame: PcmFrame): void {
    this.frames.push(frame);
  }

  drain(maxFrames = Number.POSITIVE_INFINITY): PcmFrame[] {
    const count = Math.min(maxFrames, this.frames.length);
    return this.frames.splice(0, count);
  }

  clear(): number {
    const dropped = this.frames.length;
    this.frames = [];
    return dropped;
  }
}
