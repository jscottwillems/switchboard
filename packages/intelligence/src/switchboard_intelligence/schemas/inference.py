"""Inferences: judgments supported by observations, not transcript spans."""

import re
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from switchboard_intelligence.schemas.common import SCHEMA_VERSION, Confidence

_E164 = re.compile(r"^\+\d{8,15}$")


class InferenceKind(str, Enum):
    IMPERSONATED_ORGANIZATION = "impersonated_organization"
    PAYMENT_RAIL = "payment_rail"
    DATA_TARGET = "data_target"
    PRESSURE_TACTIC = "pressure_tactic"
    OFFER_TERMS = "offer_terms"
    CALLBACK_CHANNEL = "callback_channel"
    THREATENED_CONSEQUENCE = "threatened_consequence"
    CLAIMED_COMPANY_NORMALIZED = "claimed_company_normalized"
    PHONE_E164 = "phone_e164"
    DOMAIN_REGISTRABLE = "domain_registrable"
    EMAIL_LOCAL_DOMAIN = "email_local_domain"
    EMAIL_DOMAIN_REGISTRABLE = "email_domain_registrable"
    SCRIPT_PHRASE_NORMALIZED = "script_phrase_normalized"
    OPENING_SCRIPT_FINGERPRINT = "opening_script_fingerprint"
    PRETEXT_CATEGORY_CANONICAL = "pretext_category_canonical"
    IDENTIFIER_KIND = "identifier_kind"
    OTHER = "other"


class PhoneSourceTag(str, Enum):
    """Where a `phone_e164` inference heard the number."""

    CALLBACK = "callback"
    SPOKEN = "spoken"
    SPOKEN_CLI = "spoken_cli"


class IdentifierKind(str, Enum):
    """Label on a case, reference, or other identifier."""

    TICKET = "ticket"
    CASE = "case"
    CLAIM = "claim"
    CONFIRMATION = "confirmation"
    REFERENCE = "reference"
    BADGE = "badge"
    SSN_LAST4 = "ssn_last4"
    ACCOUNT = "account"


class InferenceMethod(str, Enum):
    RULE = "rule"
    MODEL = "model"
    ANALYST = "analyst"


class Inference(BaseModel):
    """A proposition derived from one or more observations.

    Inferences have no transcript span. The evidence is
    `supporting_observation_ids`.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["sherlock.intelligence.v1"] = SCHEMA_VERSION
    record_type: Literal["inference"] = "inference"
    inference_id: str = Field(min_length=1)
    call_id: str = Field(min_length=1)
    kind: InferenceKind
    proposition: str = Field(min_length=1)
    supporting_observation_ids: list[str] = Field(min_length=1)
    confidence: Confidence
    method: InferenceMethod
    rationale: str = Field(min_length=1)
    normalized_value: str | None = None
    original_value: str | None = None
    source_tag: PhoneSourceTag | None = None
    identifier_kind: IdentifierKind | None = None
    email_local: str | None = None
    email_domain: str | None = None
    fingerprint_tokens: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def derived_fields(self) -> "Inference":
        correlation = self.kind in _CORRELATION_KINDS
        if correlation and not self.normalized_value:
            raise ValueError(f"{self.kind.value} requires normalized_value")
        if not correlation and self.normalized_value is not None:
            raise ValueError(f"normalized_value does not belong on kind {self.kind.value}")
        if self.kind is InferenceKind.PHONE_E164:
            if self.source_tag is None:
                raise ValueError("phone_e164 requires source_tag")
            if self.normalized_value is None or _E164.fullmatch(self.normalized_value) is None:
                raise ValueError("phone_e164 normalized_value must be E.164")
        elif self.source_tag is not None:
            raise ValueError(f"source_tag does not belong on kind {self.kind.value}")
        if self.kind is InferenceKind.OPENING_SCRIPT_FINGERPRINT:
            if not self.fingerprint_tokens:
                raise ValueError("opening_script_fingerprint requires fingerprint_tokens")
        elif self.fingerprint_tokens:
            raise ValueError(f"fingerprint_tokens does not belong on kind {self.kind.value}")
        if self.kind is InferenceKind.IDENTIFIER_KIND:
            if self.identifier_kind is None:
                raise ValueError("identifier_kind inferences require identifier_kind")
        elif self.identifier_kind is not None:
            raise ValueError(f"identifier_kind does not belong on kind {self.kind.value}")
        if self.kind is InferenceKind.EMAIL_LOCAL_DOMAIN:
            if not self.email_local or not self.email_domain:
                raise ValueError("email_local_domain requires email_local and email_domain")
        elif self.email_local is not None or self.email_domain is not None:
            raise ValueError(f"email split does not belong on kind {self.kind.value}")
        if self.kind in _ORIGINAL_REQUIRED and not self.original_value:
            raise ValueError(f"{self.kind.value} requires original_value")
        if self.original_value is not None and self.kind not in _ORIGINAL_ALLOWED:
            raise ValueError(f"original_value does not belong on kind {self.kind.value}")
        return self


_CORRELATION_KINDS = {
    InferenceKind.CLAIMED_COMPANY_NORMALIZED,
    InferenceKind.PHONE_E164,
    InferenceKind.DOMAIN_REGISTRABLE,
    InferenceKind.EMAIL_LOCAL_DOMAIN,
    InferenceKind.EMAIL_DOMAIN_REGISTRABLE,
    InferenceKind.SCRIPT_PHRASE_NORMALIZED,
    InferenceKind.OPENING_SCRIPT_FINGERPRINT,
    InferenceKind.PRETEXT_CATEGORY_CANONICAL,
    InferenceKind.IDENTIFIER_KIND,
}

_ORIGINAL_REQUIRED = {
    InferenceKind.CLAIMED_COMPANY_NORMALIZED,
    InferenceKind.SCRIPT_PHRASE_NORMALIZED,
    InferenceKind.PRETEXT_CATEGORY_CANONICAL,
    InferenceKind.IDENTIFIER_KIND,
}

_ORIGINAL_ALLOWED = _ORIGINAL_REQUIRED | {
    InferenceKind.PHONE_E164,
    InferenceKind.EMAIL_LOCAL_DOMAIN,
}
