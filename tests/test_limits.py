"""Resource-limit tests. These exercise pure helpers, not a media server."""

from __future__ import annotations

import pytest

from sentinel.limits import (
    CallBudget,
    ConcurrencyGate,
    EventRateLimiter,
    JitterClass,
    KeyedEventLimiter,
    LimitAction,
    LimitReason,
    ResourceLimits,
    action_for,
    check_prompt_length,
    check_ws_message,
    classify_packet_delay,
    evaluate_audio_frame,
)


def _tight() -> ResourceLimits:
    return ResourceLimits(
        max_concurrent_calls=3,
        max_call_duration_seconds=10,
        max_audio_bytes_per_call=1_000,
        max_audio_bytes_per_second=100,
        max_ws_message_bytes=64,
        max_webhook_body_bytes=128,
        max_events_per_minute=5,
        max_transcript_chars=20,
        max_prompt_chars=16,
        audio_window_seconds=1,
        max_jitter_seconds=0.2,
    )


def test_audio_flood_exceeds_bytes_per_second_and_does_not_persist() -> None:
    limits = _tight()
    budget = CallBudget(limits)
    first = budget.note_audio(80, at=0)
    flood = budget.note_audio(80, at=0.2)
    assert first.reason is LimitReason.OK
    assert flood.reason is LimitReason.AUDIO_RATE
    assert action_for(flood.reason) is LimitAction.END_CALL
    assert budget.audio_total == 80
    later = budget.note_audio(80, at=1.2)
    assert later.reason is LimitReason.OK
    assert budget.audio_total == 160


def test_single_chunk_over_the_rate_cap_is_refused() -> None:
    budget = CallBudget(_tight())
    decision = budget.note_audio(101, at=0)
    assert decision.reason is LimitReason.AUDIO_RATE
    assert budget.audio_total == 0


def test_extremely_long_call_is_cut_off() -> None:
    budget = CallBudget(_tight())
    assert budget.note_elapsed(10).reason is LimitReason.OK
    ended = budget.note_elapsed(10.01)
    assert ended.reason is LimitReason.DURATION
    assert action_for(ended.reason) is LimitAction.END_CALL


def test_audio_total_ends_the_call_without_counting_the_overflow() -> None:
    budget = CallBudget(_tight())
    assert budget.note_audio(100, at=0).reason is LimitReason.OK
    assert budget.note_audio(100, at=2).reason is LimitReason.OK
    for second in range(3, 11):
        assert budget.note_audio(100, at=second).reason is LimitReason.OK
    overflow = budget.note_audio(1, at=20)
    assert overflow.reason is LimitReason.AUDIO_TOTAL
    assert budget.audio_total == 1_000


def test_rapid_concurrent_calls_past_capacity() -> None:
    gate = ConcurrencyGate(_tight())
    assert gate.try_acquire("call-1").reason is LimitReason.OK
    assert gate.try_acquire("call-2").reason is LimitReason.OK
    assert gate.try_acquire("call-3").reason is LimitReason.OK
    refused = gate.try_acquire("call-4")
    assert refused.reason is LimitReason.CONCURRENCY
    assert action_for(refused.reason) is LimitAction.REJECT_INPUT
    assert gate.active_count == 3


def test_same_call_id_does_not_consume_a_second_slot() -> None:
    gate = ConcurrencyGate(_tight())
    assert gate.try_acquire("call-1").reason is LimitReason.OK
    assert gate.try_acquire("call-1").reason is LimitReason.OK
    assert gate.active_count == 1
    gate.release("call-1")
    assert gate.active_count == 0
    assert gate.try_acquire("call-2").reason is LimitReason.OK


def test_releasing_a_slot_allows_a_waiting_call() -> None:
    gate = ConcurrencyGate(_tight())
    for index in range(3):
        gate.try_acquire(f"call-{index}")
    gate.release("call-0")
    assert gate.try_acquire("call-3").reason is LimitReason.OK


