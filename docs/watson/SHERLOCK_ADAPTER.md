# WATSON adapter for call-intelligence indicators

SHERLOCK's observation schema was not on `main` when this slice was written. WATSON does not implement SHERLOCK. It defines the indicators it knows how to score, and tests use a fixture provider.

When SHERLOCK's schema lands, adapt it onto this interface. Leave the scorer unchanged.

## Provider

```python
class CallIntelligenceProvider(Protocol):
    def indicators_for(self, call: CompletedCall) -> CallIntelligence: ...
```

`call_id` on the returned `CallIntelligence` must match the completed call. `FixtureIntelligenceProvider` (`watson/sherlock/mock.py`) returns observations pre-keyed by call id and returns an empty list for unknown ids. That is the implementation tests and the synthetic dataset use.

## Observation

```python
class IntelligenceObservation(BaseModel):
    kind: ObservationKind
    value: str
    confidence: float  # 0..1
    evidence: str | None
```

| `kind` | `value` WATSON expects | Feature |
| --- | --- | --- |
| `claimed_organization` | organization name as spoken or canonicalized by SHERLOCK | `claimed_organization` |
| `callback_identifier` | phone number, any common punctuation | `callback_identifiers` |
| `domain` | host or URL | `domains` |
| `email_pattern` | email address | `email_patterns` |
| `repeated_phrase` | a distinctive phrase, not a generic greeting | `repeated_phrases` |
| `opening_script` | the pitch opening, not only "hello" | `opening_script` |
| `ivr_structure` | steps separated by `>`, `/`, `,`, or `\|` | `ivr_structure` |

`confidence` is required. Values below 0.50 are ignored. The synthetic bank call includes an Internal Revenue Service organization and an IRS phrase at confidence 0.15 and 0.10; those must not affect the score. `evidence` is retained for traceability and is not itself a feature.

## What stays on the call record

WATSON reads these from `CompletedCall`, not from SHERLOCK:

- transcript (token overlap, and the opening span when no `opening_script` observation is present)
- `started_at` / `ended_at` (duration and timing)
- `transferred`
- `ivr_path` when the honeypot already has a structured path

Precedence:

- An `opening_script` observation at or above the confidence floor replaces the transcript-derived opening.
- A non-empty `call.ivr_path` replaces an `ivr_structure` observation.

Caller id is intentionally unused. Rotating callback numbers are `callback_identifier` observations. A repeated caller who switches pretext is a different campaign unless script and indicators agree.

## Alignment notes for SHERLOCK

- One observation per extracted value. Multiple phrases or callbacks are multiple observations.
- Prefer the full organization name over an abbreviation until WATSON has an alias table.
- The opening span should cover the start of the pitch (this dataset uses the first 70 words). A shared hello by itself is not a campaign signature.
- Do not put generic lines such as "do not hang up" in `repeated_phrase`. Those belong in the transcript overlap, where they stay low-weighted.
- This contract is provisional. Field names here are what WATSON scores today.
