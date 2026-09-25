# WATSON deterministic scorer evaluation

Synthetic labeled calls scored without embeddings or clustering.
Pairwise labels are ground-truth campaign equality. A predicted positive
means the two calls would be treated as the same campaign.

- Calls: 15
- Ground-truth campaigns: 8
- Same-campaign pairs: 11
- Different-campaign pairs: 94
- Minimum same-campaign score: 0.8791
- Maximum different-campaign score: 0.1204
- Gap: 0.7587

## Operating point

- `associate_threshold`: 0.50
- Evidence guard: script group >= 0.40, or identifier group >= 0.50 and script group >= 0.25
- Missing features contribute 0. Weights are not renormalized.
- Caller id is not a feature.

Group weights:

| group | weight |
| --- | --- |
| script | 0.70 |
| identifier | 0.25 |
| structure | 0.05 |

Leaf weights inside each group:

### script

| feature | weight |
| --- | --- |
| opening_script | 0.45 |
| transcript | 0.35 |
| repeated_phrases | 0.20 |

### identifier

| feature | weight |
| --- | --- |
| claimed_organization | 0.34 |
| callback_identifiers | 0.30 |
| domains | 0.20 |
| email_patterns | 0.16 |

### structure

| feature | weight |
| --- | --- |
| timing | 0.35 |
| duration | 0.20 |
| transfer_behavior | 0.20 |
| ivr_structure | 0.25 |


Association score = 0.70 * script + 0.25 * identifier + 0.05 * structure,
using the leaf weights above. Opening script score is the maximum of
token Jaccard and a near-copy edit-distance bucket (1.00 at ratio >= 0.90, 0.85 at ratio >= 0.80, otherwise 0). Looser edit distance does not score.

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
| irs-2 | gt-irs | associate | camp-0001 | 0.9906 | irs-1 |
| irs-3 | gt-irs | associate | camp-0001 | 0.9761 | irs-2 |
| irs-4 | gt-irs | associate | camp-0001 | 0.8985 | irs-1 |
| tech-1 | gt-tech | new_campaign | camp-0002 | 0.0000 |  |
| tech-2 | gt-tech | associate | camp-0002 | 0.9885 | tech-1 |
| tech-3 | gt-tech | associate | camp-0002 | 0.9712 | tech-1 |
| bank-1 | gt-bank | new_campaign | camp-0003 | 0.1204 | irs-1 |
| bank-2 | gt-bank | associate | camp-0003 | 0.9797 | bank-1 |
| solar-1 | gt-solar | new_campaign | camp-0004 | 0.0000 |  |
| insurance-1 | gt-insurance | new_campaign | camp-0005 | 0.0990 | solar-1 |
| warranty-1 | gt-warranty | new_campaign | camp-0006 | 0.0740 | insurance-1 |
| warranty-2 | gt-warranty | associate | camp-0006 | 0.9744 | warranty-1 |
| gift-1 | gt-gift | new_campaign | camp-0007 | 0.0000 |  |
| survey-1 | gt-survey | new_campaign | camp-0008 | 0.0000 |  |

## Scenario scores

- clearly_related_irs: 0.9906
- changing_identifiers_irs: 0.8985
- repeat_caller_different_campaign: 0.0115
- partial_irs_bank: 0.1204
- partial_solar_insurance: 0.0990
- unrelated_gift_survey: 0.0220
- clearly_related_warranty: 0.9744

Partial-overlap pairs are 0.1204 (IRS versus bank) and 0.0990 (solar versus insurance). Both stay under the 0.50 association threshold. Same-campaign pairs are at or above 0.8791.

## Example association

`irs-2` decision `associate` campaign `camp-0001` score 0.9906.

Reasons:

- Associated with campaign camp-0001 because association_score 0.99 >= threshold 0.50 (closest call irs-1).
- Weighted groups: script 0.99 (weight 0.70), identifier 1.00 (weight 0.25), structure 1.00 (weight 0.05).
- opening_script score 1.00: token Jaccard 0.94; edit-distance bucket 1.00.
- transcript score 0.96: token Jaccard overlap.
- repeated_phrases score 1.00: shared phrases 'federal refund is on hold', 'filing discrepancy', 'refund verification department'.
- claimed_organization score 1.00: shared organization internal revenue service.
- callback_identifiers score 1.00: shared callback identifier 8005550101.
- domains score 1.00: shared domain irs-refund-help.com.
- email_patterns score 1.00: shared email refunds@irs-refund-help.com.
- timing score 1.00: call intervals overlap.
- duration score 1.00: 210s versus 210s.
- transfer_behavior score 1.00: both calls were transferred.
- ivr_structure score 1.00: identical IVR path greeting > ssn_prompt > refund_agent.

Feature scores:

| feature | score |
| --- | --- |
| opening_script | 1.0000 |
| transcript | 0.9615 |
| repeated_phrases | 1.0000 |
| claimed_organization | 1.0000 |
| callback_identifiers | 1.0000 |
| domains | 1.0000 |
| email_patterns | 1.0000 |
| timing | 1.0000 |
| duration | 1.0000 |
| transfer_behavior | 1.0000 |
| ivr_structure | 1.0000 |

## Example rejection

`bank-1` decision `new_campaign` campaign `camp-0003` score 0.1204.

Reasons:

- Opened a new campaign camp-0003 for call bank-1 because closest campaign camp-0001 (call irs-1) scored 0.12, below threshold 0.50.
- Weighted groups: script 0.15 (weight 0.70), identifier 0.00 (weight 0.25), structure 0.28 (weight 0.05).
- opening_script score 0.20: token Jaccard 0.20; edit-distance bucket 0.00.
- duration score 1.00: 210s versus 210s.

## Later comparison arm

Embeddings and clustering are not part of this scorer. A later slice
can measure them against this same labeled set and compare false
merges, missed merges, and whether each positive decision still has
a human-readable reason. This report is the baseline.
