"""Correlation-facing indicators WATSON consumes.

SHERLOCK's package is not on main. The landed branch
`cursor/sherlock-intelligence-slice-1574` exports span Observations and a
proposition-style Inference. It does not yet carry the correlation fields
below. This module is the thin adapter. When that PR grows the correlation
contract, import these names from:

- `switchboard_intelligence.schemas.observation.Observation`
- `switchboard_intelligence.schemas.observation.ObservationKind`
- `switchboard_intelligence.schemas.inference` for the correlation inference
  fields (`claimed_company_normalized`, `phone_e164`, `domain_registrable`,
  `email` local/domain split, `email_domain_registrable`,
  `script_phrase_normalized`, `opening_script_fingerprint`,
  `pretext_category_canonical`, `identifier_kind`)

No dense vectors. Campaign ids are not Sherlock's to assign.
"""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION: Literal["sherlock.intelligence.v1"] = "sherlock.intelligence.v1"


class ObservationKind(str, Enum):
    """Transcript-grounded kinds.

    The first block is the LOKI elicitation list from Sherlock's observation
    enum. The second block is the correlation contract added for WATSON.
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
    OPENING_TURNS = "opening_turns"
    OPENING_SCRIPT_TEXT = "opening_script_text"
    IVR_PROMPTS = "ivr_prompts"
    TRANSFER_DESTINATION_CLAIMED = "transfer_destination_claimed"
    CALLING_FROM = "calling_from"
    SCRIPT_LANGUAGE = "script_language"


class Observation(BaseModel):
    """Verbatim transcript span. Same fields as Sherlock's Observation record."""

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
    start_timestamp: float = Field(ge=0)
    end_timestamp: float = Field(ge=0)
    char_start: int = Field(ge=0)
    char_end: int = Field(ge=0)
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def span_is_ordered(self) -> "Observation":
        if self.end_timestamp < self.start_timestamp:
            raise ValueError("end_timestamp must be greater than or equal to start_timestamp")
        if self.char_end < self.char_start:
            raise ValueError("char_end must be greater than or equal to char_start")
        return self


class PhoneE164(BaseModel):
    """One inferred phone. `source` is callback or spoken."""

    model_config = ConfigDict(extra="forbid")

    phone_e164: str = Field(min_length=1)
    source: Literal["callback", "spoken"]


class EmailSplit(BaseModel):
    """Email local/domain split plus the registrable domain."""

    model_config = ConfigDict(extra="forbid")

    local: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    email_domain_registrable: str = Field(min_length=1)


class CorrelationInference(BaseModel):
    """Sherlock-emitted judgments. Confidence is separate from observations.

    `email` holds the local/domain split. `email_domain_registrable` is the
    registrable-domain list. There is no embedding field.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["sherlock.intelligence.v1"] = SCHEMA_VERSION
    call_id: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    claimed_company_normalized: str | None = None
    phone_e164: list[PhoneE164] = Field(default_factory=list)
    domain_registrable: list[str] = Field(default_factory=list)
    email: list[EmailSplit] = Field(default_factory=list)
    email_domain_registrable: list[str] = Field(default_factory=list)
    script_phrase_normalized: list[str] = Field(default_factory=list)
    opening_script_fingerprint: str | None = None
    pretext_category_canonical: str | None = None
    identifier_kind: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def registrable_domains_cover_splits(self) -> "CorrelationInference":
        from_splits = [item.email_domain_registrable for item in self.email]
        if from_splits and self.email_domain_registrable != from_splits:
            raise ValueError("email_domain_registrable must match email splits in order")
        return self


class CallIntelligence(BaseModel):
    """Observations plus the correlation inference for one completed call."""

    model_config = ConfigDict(extra="forbid")

    call_id: str = Field(min_length=1)
    observations: list[Observation]
    inference: CorrelationInference | None = None
