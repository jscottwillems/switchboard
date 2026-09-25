"""Deterministic μ-law tone returned on the media path until ECHO replaces it."""

import math

from switchboard.media.mulaw import linear_to_mulaw

SAMPLE_RATE = 8000
FRAME_SAMPLES = 160
TONE_HZ = 440
TONE_AMPLITUDE = 8000


def fixed_response_frame() -> bytes:
    """20 ms of 440 Hz μ-law audio at 8 kHz (160 bytes)."""

    frame = bytearray(FRAME_SAMPLES)
    for index in range(FRAME_SAMPLES):
        pcm = int(TONE_AMPLITUDE * math.sin(2 * math.pi * TONE_HZ * index / SAMPLE_RATE))
        frame[index] = linear_to_mulaw(pcm)
    return bytes(frame)
