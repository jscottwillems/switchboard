import assert from "node:assert/strict";
import test from "node:test";

import { ECHO_MEDIA } from "../../src/echo/media.js";
import { EnergyVad } from "../../src/echo/vad/energy.js";
import { SilenceDetector } from "../../src/echo/vad/silence.js";
import { silenceFrame, sineFrame } from "./helpers.js";

test("silence detector endpoints after the configured trailing window", () => {
  const detector = new SilenceDetector(ECHO_MEDIA.silenceToEndpointMs, ECHO_MEDIA.frameDurationMs);
  const framesToEndpoint = ECHO_MEDIA.silenceToEndpointMs / ECHO_MEDIA.frameDurationMs;
  for (let i = 0; i < framesToEndpoint - 1; i += 1) {
    assert.equal(detector.observe(false), false);
  }
  assert.equal(detector.observe(false), true);
  detector.reset();
  assert.equal(detector.observe(false), false);
});

test("energy VAD confirms speech and ignores short gaps", () => {
  const vad = new EnergyVad();
  assert.equal(vad.push(silenceFrame(0)).event, null);

  const first = vad.push(sineFrame(1));
  assert.equal(first.event, null);
  const started = vad.push(sineFrame(2));
  assert.equal(started.event?.type, "speech_start");
  assert.equal(started.event && started.event.type === "speech_start" ? started.event.audioTimeMs : -1, 20);

  for (let i = 0; i < 9; i += 1) {
    assert.equal(vad.push(silenceFrame(3 + i)).event, null);
  }
  assert.equal(vad.push(sineFrame(12)).voiced, true);
});

test("energy VAD emits speech end after trailing silence", () => {
  const vad = new EnergyVad();
  vad.push(sineFrame(0));
  vad.push(sineFrame(1));
  const silenceFrames = ECHO_MEDIA.silenceToEndpointMs / ECHO_MEDIA.frameDurationMs;
  let ended = false;
  for (let i = 0; i < silenceFrames; i += 1) {
    const observation = vad.push(silenceFrame(2 + i));
    ended = observation.event?.type === "speech_end";
  }
  assert.equal(ended, true);
});
