"""Raw observations. Each one is a span of the transcript, not a conclusion."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from switchboard_intelligence.schemas.common import (
    SCHEMA_VERSION,
    CallRelativeSeconds,
    Confidence,
)


class ObservationKind(str, Enum):
    """Indicator kinds Sherlock stores.

    Add a member when an indicator becomes first-class. Until then, put
    unmatched identifiers on `other`. String values are the cross-language
    contract; regenerate TypeScript after changing them.
    """

    CLAIMED_COMPANY = "claimed_company"
    CLAIMED_AGENT = "claimed_agent"
    CLAIMED_DEPARTMENT = "claimed_department"
    CALLBACK_NUMBERS = "callback_numbers"
    SPOKEN_NUMBERS = "spoken_numbers"
    DOMAINS = "domains"
    URLS = "urls"
    EMAIL_ADDRESSES = "email_addresses"
    LOAN_AMOUNTS = "loan_amounts"
    RATES = "rates"
    FEES = "fees"
    REQUESTED_INFORMATION = "requested_information"
    PAYMENT_METHODS = "payment_methods"
    SCRIPT_PHRASES = "script_phrases"
    URGENCY_LANGUAGE = "urgency_language"
    TRANSFER_EVENTS = "transfer_events"
    OTHER = "other"


class Observation(BaseModel):
    """A value taken from a transcript span.

    Required on every observation: `value`, `source`, `transcript_segment_id`,
    `start_timestamp`, `end_timestamp`, and `confidence`. `value` is the
    exact substring `text[char_start:char_end]` of that segment. Conclusions
    that are not a verbatim span belong on Inference, not here.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["sherlock.intelligence.v1"] = SCHEMA_VERSION
    record_type: Literal["observation"] = "observation"
    observation_id: str = Field(min_length=1)
    call_id: str = Field(min_length=1)
    kind: ObservationKind
    value: str = Field(min_length=1)
    normalized_value: str = Field(min_length=1)
    source: str = Field(min_length=1, max_length=200)
    transcript_segment_id: str = Field(min_length=1)
    start_timestamp: CallRelativeSeconds
    end_timestamp: CallRelativeSeconds
    char_start: int = Field(ge=0)
    char_end: int = Field(ge=0)
    confidence: Confidence

    @model_validator(mode="after")
    def span_is_ordered(self) -> "Observation":
        if self.end_timestamp < self.start_timestamp:
            raise ValueError("end_timestamp must be greater than or equal to start_timestamp")
        if self.char_end < self.char_start:
            raise ValueError("char_end must be greater than or equal to char_start")
        return self
