# WATSON adapter for IntelligenceFinding

The live correlation input is `IntelligenceFinding` from `packages/schemas` (import `switchboard_schemas.interpretations.IntelligenceFinding`). This slice vendors that package from SB-009 (`cursor/sb-009-e164-finding-1574` at `cfa727a`), which landed on the Atlas skeleton as pull request 13. WATSON does not define a parallel observation or inference model.

PR #4's Observation, Inference, and Attribution models are superseded. They are not the live path.

## Import

```python
from switchboard_schemas.enums import FindingKind, FindingStatus
from switchboard_schemas.interpretations import IntelligenceFinding
```

`FindingKind` today:

| kind | emitted today | how WATSON scores it |
| --- | --- | --- |
| `callback_number` | yes, SB-009, literal E.164 only | primary tier A anchor. A shared value alone can associate |
| `pretext` | no | tier B. Fixture-only until ATLAS expands `FindingKind` emission |
| `organization_name` | no | tier A. Fixture-only until ATLAS expands emission |
| `payment_method` | no | tier A. Fixture-only until ATLAS expands emission |
| `url` | no | tier A. Fixture-only until ATLAS expands emission |
| `person_name` | no | tier B. Fixture-only until ATLAS expands emission |
| `other` | no | tier A, used for case and reference ids. Fixture-only until ATLAS expands emission |

SB-009 (`E164FindingExtractor`) proposes one `callback_number` when a transcript segment contains a literal E.164 token such as `+18005550101`. `value` and `raw_quote` are that substring. `confidence` is `1.0` because the rule ran. `extractor` is `e164`, `extractor_version` is `0.1.0`. `status` is `proposed`. Formatted numbers such as `(800) 555-0199` are not findings. Richer Loki and Watson kinds need an ATLAS `FindingKind` change before Sherlock emits them. No new kinds were added here.

## Provider

```python
class FindingProvider(Protocol):
    def findings_for(self, call: CompletedCall) -> list[IntelligenceFinding]: ...
```

`FixtureFindingProvider` (`watson/sherlock/mock.py`) returns findings pre-keyed by call id and an empty list for unknown ids. That is what the synthetic dataset uses. Each finding cites `transcript_segment_ids`. WATSON ignores `rejected` findings and anything below confidence 0.50.

## What stays on the call record

CLI/ANI (`caller_id`), `started_at` / `ended_at` (duration, timing, simultaneous calls), and the transcript used for retrieval overlap are not findings. Transcript overlap can raise a score slightly and cannot associate a pair by itself. Reasons for a finding match cite the kind and the value, for example `callback_number +18005550101`.

Campaign ids stay on `CampaignAssociation`. Sherlock does not assign them.
