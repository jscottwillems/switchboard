"""Pure resource limits for calls, audio, events, and websocket frames.

No media server is required. Adapters call these helpers before buffering.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from sentinel._never import assert_never

_MAX_WINDOW_SAMPLES = 4096
_CALL_ID_MIN = 1
_CALL_ID_MAX = 128


class LimitReason(Enum):
    OK = "ok"
    INVALID_AMOUNT = "invalid_amount"
    CONCURRENCY = "concurrency"
    DURATION = "duration"
    AUDIO_TOTAL = "audio_total"
    AUDIO_RATE = "audio_rate"
    WS_MESSAGE = "ws_message"
    EVENT_RATE = "event_rate"
    TRANSCRIPT = "transcript"
    PROMPT = "prompt"
    JITTER = "jitter"


class LimitAction(Enum):
    CONTINUE = "continue"
    REJECT_INPUT = "reject_input"
    END_CALL = "end_call"


@dataclass(frozen=True, slots=True)
class LimitDecision:
    allowed: bool
    reason: LimitReason

    def __post_init__(self) -> None:
        if self.allowed != (self.reason is LimitReason.OK):
            raise ValueError("allowed must agree with reason")


@dataclass(frozen=True, slots=True)
class AudioFrameDecision:
    """`accounted` means the bytes count toward the call budget even when not played."""

    accounted: bool
    playable: bool
    reason: LimitReason


@dataclass(frozen=True, slots=True)
class ResourceLimits:
    """Defaults proposed for adapters. ATLAS's SECURITY.md confirms the policy."""

    max_concurrent_calls: int = 50
    max_call_duration_seconds: float = 1800
    max_audio_bytes_per_call: int = 25 * 1024 * 1024
    max_audio_bytes_per_second: int = 64 * 1024
    max_ws_message_bytes: int = 64 * 1024
    max_webhook_body_bytes: int = 1_048_576
    max_events_per_minute: int = 600
    max_transcript_chars: int = 100_000
    max_prompt_chars: int = 32_000
    audio_window_seconds: float = 1.0
    max_jitter_seconds: float = 0.2

    def __post_init__(self) -> None:
        numeric = {
            "max_concurrent_calls": self.max_concurrent_calls,
            "max_call_duration_seconds": self.max_call_duration_seconds,
            "max_audio_bytes_per_call": self.max_audio_bytes_per_call,
            "max_audio_bytes_per_second": self.max_audio_bytes_per_second,
            "max_ws_message_bytes": self.max_ws_message_bytes,
            "max_webhook_body_bytes": self.max_webhook_body_bytes,
            "max_events_per_minute": self.max_events_per_minute,
            "max_transcript_chars": self.max_transcript_chars,
            "max_prompt_chars": self.max_prompt_chars,
            "audio_window_seconds": self.audio_window_seconds,
            "max_jitter_seconds": self.max_jitter_seconds,
        }
        for name, value in numeric.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                raise ValueError(f"{name} must be positive")


class JitterClass(Enum):
    ON_TIME = "on_time"
    LATE = "late"
    INVALID = "invalid"


def action_for(reason: LimitReason) -> LimitAction:
    """What an adapter should do with a limit decision."""
    match reason:
        case LimitReason.OK:
            return LimitAction.CONTINUE
        case (
            LimitReason.INVALID_AMOUNT
            | LimitReason.CONCURRENCY
            | LimitReason.WS_MESSAGE
            | LimitReason.EVENT_RATE
            | LimitReason.JITTER
        ):
            return LimitAction.REJECT_INPUT
        case (
            LimitReason.DURATION
            | LimitReason.AUDIO_TOTAL
            | LimitReason.AUDIO_RATE
            | LimitReason.TRANSCRIPT
            | LimitReason.PROMPT
        ):
            return LimitAction.END_CALL
    assert_never(reason)


