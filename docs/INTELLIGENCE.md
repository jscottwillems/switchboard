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

`ObservationKind` is a closed string enum. Add a member when an indicator becomes first-class. Until then, use `other`. Current members:

`claimed_company`, `claimed_agent`, `claimed_department`, `callback_numbers`, `spoken_numbers`, `domains`, `urls`, `email_addresses`, `loan_amounts`, `rates`, `fees`, `requested_information`, `payment_methods`, `script_phrases`, `urgency_language`, `transfer_events`, `other`.

**Inference** is a proposition supported by one or more observations. It has no transcript span. Rule inferences in this slice:

| Inference kind | Built from |
| --- | --- |
| `impersonated_organization` | `claimed_company` |
| `payment_rail` | `payment_methods` |
| `data_target` | `requested_information` |
| `pressure_tactic` | `urgency_language` |
| `offer_terms` | `fees`, `loan_amounts`, `rates` |
| `callback_channel` | `callback_numbers` |

Other observation kinds stay observations. A guessed campaign link is not an inference.

**Attribution** links observations or inferences to an external subject (`campaign`, `actor`, `infrastructure`, `script_family`, or `unknown`). The record exists so it cannot be confused with the other two. This milestone has no campaign corpus. `NoCampaignCorpusAttributor` returns an empty list. Pass a different `Attributor` when a corpus exists.

Input transcripts use a local adapter (`Transcript`, `TranscriptSegment`) defined for Sherlock. Speakers are `scammer`, `target`, `system`, or `unknown`. That adapter is not a Switchboard-wide session contract.

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
| `spoken_numbers` | NANP phone without a callback cue |
| `domains` | URL host, email host, or a bare host with a known TLD |
| `urls` | `http` and `https` URLs |
| `email_addresses` | Standard email addresses |
| `loan_amounts` | `$` amount whose nearest cue is a loan word |
| `rates` | Percent in a segment that also says interest, APR, or rate |
| `fees` | `$` amount whose nearest cue is a fee word |
| `requested_information` | Target phrase plus an ask cue in the same segment |
| `payment_methods` | Payment lexicon (gift card, wire, bitcoin, Zelle, and similar) |
| `script_phrases` | Canned pitch lexicon |
| `urgency_language` | Urgency lexicon |
| `transfer_events` | Transfer lexicon |
| `other` | Case, badge, reference, ticket, or confirmation numbers that contain a digit |

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
