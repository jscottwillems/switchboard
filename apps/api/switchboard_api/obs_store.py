"""Observation store for the voice webhook and the status callback.

The SQL lives in `switchboard_repositories.TelephonyObsStore`. This module binds
that store to the API database URL so `get_obs_store()` keeps the same calls:
active operator lookup, idempotent ringing insert, forward state updates, and
an append-only receipt.
"""

from switchboard_repositories import TelephonyObsStore

from switchboard_api.settings import get_settings


def get_obs_store() -> TelephonyObsStore:
    return TelephonyObsStore(get_settings().database_url)
