# Sherlock intelligence

Sherlock turns a call transcript into structured intelligence. This milestone is a vertical slice: canonical schemas, a deterministic extractor, and a place to plug in a model later. It does not implement Bell, Echo, or Loki, and it does not define a shared call-session API.

The package lives at `packages/intelligence` because the repository had no layout yet. Pydantic models under `src/switchboard_intelligence/schemas` are the source of truth.

## Observation, inference, attribution

These are different records. A JSON object says which one it is with `record_type`.

**Observation** is a verbatim span of the transcript. It records what was said, not what it means. Every observation includes:

| Field | Meaning |
| --- | --- |
| `value` | Exact substring `segment.text[char_start:char_end]` |
| `source` | Rule or model that produced it, such as `deterministic.rules/v1#phone` |
| `transcript_segment_id` | Segment the span came from |
| `start_timestamp` | Call-relative seconds where the span starts |
| `end_timestamp` | Call-relative seconds where the span ends |
| `confidence` | Explicit number in `[0, 1]`, chosen by the rule, not estimated at runtime |

`normalized_value` is the canonical form used for identity (E.164-style phones, lowercased hosts, numeric amounts). Timestamps are interpolated across the segment from the character span and clamped to the segment bounds. Reprocessing the same transcript yields the same ids.

`ObservationKind` is a closed string enum. Those strings are also the goal ids Loki may put in `goals_completed` and `goals_remaining`. Add a member when an indicator becomes first-class. Until then, use `other`. Current members:

`claimed_company`, `claimed_agent`, `claimed_department`, `callback_numbers`, `spoken_numbers`, `domains`, `urls`, `email_addresses`, `loan_amounts`, `rates`, `fees`, `requested_information`, `payment_methods`, `script_phrases`, `urgency_language`, `transfer_events`, `pretext_category`, `case_or_reference_ids`, `threat_or_consequence_language`, `remote_access_tools`, `spoofed_authority_claims`, `follow_up_promises`, `opening_script_text`, `ivr_prompts`, `ivr_menu_path`, `transfer_destination_claimed`, `spoken_cli_claim`, `script_language`, `other`.

Two kinds carry an extra enum. It is unset on every other kind.

- `pretext_category` (kind) uses `pretext_category`: `tax`, `bank`, `warranty`, `debt`, `prize`, `tech_support`, `government`, `utility`, `other`. `value` is the free-text purpose span. `normalized_value` repeats the enum.
- `payment_methods` uses `payment_method`: `gift_card`, `wire`, `crypto`, `remote_access`, `bank_verify`, `other`. `value` is the spoken phrase. `normalized_value` repeats the enum.
- `script_language` uses `locale`: `en`, `es`, or `other`. `value` is the evidence span. `normalized_value` repeats the locale.
- `opening_script_text` uses `opening_turn_index` 0, 1, or 2. `value` is the full text of that caller turn.

`threat_or_consequence_language` is arrest, account freeze, or lawsuit language. `urgency_language` is time pressure only. `case_or_reference_ids` are ticket, case, claim, confirmation, account, and social-security-last-four numbers. Badge numbers stay on `other`. `spoofed_authority_claims` is the spoken "I am calling from…" or "I'm with…" clause, separate from the extracted company name and from `spoken_cli_claim` (a number they say will appear on caller ID). `follow_up_promises` is a promise to call back, send a link, or follow up, separate from a live `transfer_events` handoff, from `transfer_destination_claimed` (the desk, organization, or number named at that handoff), and from `remote_access_tools` (AnyDesk, TeamViewer, and similar). `ivr_prompts` are system-speaker "press N for …" lines. `ivr_menu_path` is the whole system segment when it contains two or more of those prompts.

These are not observations: timing windows, simultaneous calls, duration, dialing cadence, true carrier CLI/ANI, and carrier spoof flags. Watson reads those from the call session.

**Inference** is a proposition supported by one or more observations. It has no transcript span. Rule inferences in this slice:

| Inference kind | Built from |
| --- | --- |
| `impersonated_organization` | `claimed_company` |
| `payment_rail` | `payment_methods` |
| `data_target` | `requested_information` |
| `pressure_tactic` | `urgency_language` |
| `threatened_consequence` | `threat_or_consequence_language` |
| `offer_terms` | `fees`, `loan_amounts`, `rates` |
| `callback_channel` | `callback_numbers` |
| `claimed_company_normalized` | `claimed_company`, lowercased, legal suffixes removed |
| `phone_e164` | `callback_numbers`, `spoken_numbers`, and `spoken_cli_claim`, tagged `callback`, `spoken`, or `spoken_cli` |
| `domain_registrable` | `domains`, reduced to eTLD+1 |
| `email_local_domain` | `email_addresses`, split into local part and domain |
| `email_domain_registrable` | the email host, reduced to eTLD+1 |
| `script_phrase_normalized` | `script_phrases`, lowercased with punctuation removed; `original_value` keeps the span |
| `opening_script_fingerprint` | `opening_script_text` turns in order, as `fingerprint_tokens` |
| `pretext_category_canonical` | `pretext_category`, the closed enum |
| `identifier_kind` | `case_or_reference_ids` and `other`, labeled ticket, case, claim, confirmation, reference, badge, ssn_last4, or account |

Each derived inference has its own confidence. A guessed campaign link is not an inference.

**Attribution** in Sherlock stays empty in v1. Watson owns campaign linking and emits `CampaignAssociation`: `call_id`, `campaign_id`, `association_score`, `reasons` (`AssociationReason.field` plus `value`), and `feature_scores`. Reasons cite Sherlock field names and values. `feature_scores` is a sparse map, not a dense embedding. Sherlock does not compute association scores. The older `Attribution` record remains in the schema so it is not confused with an observation or an inference, and `NoCampaignCorpusAttributor` still returns an empty list.