def classify_packet_delay(
    delay_seconds: float,
    *,
    max_jitter_seconds: float = 0.2,
) -> JitterClass:
    """Classify media delay. Does not perform I/O."""
    if isinstance(delay_seconds, bool) or not isinstance(delay_seconds, (int, float)):
        return JitterClass.INVALID
    if not math.isfinite(float(delay_seconds)) or delay_seconds < 0:
        return JitterClass.INVALID
    if delay_seconds > max_jitter_seconds:
        return JitterClass.LATE
    return JitterClass.ON_TIME


def check_ws_message(nbytes: int, limits: ResourceLimits | None = None) -> LimitDecision:
    limits = limits or ResourceLimits()
    if isinstance(nbytes, bool) or not isinstance(nbytes, int) or nbytes < 0:
        return LimitDecision(False, LimitReason.INVALID_AMOUNT)
    if nbytes > limits.max_ws_message_bytes:
        return LimitDecision(False, LimitReason.WS_MESSAGE)
    return LimitDecision(True, LimitReason.OK)


def check_transcript_length(total_chars: int, limits: ResourceLimits | None = None) -> LimitDecision:
    return _check_char_budget(
        total_chars,
        (limits or ResourceLimits()).max_transcript_chars,
        LimitReason.TRANSCRIPT,
    )


def check_prompt_length(total_chars: int, limits: ResourceLimits | None = None) -> LimitDecision:
    return _check_char_budget(
        total_chars,
        (limits or ResourceLimits()).max_prompt_chars,
        LimitReason.PROMPT,
    )


class ConcurrencyGate:
    """Admission control for simultaneous calls. Same call id is idempotent."""

    def __init__(self, limits: ResourceLimits | None = None) -> None:
        self._limits = limits or ResourceLimits()
        self._active: set[str] = set()

    def try_acquire(self, call_id: str) -> LimitDecision:
        if not _valid_call_id(call_id):
            return LimitDecision(False, LimitReason.INVALID_AMOUNT)
        if call_id in self._active:
            return LimitDecision(True, LimitReason.OK)
        if len(self._active) >= self._limits.max_concurrent_calls:
            return LimitDecision(False, LimitReason.CONCURRENCY)
        self._active.add(call_id)
        return LimitDecision(True, LimitReason.OK)

    def release(self, call_id: str) -> None:
        self._active.discard(call_id)

    @property
    def active_count(self) -> int:
        return len(self._active)


class CallBudget:
    """Per-call audio, duration, and transcript accounting. Rejected audio is not stored."""

    def __init__(self, limits: ResourceLimits | None = None) -> None:
        self._limits = limits or ResourceLimits()
        self._audio_total = 0
        self._window: list[tuple[float, int]] = []

    @property
    def audio_total(self) -> int:
        return self._audio_total

    def note_elapsed(self, seconds: float) -> LimitDecision:
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or seconds < 0:
            return LimitDecision(False, LimitReason.INVALID_AMOUNT)
        if not math.isfinite(float(seconds)):
            return LimitDecision(False, LimitReason.INVALID_AMOUNT)
        if seconds > self._limits.max_call_duration_seconds:
            return LimitDecision(False, LimitReason.DURATION)
        return LimitDecision(True, LimitReason.OK)

    def note_audio(self, nbytes: int, *, at: float) -> LimitDecision:
        if isinstance(nbytes, bool) or not isinstance(nbytes, int) or nbytes < 0:
            return LimitDecision(False, LimitReason.INVALID_AMOUNT)
        if isinstance(at, bool) or not isinstance(at, (int, float)) or not math.isfinite(float(at)) or at < 0:
            return LimitDecision(False, LimitReason.INVALID_AMOUNT)
        if nbytes == 0:
            return LimitDecision(True, LimitReason.OK)
        if self._audio_total + nbytes > self._limits.max_audio_bytes_per_call:
            return LimitDecision(False, LimitReason.AUDIO_TOTAL)
        window_start = float(at) - self._limits.audio_window_seconds
        self._window = [(stamp, size) for stamp, size in self._window if window_start < stamp <= at]
        if len(self._window) >= _MAX_WINDOW_SAMPLES:
            return LimitDecision(False, LimitReason.AUDIO_RATE)
        in_window = sum(size for _, size in self._window)
        if in_window + nbytes > self._limits.max_audio_bytes_per_second:
            return LimitDecision(False, LimitReason.AUDIO_RATE)
        self._audio_total += nbytes
        self._window.append((float(at), nbytes))
        return LimitDecision(True, LimitReason.OK)

    def note_transcript(self, total_chars: int) -> LimitDecision:
        return check_transcript_length(total_chars, self._limits)


