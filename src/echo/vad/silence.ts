/** Trailing-silence endpoint. Counts consecutive unvoiced audio and fires once. */
export class SilenceDetector {
  private accumulatedMs = 0;

  constructor(
    private readonly thresholdMs: number,
    private readonly frameMs: number,
  ) {}

  reset(): void {
    this.accumulatedMs = 0;
  }

  /** Returns true on the frame that reaches the endpoint threshold. */
  observe(voiced: boolean): boolean {
    if (voiced) {
      this.accumulatedMs = 0;
      return false;
    }
    this.accumulatedMs += this.frameMs;
    return this.accumulatedMs >= this.thresholdMs;
  }
}