def test_event_rate_exhaustion() -> None:
    limiter = EventRateLimiter(_tight())
    for index in range(5):
        assert limiter.allow(at=index).reason is LimitReason.OK
    denied = limiter.allow(at=5)
    assert denied.reason is LimitReason.EVENT_RATE
    assert limiter.allow(at=65).reason is LimitReason.OK


def test_transcript_and_prompt_exhaustion() -> None:
    limits = _tight()
    budget = CallBudget(limits)
    assert budget.note_transcript(20).reason is LimitReason.OK
    assert budget.note_transcript(21).reason is LimitReason.TRANSCRIPT
    assert check_prompt_length(16, limits).reason is LimitReason.OK
    prompt = check_prompt_length(17, limits)
    assert prompt.reason is LimitReason.PROMPT
    assert action_for(prompt.reason) is LimitAction.END_CALL


def test_websocket_message_cap() -> None:
    limits = _tight()
    assert check_ws_message(64, limits).reason is LimitReason.OK
    assert check_ws_message(65, limits).reason is LimitReason.WS_MESSAGE
    assert check_ws_message(-1, limits).reason is LimitReason.INVALID_AMOUNT


def test_many_tiny_frames_trip_the_window_sample_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    budget = CallBudget(_tight())
    monkeypatch.setattr("sentinel.limits._MAX_WINDOW_SAMPLES", 3)
    assert budget.note_audio(1, at=0.0).reason is LimitReason.OK
    assert budget.note_audio(1, at=0.1).reason is LimitReason.OK
    assert budget.note_audio(1, at=0.2).reason is LimitReason.OK
    flooded = budget.note_audio(1, at=0.3)
    assert flooded.reason is LimitReason.AUDIO_RATE
    assert budget.audio_total == 3


def test_late_frames_are_counted_and_not_played() -> None:
    limits = _tight()
    budget = CallBudget(limits)
    played = evaluate_audio_frame(budget, 40, at=1.0, delay_seconds=0.1, limits=limits)
    late = evaluate_audio_frame(budget, 40, at=2.0, delay_seconds=0.5, limits=limits)
    invalid = evaluate_audio_frame(budget, 10, at=3.0, delay_seconds=-1, limits=limits)
    assert played.playable is True and played.accounted is True
    assert late.playable is False and late.accounted is True
    assert late.reason is LimitReason.JITTER
    assert invalid.accounted is True and invalid.playable is False
    assert budget.audio_total == 90
    assert classify_packet_delay(0.2, max_jitter_seconds=0.2) is JitterClass.ON_TIME
    assert classify_packet_delay(float("nan")) is JitterClass.INVALID


def test_negative_audio_does_not_change_the_budget() -> None:
    budget = CallBudget(_tight())
    assert budget.note_audio(-5, at=0).reason is LimitReason.INVALID_AMOUNT
    assert budget.audio_total == 0


def test_every_limit_reason_has_an_action() -> None:
    seen: set[LimitAction] = set()
    for reason in LimitReason:
        seen.add(action_for(reason))
    assert seen == {LimitAction.CONTINUE, LimitAction.REJECT_INPUT, LimitAction.END_CALL}


def test_keyed_limiter_isolates_clients_and_fails_closed_when_full() -> None:
    limits = ResourceLimits(max_events_per_minute=1)
    limiter = KeyedEventLimiter(limits, max_keys=1)
    assert limiter.allow("client-a", at=0).reason is LimitReason.OK
    assert limiter.allow("client-a", at=1).reason is LimitReason.EVENT_RATE
    refused = limiter.allow("client-b", at=0)
    assert refused.reason is LimitReason.EVENT_RATE
    assert action_for(refused.reason) is LimitAction.REJECT_INPUT
    assert limiter.allow("", at=0).reason is LimitReason.INVALID_AMOUNT


def test_empty_call_id_is_rejected() -> None:
    gate = ConcurrencyGate(_tight())
    assert gate.try_acquire("").reason is LimitReason.INVALID_AMOUNT
    assert gate.active_count == 0
