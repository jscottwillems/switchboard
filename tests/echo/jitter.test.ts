import assert from "node:assert/strict";
import test from "node:test";

import { frameRms } from "../../src/echo/audio/pcm.js";
import { JitterBuffer } from "../../src/echo/audio/jitterBuffer.js";
import { ECHO_MEDIA } from "../../src/echo/media.js";
import { sineFrame } from "./helpers.js";

test("jitter buffer delays release until it holds three frames", () => {
  const buffer = new JitterBuffer();
  assert.equal(buffer.push(sineFrame(0)).length, 0);
  assert.equal(buffer.push(sineFrame(1)).length, 0);
  const released = buffer.push(sineFrame(2));
  assert.deepEqual(
    released.map((frame) => frame.sequence),
    [0],
  );
  const flushed = buffer.flush();
  assert.deepEqual(
    flushed.map((frame) => frame.sequence),
    [1, 2],
  );
});

test("jitter buffer fills missing sequence numbers with silence", () => {
  const buffer = new JitterBuffer();
  const released = [...buffer.push(sineFrame(0)), ...buffer.push(sineFrame(1)), ...buffer.push(sineFrame(3))];
  assert.deepEqual(
    released.map((frame) => frame.sequence),
    [0],
  );
  const flushed = buffer.flush();
  assert.deepEqual(
    flushed.map((frame) => frame.sequence),
    [1, 2, 3],
  );
  const gap = flushed[1];
  assert.ok(gap);
  assert.equal(frameRms(gap.samples), 0);
  assert.equal(gap.sampleRateHz, ECHO_MEDIA.sampleRateHz);
  assert.equal(gap.samples.length, ECHO_MEDIA.samplesPerFrame);
});
