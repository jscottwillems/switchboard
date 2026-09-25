"""G.711 μ-law encoder used for the fixed reply frame.

Python 3.13 removed the stdlib audioop module, so the slice carries the
small encoder it needs.
"""

_BIAS = 0x84
_CLIP = 32635


def linear_to_mulaw(sample: int) -> int:
    """Encode one 16-bit PCM sample as a μ-law byte."""

    sign = 0
    if sample < 0:
        sign = 0x80
        sample = -sample
    if sample > _CLIP:
        sample = _CLIP
    sample += _BIAS
    exponent = 7
    mask = 0x4000
    while exponent > 0 and (sample & mask) == 0:
        exponent -= 1
        mask >>= 1
    mantissa = (sample >> (exponent + 3)) & 0x0F
    return (~(sign | (exponent << 4) | mantissa)) & 0xFF
