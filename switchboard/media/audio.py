"""Deterministic μ-law tone returned on the media path until ECHO replaces it."""

import math

from switchboard.media.mulaw import linear_to_mulaw

SAMPLE_RATE = 8000
FRAME_SAMPLES = 160
TONE_HZ = 440
TONE_AMPLITUDE = 8000


def fixed_response_frame() -> bytes:
    """20 ms of 440 Hz μ-law, 8 kHz, mono (160 bytes).

    Samples are synthesized as linear PCM only inside this function, then
    converted with `linear_to_mulaw` before the bytes are returned. Callers
    put the return value on the provider wire as-is.
    """

    frame = bytearray(FRAME_SAMPLES)
    for index in range(FRAME_SAMPLES):
        linear = int(TONE_AMPLITUDE * math.sin(2 * math.pi * TONE_HZ * index / SAMPLE_RATE))
        frame[index] = linear_to_mulaw(linear)
    return bytes(frame)
