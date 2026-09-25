export interface Clock {
  nowMs(): number;
  advance(ms: number): void;
  /** Move forward to `ms` when that is later than now. Never moves backward. */
  seek(ms: number): void;
}

export function createManualClock(startMs = 0): Clock {
  let now = startMs;
  return {
    nowMs() {
      return now;
    },
    advance(ms: number) {
      assertAdvance(ms);
      now += ms;
    },
    seek(ms: number) {
      if (!Number.isFinite(ms)) {
        throw new Error(`Clock seek must be finite, received ${ms}`);
      }
      if (ms > now) {
        now = ms;
      }
    },
  };
}

export function createWallClock(): Clock {
  const origin = performance.now();
  let extra = 0;
  return {
    nowMs() {
      return performance.now() - origin + extra;
    },
    advance(ms: number) {
      assertAdvance(ms);
      extra += ms;
    },
    seek(ms: number) {
      if (!Number.isFinite(ms)) {
        throw new Error(`Clock seek must be finite, received ${ms}`);
      }
      const current = performance.now() - origin + extra;
      if (ms > current) {
        extra += ms - current;
      }
    },
  };
}

function assertAdvance(ms: number): void {
  if (!Number.isFinite(ms) || ms < 0) {
    throw new Error(`Clock advance must be a non-negative finite number, received ${ms}`);
  }
}