Input transcripts use a local adapter (`Transcript`, `TranscriptSegment`) defined for Sherlock. Speakers are `scammer`, `target`, `system`, or `unknown`. That adapter is not a Switchboard-wide session contract.

## Who owns what

Sherlock owns typed Observation and Inference records. Each observation is grounded in a transcript span and an explicit confidence. That grounding is Sherlock-only. Watson owns `CampaignAssociation` in v1.

Loki does not emit parallel typed observations and does not attach an extraction confidence. The only soft handoff is optional and unverified:

```json
"elicited_hints": [
  {"goal": "callback_numbers", "surface_text": "call this number", "turn_index": 3}
]
```

`goal` must be an `ObservationKind` value, the same string Loki uses in `goals_completed` and `goals_remaining`. `surface_text` is whatever was heard. `turn_index` is Loki's turn counter. Hints are echoed on the bundle and are not promoted into observations. Sherlock still has to find a span before anything counts as intelligence.

## Extraction

`extract_intelligence` does three steps:

1. `DeterministicExtractor` scans each segment with regexes and lexicons.
2. Optionally, a `ModelExtractor` adds further observations. The default call does not invoke one. `NullModelExtractor` is the stub and returns nothing.
3. Rule inferences are derived from the observations. Attribution runs only through the attributor, which defaults to the empty corpus stub.

Model output still has to be an `Observation`: a verbatim span, a source string, and an explicit confidence. Paraphrases belong on `Inference`.

The model hook is `ModelExtractor.extract(transcript, deterministic)`. Implement that protocol when rules are not enough. See `MODEL_GAPS` in `extraction/coverage.py`:

- Phone numbers spoken as words
- Dollar amounts written as words
- Urgency or script lines outside the lexicon
- Organizations outside the lexicon
- Hosts spoken as "dot com"
- Obfuscated or scheme-less URLs

### Deterministic coverage

High precision is the goal. Dollar amounts are kept only when a fee cue or a loan cue is nearer. Percents are kept only when the same segment says interest, APR, or rate. Callback numbers require a callback cue in the window before the phone; other NANP numbers are `spoken_numbers`.

| Kind | What the rules accept |
| --- | --- |
| `claimed_company` | Organization lexicon within 80 characters after a claim cue |
| `claimed_agent` | Name after "my name is", or after Agent, Officer, or Detective |
| `claimed_department` | Department lexicon |
| `callback_numbers` | NANP phone with a callback cue |
| `spoken_numbers` | NANP phone without a callback cue or a spoken caller-ID cue |
| `spoken_cli_claim` | NANP phone after "caller ID will show" or "shows up as" |
| `domains` | URL host, email host, or a bare host with a known TLD |
| `urls` | `http` and `https` URLs |
| `email_addresses` | Standard email addresses |
| `loan_amounts` | `$` amount whose nearest cue is a loan word |
| `rates` | Percent in a segment that also says interest, APR, or rate |
| `fees` | `$` amount whose nearest cue is a fee word |
| `requested_information` | Target phrase plus an ask cue in the same segment |
| `payment_methods` | Payment phrase, plus `payment_method` enum |
| `script_phrases` | Canned pitch lexicon |
| `urgency_language` | Time-pressure lexicon |
| `transfer_events` | Live transfer lexicon |
| `pretext_category` | Known purpose phrase after "the purpose of this call is" |
| `case_or_reference_ids` | Case, claim, reference, ticket, or confirmation numbers |
| `threat_or_consequence_language` | Arrest, freeze, lawsuit, or failure-to-comply lexicon |
| `remote_access_tools` | Named tools such as AnyDesk or TeamViewer |
| `spoofed_authority_claims` | "I am calling from…", "I am with…", or "I'm with…" |
| `follow_up_promises` | Call-back, send-a-link, or follow-up promises |
| `opening_script_text` | Full text of the first three scammer turns |
| `ivr_prompts` | System-speaker "press N for …" prompts |
| `ivr_menu_path` | Full system segment when it has two or more IVR prompts |
| `transfer_destination_claimed` | Organization, department, or phone in a transfer segment |
| `script_language` | Locale from an explicit cue, or `en` when an English function word is present |
| `other` | Badge numbers that are not case or reference ids |

Known TLDs for bare domains: `com`, `net`, `org`, `gov`, `edu`, `info`, `biz`, `us`.

The machine-readable copy of this table is `DETERMINISTIC_COVERAGE`.

### Fixture bar

`fixtures/synthetic_transcripts.jsonl` holds 50 synthetic scam calls. Gold labels are the substrings the fixture builder planted, not a dump of extractor output. Pytest requires precision 1.0 and recall 1.0 on that gold set. Decoy lines (spoken digits, word amounts, paraphrased pressure, "dot com") must produce no observations. That is expected coverage for this milestone: complete on the planted obvious forms, silent on the model gaps.

Regenerate the file with:

```bash
python packages/intelligence/scripts/build_fixtures.py
```

## TypeScript

`packages/intelligence/typescript/intelligence.ts` is generated from the Pydantic models. Do not edit it by hand.

```bash
python -m switchboard_intelligence.codegen.typescript
```

`tests/test_typescript_sync.py` fails if the checked-in file drifts.

## HTTP

`POST /v1/intelligence/extract` accepts the local transcript adapter and returns an `IntelligenceBundle`. `GET /health` is a liveness check. Start the app with `uvicorn switchboard_intelligence.api:app`.
