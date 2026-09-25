"""Forward-only status changes from docs/ARCHITECTURE.md and docs/DATA_MODEL.md."""

from typing import Never

from switchboard_schemas.enums import CallState, MediaStreamState

from switchboard_repositories.errors import StateConflict


def ensure_call_transition(current: CallState, proposed: CallState) -> None:
    match current:
        case CallState.RINGING:
            allowed = {CallState.IN_PROGRESS, CallState.COMPLETED, CallState.FAILED}
        case CallState.IN_PROGRESS:
            allowed = {CallState.COMPLETED, CallState.FAILED}
        case CallState.COMPLETED:
            allowed = set[CallState]()
        case CallState.FAILED:
            allowed = set[CallState]()
        case _ as unreachable:
            _never(unreachable)
    if proposed != current and proposed not in allowed:
        raise StateConflict(
            f"call session cannot move from {current.value} to {proposed.value}"
        )


def ensure_media_transition(current: MediaStreamState, proposed: MediaStreamState) -> None:
    match current:
        case MediaStreamState.CONNECTING:
            allowed = {
                MediaStreamState.STREAMING,
                MediaStreamState.CLOSED,
                MediaStreamState.FAILED,
            }
        case MediaStreamState.STREAMING:
            allowed = {MediaStreamState.CLOSED, MediaStreamState.FAILED}
        case MediaStreamState.CLOSED:
            allowed = set[MediaStreamState]()
        case MediaStreamState.FAILED:
            allowed = set[MediaStreamState]()
        case _ as unreachable:
            _never(unreachable)
    if proposed != current and proposed not in allowed:
        raise StateConflict(
            f"media stream cannot move from {current.value} to {proposed.value}"
        )


def _never(value: Never) -> Never:
    raise AssertionError(f"unhandled state: {value}")
