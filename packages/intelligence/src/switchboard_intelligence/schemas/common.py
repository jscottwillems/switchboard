"""Shared field types for Sherlock records."""

from typing import Annotated

from pydantic import Field

SCHEMA_VERSION = "sherlock.intelligence.v1"

Confidence = Annotated[
    float,
    Field(ge=0.0, le=1.0, description="Explicit confidence in the closed interval [0, 1]."),
]

CallRelativeSeconds = Annotated[
    float,
    Field(ge=0.0, description="Seconds from the start of the call."),
]
