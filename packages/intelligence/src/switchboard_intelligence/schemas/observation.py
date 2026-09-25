"""Raw observations. Each one is a span of the transcript, not a conclusion."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from switchboard_intelligence.schemas.common import (
    SCHEMA_VERSION,
    CallRelativeSeconds,
    Confidence,
)


class PretextCategory(str, Enum):
    """Coarse purpose class for a `pretext_category` observation."""

    TAX = "tax"
    BANK = "bank"
    WARRANTY = "warranty"
    DEBT = "debt"
    PRIZE = "prize"
    TECH_SUPPORT = "tech_support"
    GOVERNMENT = "government"
    UTILITY = "utility"
    OTHER = "other"


class PaymentMethod(str, Enum):
    """Cash-out rail for a `payment_methods` observation."""

    GIFT_CARD = "gift_card"
    WIRE = "wire"
    CRYPTO = "crypto"
    REMOTE_ACCESS = "remote_access"
    BANK_VERIFY = "bank_verify"
    OTHER = "other"


class ObservationKind(str, Enum):
    """Indicator kinds Sherlock stores.

    String values are the goal ids Loki may put in `goals_completed` and
    `goals_remaining`. Add a member when an indicator becomes first-class.
    Until then, put unmatched identifiers on `other`. Regenerate TypeScript
    after changing them.
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
    PRETEXT_CATEGORY = "pretext_category"
    CASE_OR_REFERENCE_IDS = "case_or_reference_ids"
    THREAT_OR_CONSEQUENCE_LANGUAGE = "threat_or_consequence_language"
    REMOTE_ACCESS_TOOLS = "remote_access_tools"
    SPOOFED_AUTHORITY_CLAIMS = "spoofed_authority_claims"
    FOLLOW_UP_PROMISES = "follow_up_promises"
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
    payment_method: PaymentMethod | None = None
    pretext_category: PretextCategory | None = None

    @model_validator(mode="after")
    def span_and_facets(self) -> "Observation":
        if self.end_timestamp < self.start_timestamp:
            raise ValueError("end_timestamp must be greater than or equal to start_timestamp")
        if self.char_end < self.char_start:
            raise ValueError("char_end must be greater than or equal to char_start")
        self._check_facet(
            self.kind is ObservationKind.PAYMENT_METHODS,
            self.payment_method,
            "payment_method",
        )
        self._check_facet(
            self.kind is ObservationKind.PRETEXT_CATEGORY,
            self.pretext_category,
            "pretext_category",
        )
        return self

    def _check_facet(self, required: bool, facet: Enum | None, field_name: str) -> None:
        if required and facet is None:
            raise ValueError(f"{self.kind.value} observations require {field_name}")
        if not required and facet is not None:
            raise ValueError(f"{field_name} does not belong on kind {self.kind.value}")
        if facet is not None and self.normalized_value != facet.value:
            raise ValueError(f"normalized_value must equal {field_name}")
