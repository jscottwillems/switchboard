# WATSON deterministic scorer evaluation

Synthetic labeled calls scored without embeddings or clustering.
Pairwise labels are ground-truth campaign equality. A predicted positive
means the two calls would be treated as the same campaign.

- Calls: 15
- Ground-truth campaigns: 8
- Same-campaign pairs: 11
- Different-campaign pairs: 94
- Minimum same-campaign score: 0.8927
- Maximum different-campaign score: 0.0340
- Gap: 0.8587

## Operating point

- `associate_threshold`: 0.50
- Evidence guard: anchor evidence >= 0.50
- Missing findings contribute 0. Evidence weights are not renormalized.
- A shared callback_number alone clears the threshold. Other kinds do not.
- Caller id is not a feature. Timing and duration come from the call
  store and do not add into association_score.

Evidence contributions (added when the leaf score is 1, then capped at 1):

| feature | contribution |
| --- | --- |
| callback_number | 0.72 |
| organization_name | 0.20 |
| url | 0.16 |
| payment_method | 0.10 |
| other | 0.14 |
| pretext | 0.18 |
| person_name | 0.06 |
| transcript_overlap | 0.12 |

Tier C mix (tie-break only):

### structure

| feature | weight |
| --- | --- |
| timing | 0.60 |
| duration | 0.40 |


Association score = min(1, sum of evidence contribution times leaf score).
Structure does not enter that sum. Reasons for finding matches cite
the finding kind and value. Transcript overlap is call-store text,
not an IntelligenceFinding.

## Pairwise scores at fixed thresholds

These rows use the score alone. The evidence guard is not applied.

| threshold | TP | FP | FN | TN | precision | recall |
| --- | --- | --- | --- | --- | --- | --- |
| 0.30 | 11 | 0 | 0 | 94 | 1.000 | 1.000 |
| 0.40 | 11 | 0 | 0 | 94 | 1.000 | 1.000 |
| 0.50 | 11 | 0 | 0 | 94 | 1.000 | 1.000 |
| 0.60 | 11 | 0 | 0 | 94 | 1.000 | 1.000 |
| 0.70 | 11 | 0 | 0 | 94 | 1.000 | 1.000 |

## Operating point (threshold and evidence guard)

| rule | TP | FP | FN | TN | precision | recall |
| --- | --- | --- | --- | --- | --- | --- |
| operating_point | 11 | 0 | 0 | 94 | 1.000 | 1.000 |

## Online pipeline clustering

Calls are ingested in time order. A pair is predicted positive when
both calls land in the same assigned campaign. This is the decision
the pipeline actually makes, including retrieval and transitivity.

| rule | TP | FP | FN | TN | precision | recall |
| --- | --- | --- | --- | --- | --- | --- |
| pipeline | 11 | 0 | 0 | 94 | 1.000 | 1.000 |

| call | ground truth | decision | campaign | score | closest call |
| --- | --- | --- | --- | --- | --- |
| irs-1 | gt-irs | new_campaign | camp-0001 | 0.0000 |  |
| irs-2 | gt-irs | associate | camp-0001 | 1.0000 | irs-1 |
| irs-3 | gt-irs | associate | camp-0001 | 1.0000 | irs-2 |
| irs-4 | gt-irs | associate | camp-0001 | 0.9600 | irs-1 |
| tech-1 | gt-tech | new_campaign | camp-0002 | 0.0146 | irs-1 |
| tech-2 | gt-tech | associate | camp-0002 | 1.0000 | tech-1 |
| tech-3 | gt-tech | associate | camp-0002 | 1.0000 | tech-2 |
| bank-1 | gt-bank | new_campaign | camp-0003 | 0.0340 | irs-1 |
| bank-2 | gt-bank | associate | camp-0003 | 1.0000 | bank-1 |
| solar-1 | gt-solar | new_campaign | camp-0004 | 0.0196 | bank-2 |
| insurance-1 | gt-insurance | new_campaign | camp-0005 | 0.0322 | solar-1 |
| warranty-1 | gt-warranty | new_campaign | camp-0006 | 0.0290 | bank-1 |
| warranty-2 | gt-warranty | associate | camp-0006 | 1.0000 | warranty-1 |
| gift-1 | gt-gift | new_campaign | camp-0007 | 0.0263 | insurance-1 |
| survey-1 | gt-survey | new_campaign | camp-0008 | 0.0204 | solar-1 |

## Scenario scores

- clearly_related_irs: 1.0000
- changing_identifiers_irs: 0.9600
- repeat_caller_different_campaign: 0.0146
- partial_irs_bank: 0.0340
- partial_solar_insurance: 0.0322
- unrelated_gift_survey: 0.0183
- clearly_related_warranty: 1.0000

Partial-overlap pairs are 0.0340 (IRS versus bank) and 0.0322 (solar versus insurance). Both stay under the 0.50 association threshold. Same-campaign pairs are at or above 0.8927.

## Example association

`irs-2` decision `associate` campaign `camp-0001` score 1.0000.

Reasons:

- Associated with campaign camp-0001 because association_score 1.00 >= threshold 0.50 (closest call irs-1).
- Tiers: anchors 1.00, script 0.18. structure 1.00 is retrieval and tie-break only.
- callback_number score 1.00: callback_number +18005550101.
- organization_name score 1.00: organization_name internal revenue service.
- url score 1.00: url irs-refund-help.com.
- payment_method score 1.00: payment_method direct deposit.
- other score 1.00: other irf4421.
- pretext score 1.00: pretext government_refund.
- transcript_overlap score 0.96: call-store transcript token Jaccard 0.96; not an IntelligenceFinding.
- timing score 1.00: call started_at/ended_at intervals overlap (simultaneous); call store, not an IntelligenceFinding.
- duration score 1.00: call duration 210s versus 210s (call store started_at/ended_at, not an IntelligenceFinding).

Feature scores:

| feature | score |
| --- | --- |
| callback_number | 1.0000 |
| organization_name | 1.0000 |
| url | 1.0000 |
| payment_method | 1.0000 |
| other | 1.0000 |
| pretext | 1.0000 |
| person_name | 0.0000 |
| transcript_overlap | 0.9592 |
| timing | 1.0000 |
| duration | 1.0000 |

## Example rejection

`bank-1` decision `new_campaign` campaign `camp-0003` score 0.0340.

Reasons:

- Opened a new campaign camp-0003 for call bank-1 because closest campaign camp-0001 (call irs-1) scored 0.03, below threshold 0.50.
- Tiers: anchors 0.00, script 0.00. structure 0.40 is retrieval and tie-break only.
- transcript_overlap score 0.28: call-store transcript token Jaccard 0.28; not an IntelligenceFinding.
- duration score 1.00: call duration 210s versus 210s (call store started_at/ended_at, not an IntelligenceFinding).

## Later comparison arm

Embeddings and clustering are not part of this scorer. A later slice
can measure them against this same labeled set and compare false
merges, missed merges, and whether each positive decision still has
a human-readable reason. This report is the baseline.
