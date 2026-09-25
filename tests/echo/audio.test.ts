import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { decodePcmS16le, encodePcmS16le, frameRms, framesFromSamples } from "../../src/echo/audio/pcm.js";
import { normalizeFrame, normalizeSamples } from "../../src/echo/audio/normalize.js";
import { readWav, writeWav } from "../../src/echo/audio/wav.js";
import { ECHO_MEDIA } from "../../src/echo/media.js";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");

test("pcm s16le is little-endian", () => {
  const samples = Int16Array.of(0x0102, -2);
  const bytes = encodePcmS16le(samples);
  assert.deepEqual(Array.from(bytes), [0x02, 0x01, 0xfe, 0xff]);
  assert.deepEqual(Array.from(decodePcmS16le(bytes)), [0x0102, -2]);
});

test("wav roundtrip keeps mono pcm", () => {
  const samples = Int16Array.from([0, 1000, -1000, 42]);
  const decoded = readWav(writeWav(samples, ECHO_MEDIA.sampleRateHz));
  assert.equal(decoded.sampleRateHz, ECHO_MEDIA.sampleRateHz);
  assert.equal(decoded.channels, 1);
  assert.deepEqual(Array.from(decoded.samples), Array.from(samples));
});

test("normalize downmixes stereo and upsamples 8 kHz to 16 kHz", () => {
  const stereo = Int16Array.of(1000, 3000, -1000, -3000);
  const mono = normalizeSamples(stereo, 16000, 2);
  assert.deepEqual(Array.from(mono), [2000, -2000]);

  const narrow = normalizeSamples(Int16Array.of(0, 1000), 8000, 1);
  assert.equal(narrow.length, 4);
  assert.equal(narrow[0], 0);
  assert.equal(narrow[1], 500);
  assert.equal(narrow[2], 1000);
});

test("8 kHz 20 ms frames become 16 kHz 320-sample frames", () => {
  const frame = {
    sequence: 3,
    audioTimeMs: 60,
    sampleRateHz: 8000,
    samples: Int16Array.from({ length: 160 }, () => 1000),
  };
  const normalized = normalizeFrame(frame);
  assert.equal(normalized.sampleRateHz, 16000);
  assert.equal(normalized.samples.length, ECHO_MEDIA.samplesPerFrame);
  assert.equal(normalized.sequence, 3);
  assert.equal(normalized.audioTimeMs, 60);
});

test("sample call fixture matches the ECHO media contract", () => {
  const wav = readWav(new Uint8Array(readFileSync(path.join(root, "tests/audio/sample_call.wav"))));
  assert.equal(wav.sampleRateHz, ECHO_MEDIA.sampleRateHz);
  assert.equal(wav.channels, ECHO_MEDIA.channels);
  assert.ok(wav.samples.length / wav.sampleRateHz > 4);
  const frames = framesFromSamples(wav.samples, wav.sampleRateHz);
  assert.equal(frames[0]?.samples.length, ECHO_MEDIA.samplesPerFrame);
  assert.equal(frameRms(frames[0]?.samples ?? new Int16Array()), 0);
});
