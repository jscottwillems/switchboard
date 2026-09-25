/**
 * Generated from the Sherlock Pydantic models. Do not edit by hand.
 *
 * Source of truth: packages/intelligence/src/switchboard_intelligence/schemas
 * Regenerate: python -m switchboard_intelligence.codegen.typescript
 */

export const SCHEMA_VERSION = "sherlock.intelligence.v1" as const;

export const SpeakerRole = [
  "scammer",
  "target",
  "system",
  "unknown",
] as const;

export type SpeakerRole = (typeof SpeakerRole)[number];

export const PretextCategory = [
  "tax",
  "bank",
  "warranty",
  "debt",
  "prize",
  "tech_support",
  "government",
  "utility",
  "other",
] as const;

export type PretextCategory = (typeof PretextCategory)[number];

export const PaymentMethod = [
  "gift_card",
  "wire",
  "crypto",
  "remote_access",
  "bank_verify",
  "other",
] as const;

export type PaymentMethod = (typeof PaymentMethod)[number];

export const ScriptLocale = [
  "en",
  "es",
  "other",
] as const;

export type ScriptLocale = (typeof ScriptLocale)[number];

export const ObservationKind = [
  "claimed_company",
  "claimed_agent",
  "claimed_department",
  "callback_numbers",
  "spoken_numbers",
  "domains",
  "urls",
  "email_addresses",
  "loan_amounts",
  "rates",
  "fees",
  "requested_information",
  "payment_methods",
  "script_phrases",
  "urgency_language",
  "transfer_events",
  "pretext_category",
  "case_or_reference_ids",
  "threat_or_consequence_language",
  "remote_access_tools",
  "spoofed_authority_claims",
  "follow_up_promises",
  "opening_script_text",
  "ivr_prompts",
  "ivr_menu_path",
  "transfer_destination_claimed",
  "spoken_cli_claim",
  "script_language",
  "other",
] as const;

export type ObservationKind = (typeof ObservationKind)[number];

export const InferenceKind = [
  "impersonated_organization",
  "payment_rail",
  "data_target",
  "pressure_tactic",
  "offer_terms",
  "callback_channel",
  "threatened_consequence",
  "claimed_company_normalized",
  "phone_e164",
  "domain_registrable",
  "email_local_domain",
  "email_domain_registrable",
  "script_phrase_normalized",
  "opening_script_fingerprint",
  "pretext_category_canonical",
  "identifier_kind",
  "other",
] as const;

export type InferenceKind = (typeof InferenceKind)[number];

export const PhoneSourceTag = [
  "callback",
  "spoken",
  "spoken_cli",
] as const;

export type PhoneSourceTag = (typeof PhoneSourceTag)[number];

export const IdentifierKind = [
  "ticket",
  "case",
  "claim",
  "confirmation",
  "reference",
  "badge",
  "ssn_last4",
  "account",
] as const;

export type IdentifierKind = (typeof IdentifierKind)[number];

export const InferenceMethod = [
  "rule",
  "model",
  "analyst",
] as const;

export type InferenceMethod = (typeof InferenceMethod)[number];

export const AttributionSubject = [
  "campaign",
  "actor",
  "infrastructure",
  "script_family",
  "unknown",
] as const;

export type AttributionSubject = (typeof AttributionSubject)[number];

export const AttributionStatus = [
  "hypothesized",
  "supported",
  "confirmed",
] as const;

export type AttributionStatus = (typeof AttributionStatus)[number];

export interface ElicitedHint {
  goal: ObservationKind;
  surface_text: string;
  turn_index: number;
}

export interface TranscriptSegment {
  segment_id: string;
  speaker: SpeakerRole;
  text: string;
  start_timestamp: number;
  end_timestamp: number;
}

export interface Transcript {
  call_id: string;
  segments: TranscriptSegment[];
  elicited_hints: ElicitedHint[];
}

export interface Observation {
  schema_version: "sherlock.intelligence.v1";
  record_type: "observation";
  observation_id: string;
  call_id: string;
  kind: ObservationKind;
  value: string;
  normalized_value: string;
  source: string;
  transcript_segment_id: string;
  start_timestamp: number;
  end_timestamp: number;
  char_start: number;
  char_end: number;
  confidence: number;
  payment_method: PaymentMethod | null;
  pretext_category: PretextCategory | null;
  locale: ScriptLocale | null;
  opening_turn_index: number | null;
}

export interface Inference {
  schema_version: "sherlock.intelligence.v1";
  record_type: "inference";
  inference_id: string;
  call_id: string;
  kind: InferenceKind;
  proposition: string;
  supporting_observation_ids: string[];
  confidence: number;
  method: InferenceMethod;
  rationale: string;
  normalized_value: string | null;
  original_value: string | null;
  source_tag: PhoneSourceTag | null;
  identifier_kind: IdentifierKind | null;
  email_local: string | null;
  email_domain: string | null;
  fingerprint_tokens: string[];
}

export interface Attribution {
  schema_version: "sherlock.intelligence.v1";
  record_type: "attribution";
  attribution_id: string;
  call_id: string;
  subject_type: AttributionSubject;
  subject_key: string;
  subject_label: string;
  supporting_observation_ids: string[];
  supporting_inference_ids: string[];
  confidence: number;
  status: AttributionStatus;
  rationale: string;
}

export interface AssociationReason {
  field: string;
  value: string;
}

export interface CampaignAssociation {
  record_type: "campaign_association";
  call_id: string;
  campaign_id: string;
  association_score: number;
  reasons: AssociationReason[];
  feature_scores: Record<string, number>;
}

export interface IntelligenceBundle {
  schema_version: "sherlock.intelligence.v1";
  call_id: string;
  observations: Observation[];
  inferences: Inference[];
  attributions: Attribution[];
  elicited_hints: ElicitedHint[];
}

export type IntelligenceRecord = Observation | Inference | Attribution;