class EventRateLimiter:
    """Sliding 60-second counter. Denied events are not recorded."""

    def __init__(self, limits: ResourceLimits | None = None) -> None:
        self._limits = limits or ResourceLimits()
        self._times: list[float] = []

    def allow(self, *, at: float) -> LimitDecision:
        if isinstance(at, bool) or not isinstance(at, (int, float)) or not math.isfinite(float(at)) or at < 0:
            return LimitDecision(False, LimitReason.INVALID_AMOUNT)
        cutoff = float(at) - 60.0
        self._times = [stamp for stamp in self._times if cutoff < stamp <= at]
        if len(self._times) >= self._limits.max_events_per_minute:
            return LimitDecision(False, LimitReason.EVENT_RATE)
        self._times.append(float(at))
        return LimitDecision(True, LimitReason.OK)


class KeyedEventLimiter:
    """Separate minute-window per key. A full key map fails closed instead of evicting."""

    def __init__(self, limits: ResourceLimits | None = None, *, max_keys: int = 10_000) -> None:
        if max_keys < 1:
            raise ValueError("max_keys must be positive")
        self._limits = limits or ResourceLimits()
        self._max_keys = max_keys
        self._buckets: dict[str, EventRateLimiter] = {}

    def allow(self, key: str, *, at: float) -> LimitDecision:
        if not isinstance(key, str) or key == "":
            return LimitDecision(False, LimitReason.INVALID_AMOUNT)
        bucket = self._buckets.get(key)
        if bucket is None:
            if len(self._buckets) >= self._max_keys:
                return LimitDecision(False, LimitReason.EVENT_RATE)
            bucket = EventRateLimiter(self._limits)
            self._buckets[key] = bucket
        return bucket.allow(at=at)


def evaluate_audio_frame(
    budget: CallBudget,
    nbytes: int,
    *,
    at: float,
    delay_seconds: float,
    limits: ResourceLimits | None = None,
) -> AudioFrameDecision:
    """Count bytes first, then decide whether the frame may be played.

    Late and invalid delays still consume the budget so a sender cannot bypass
    the cap by marking frames late.
    """
    limits = limits or ResourceLimits()
    decision = budget.note_audio(nbytes, at=at)
    if not decision.allowed:
        return AudioFrameDecision(False, False, decision.reason)
    jitter = classify_packet_delay(delay_seconds, max_jitter_seconds=limits.max_jitter_seconds)
    match jitter:
        case JitterClass.ON_TIME:
            return AudioFrameDecision(True, True, LimitReason.OK)
        case JitterClass.LATE:
            return AudioFrameDecision(True, False, LimitReason.JITTER)
        case JitterClass.INVALID:
            return AudioFrameDecision(True, False, LimitReason.INVALID_AMOUNT)
    assert_never(jitter)


def _check_char_budget(total_chars: int, cap: int, reason: LimitReason) -> LimitDecision:
    if isinstance(total_chars, bool) or not isinstance(total_chars, int) or total_chars < 0:
        return LimitDecision(False, LimitReason.INVALID_AMOUNT)
    if total_chars > cap:
        return LimitDecision(False, reason)
    return LimitDecision(True, LimitReason.OK)


def _valid_call_id(call_id: str) -> bool:
    if not isinstance(call_id, str):
        return False
    if not _CALL_ID_MIN <= len(call_id) <= _CALL_ID_MAX:
        return False
    return all(ch.isalnum() or ch in "_.:-" for ch in call_id)

