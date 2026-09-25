/**
 * Media contract ECHO implements today and expects from BELL.
 * Narrative draft lives in docs/echo/MEDIA_REQUIREMENTS.md. Keep the two in sync.
 * Do not copy this into shared contract docs until ATLAS publishes them.
 */
export const ECHO_MEDIA = {
  codec: "pcm_s16le",
  sampleRateHz: 16000,
  acceptedSampleRatesHz: [16000, 8000] as const,
  channels: 1,
  bitsPerSample: 16,
  endianness: "little" as const,
  frameDurationMs: 20,
  samplesPerFrame: 320,
  bytesPerFrame: 640,
  /** Frames held before the oldest is released to VAD. */
  jitterFrames: 3,
  /**
   * Delay added when a frame leaves the jitter buffer.
   * The buffer releases the oldest frame once 3 frames are queued, which is
   * 40 ms after that frame arrived, and the newest frame is still 20 ms long.
   */
  jitterDelayMs: 60,
  vadRmsThreshold: 400,
  speechStartFrames: 2,
  silenceToEndpointMs: 500,
  maxUtteranceMs: 15_000,
  bargeIn: {
    inFlightFrameMs: 20,
    dropQueuedFrames: true,
  },
} as const;

export const MOCK_LATENCY = {
  sttFinalizeMs: 40,
  decisionMs: 20,
  ttsFirstByteMs: 30,
  msPerWord: 160,
} as const;
