"""Exhaustive-match helper for enums and unions."""

from __future__ import annotations

from typing import Never


def assert_never(value: Never) -> Never:
    """Fail when a newly added variant was not handled."""
    raise AssertionError(f"unhandled variant: {value!r}")
