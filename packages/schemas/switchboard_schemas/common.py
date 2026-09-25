"""Shared contract types.

Pydantic models in this package are the machine-readable source of truth.
TypeScript stubs under packages/schemas/ts mirror them for the dashboard.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

CONTRACT_VERSION = "0.1.0"

# Namespace for deterministic stub identifiers (UUIDv5). Not a call id.
SWITCHBOARD_ID_NAMESPACE = UUID("6f0d8a1e-7c2b-5a44-9e11-0a6c3d8b2f70")


def _require_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError("datetime must be timezone-aware")
    return value


AwareDatetime = Annotated[datetime, AfterValidator(_require_aware)]

Confidence = Annotated[
    float,
    Field(
        ge=0.0,
        le=1.0,
        description=(
            "Producer certainty that it followed its own method. "
            "This is not a probability that the claim is true in the world, "
            "and it is not a speech-to-text provider score."
        ),
    ),
]

E164 = Annotated[
    str,
    Field(
        pattern=r"^\+[1-9]\d{1,14}$",
        description="Observed E.164 signaling number. Untrusted. May be spoofed.",
    ),
]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
