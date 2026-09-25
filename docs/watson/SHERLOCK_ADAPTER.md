# WATSON adapter for the v1 correlation contract

SHERLOCK's correlation-facing models are not on `main`. The branch `cursor/sherlock-intelligence-slice-1574` exports span `Observation` records and a proposition-style `Inference` (`kind`, `proposition`, `supporting_observation_ids`, `confidence`, `method`, `rationale`). That inference does not yet carry the correlation fields below, and its attributor does not assign campaign ids.

WATSON keeps a thin adapter with those semantic fields. Do not import `switchboard_intelligence` until the correlation models land. When they do, replace this adapter with:

- `switchboard_intelligence.schemas.observation.Observation`
- `switchboard_intelligence.schemas.observation.ObservationKind`
- `switchboard_intelligence.schemas.inference` for `claimed_company_normalized`, `phone_e164` (`source` `callback` or `spoken`), `domain_registrable`, the email local/domain split, `email_domain_registrable`, `script_phrase_normalized`, `opening_script_fingerprint`, `pretext_category_canonical`, and `identifier_kind`

`CorrelationInference` in `watson/sherlock/models.py` is the local stand-in. It is not Sherlock's current `Inference` class. There is no embedding field. Campaign ids stay on `CampaignAssociation`, which WATSON owns.

## Provider

```python
class CallIntelligenceProvider(Protocol):
    def indicators_for(self, call: CompletedCall) -> CallIntelligence: ...
```

`call_id` on the returned `CallIntelligence` must match the completed call. `FixtureIntelligenceProvider` (`watson/sherlock/mock.py`) returns a prebuilt `CallIntelligence` and an empty observation list with `inference=None` for unknown ids.

## Observation

A transcript-grounded span. Field names match Sherlock's observation record: `schema_version` (`sherlock.intelligence.v1`), `record_type` (`observation`), `observation_id`, `call_id`, `kind`, `value`, `normalized_value`, `source`, `transcript_segment_id`, `start_timestamp`, `end_timestamp`, `char_start`, `char_end`, `confidence`.

`calling_from` is the spoken "calling from" observation. It is a separate kind from `claimed_company`. WATSON normalizes it by stripping a leading "calling from the " or "calling from ", and still cites `calling_from` in reasons.

| `kind` | How WATSON uses it |
| --- | --- |
| `claimed_company` | anchor `claimed_company_normalized` |
| `claimed_agent` | accepted, not scored |
| `claimed_department` | accepted, not scored |
| `callback_numbers` | `phone_e164` with `source=callback` |
| `spoken_numbers` | `phone_e164` with `source=spoken` |
| `domains` | `domain_registrable` |
| `urls` | `domain_registrable` |
| `email_addresses` | email local/domain split and `email_domain_registrable` |
| `loan_amounts` | accepted, not scored |
| `rates` | accepted, not scored |
| `fees` | accepted, not scored |
| `requested_information` | accepted, not scored |
| `payment_methods` | accepted, not scored |
| `script_phrases` | `script_phrase_normalized` |
| `urgency_language` | accepted, not scored |
| `transfer_events` | accepted, not scored |
| `other` | case, badge, or reference id, scored as `case_id` |
| `opening_turns` | supporting turns cited with `opening_script_text` |
| `opening_script_text` | tier B opening comparison |
| `ivr_prompts` | tier C path, steps separated by `>`, `/`, `,`, or `\|` |
| `transfer_destination_claimed` | tier B destination |
| `calling_from` | distinct from `claimed_company`; feeds the company anchor and is cited by name |
| `script_language` | tier B; shared `en` is recorded and scores 0 |

`confidence` is required. Values below 0.50 are ignored. The synthetic bank call includes an Internal Revenue Service `claimed_company` and an IRS `script_phrases` span at confidence 0.15 and 0.10. Those must not affect the score.

`ivr_prompts` in the fixture use `transcript_segment_id` `ivr` and a zero character span. The path is honeypot metadata attached as an observation. It is not a sentence in the scammer transcript. CLI/ANI, timing, duration, and simultaneous calls are not observations.

## Inference

`CorrelationInference` is one Sherlock-emitted judgment per call, with its own `confidence` (same 0.50 floor). Fields:

- `claimed_company_normalized`
- `phone_e164`: list of `{phone_e164, source}` where `source` is `callback` or `spoken`
- `domain_registrable`
- `email`: list of `{local, domain, email_domain_registrable}`
- `email_domain_registrable`: same registrable domains as `email`, in the same order
- `script_phrase_normalized`
- `opening_script_fingerprint`
- `pretext_category_canonical`
- `identifier_kind`: tags such as `phone`, `case_id`, `email`, `url`

No dense vectors. A low-confidence inference is dropped as a whole.

## What stays on the call record

WATSON reads these from `CompletedCall`, not from Sherlock:

- transcript, used when `opening_script_text` and `opening_turns` are absent, and for retrieval token overlap
- `started_at` / `ended_at` (duration, timing, simultaneous calls)
- `caller_id` (CLI/ANI), stored and unused

An `opening_script_text` observation at or above the confidence floor replaces the transcript-derived opening. Joined `opening_turns` are the next fallback.

## Alignment notes

- One observation per extracted value. Multiple phrases are multiple observations.
- Ground `value` in the transcript (`char_start` / `char_end`) except for `ivr_prompts` supplied by the honeypot.
- Prefer the full organization name over an abbreviation until WATSON has an alias table.
- The opening span should cover the start of the pitch (this dataset uses the first 70 words).
- Do not put generic lines such as "do not hang up" in `script_phrases`. Those belong in the transcript overlap.
- Keep the kind spelling `calling_from` for the spoken "calling from" observation.
