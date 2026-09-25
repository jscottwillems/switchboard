# WATSON deterministic scorer evaluation

Synthetic labeled calls scored without embeddings or clustering.
Pairwise labels are ground-truth campaign equality. A predicted positive
means the two calls would be treated as the same campaign.

- Calls: 15
- Ground-truth campaigns: 8
- Same-campaign pairs: 11
- Different-campaign pairs: 94
- Minimum same-campaign score: 0.7872
- Maximum different-campaign score: 0.0261
- Gap: 0.7611

## Operating point

- `associate_threshold`: 0.50
- Evidence guard: anchor group >= 0.34, or script group >= 0.85
- Missing features contribute 0. Weights are not renormalized.
- Caller id is not a feature. Timing, duration, and simultaneous calls
  come from the call store and do not add into association_score.

Group weights:

| group | weight |
| --- | --- |
| anchor | 0.60 |
| script | 0.40 |
| structure | 0.00 |

Leaf weights inside each group:

### anchor

| feature | weight |
| --- | --- |
| phone_e164 | 0.28 |
| case_id | 0.16 |
| domain_registrable | 0.22 |
| email_domain_registrable | 0.16 |
| claimed_company_normalized | 0.18 |

### script

| feature | weight |
| --- | --- |
| opening_script_text | 0.32 |
| opening_script_fingerprint | 0.22 |
| script_phrase_normalized | 0.20 |
| pretext_category_canonical | 0.12 |
| transfer_destination_claimed | 0.10 |
| script_language | 0.04 |

### structure

| feature | weight |
| --- | --- |
| timing | 0.50 |
| duration | 0.20 |
| ivr_prompts | 0.30 |


Association score = 0.60 * anchor + 0.40 * script + 0.00 * structure.
Structure weight is 0. That group is retrieval and a tie-break only.
Opening script score is the maximum of token Jaccard and a near-copy
edit-distance bucket (1.00 at ratio >= 0.90, 0.85 at ratio >= 0.80, otherwise 0). Looser edit distance does not score.
Reasons cite Observation and Inference field names and values.

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
| irs-2 | gt-irs | associate | camp-0001 | 0.9840 | irs-1 |
| irs-3 | gt-irs | associate | camp-0001 | 0.9840 | irs-2 |
| irs-4 | gt-irs | associate | camp-0001 | 0.7872 | irs-1 |
| tech-1 | gt-tech | new_campaign | camp-0002 | 0.0021 | irs-1 |
| tech-2 | gt-tech | associate | camp-0002 | 0.9840 | tech-1 |
| tech-3 | gt-tech | associate | camp-0002 | 0.9840 | tech-2 |
| bank-1 | gt-bank | new_campaign | camp-0003 | 0.0261 | irs-1 |
| bank-2 | gt-bank | associate | camp-0003 | 0.9840 | bank-1 |
| solar-1 | gt-solar | new_campaign | camp-0004 | 0.0040 | irs-3 |
| insurance-1 | gt-insurance | new_campaign | camp-0005 | 0.0124 | solar-1 |
| warranty-1 | gt-warranty | new_campaign | camp-0006 | 0.0102 | insurance-1 |
| warranty-2 | gt-warranty | associate | camp-0006 | 0.9552 | warranty-1 |
| gift-1 | gt-gift | new_campaign | camp-0007 | 0.0064 | tech-3 |
| survey-1 | gt-survey | new_campaign | camp-0008 | 0.0041 | bank-2 |

## Scenario scores

- clearly_related_irs: 0.9840
- changing_identifiers_irs: 0.7872
- repeat_caller_different_campaign: 0.0021
- partial_irs_bank: 0.0261
- partial_solar_insurance: 0.0124
- unrelated_gift_survey: 0.0020
- clearly_related_warranty: 0.9552

Partial-overlap pairs are 0.0261 (IRS versus bank) and 0.0124 (solar versus insurance). Both stay under the 0.50 association threshold. Same-campaign pairs are at or above 0.7872.

## Example association

`irs-2` decision `associate` campaign `camp-0001` score 0.9840.

Reasons:

- Associated with campaign camp-0001 because association_score 0.98 >= threshold 0.50 (closest call irs-1).
- Tiers: anchors 1.00 (weight 0.60), script 0.96 (weight 0.40). structure 1.00 is retrieval and tie-break only (association weight 0.00).
- phone_e164 score 1.00: phone_e164 +18005550101 source=callback,spoken.
- case_id score 1.00: observation other irf4421; identifier_kind=case_id.
- domain_registrable score 1.00: domain_registrable irs-refund-help.com.
- email_domain_registrable score 1.00: local refunds domain irs-refund-help.com; email_domain_registrable irs-refund-help.com.
- claimed_company_normalized score 1.00: claimed_company_normalized and calling_from internal revenue service.
- opening_script_text score 1.00: opening_script_text token Jaccard 0.94; edit-distance bucket 1.00; opening_turns 2 and 2.
- opening_script_fingerprint score 1.00: opening_script_fingerprint fp-irs-refund-v1.
- script_phrase_normalized score 1.00: script_phrase_normalized 'federal refund is on hold', 'filing discrepancy', 'refund verification department'.
- pretext_category_canonical score 1.00: pretext_category_canonical government_refund.
- transfer_destination_claimed score 1.00: transfer_destination_claimed refund verification department.
- script_language score 0.00: script_language en is shared and is not campaign evidence.
- timing score 1.00: call started_at/ended_at intervals overlap (simultaneous); call store, not an Observation.
- duration score 1.00: call duration 210s versus 210s (call store started_at/ended_at, not an Observation).
- ivr_prompts score 1.00: ivr_prompts greeting > ssn_prompt > refund_agent.

Feature scores:

| feature | score |
| --- | --- |
| phone_e164 | 1.0000 |
| case_id | 1.0000 |
| domain_registrable | 1.0000 |
| email_domain_registrable | 1.0000 |
| claimed_company_normalized | 1.0000 |
| opening_script_text | 1.0000 |
| opening_script_fingerprint | 1.0000 |
| script_phrase_normalized | 1.0000 |
| pretext_category_canonical | 1.0000 |
| transfer_destination_claimed | 1.0000 |
| script_language | 0.0000 |
| timing | 1.0000 |
| duration | 1.0000 |
| ivr_prompts | 1.0000 |

## Example rejection

`bank-1` decision `new_campaign` campaign `camp-0003` score 0.0261.

Reasons:

- Opened a new campaign camp-0003 for call bank-1 because closest campaign camp-0001 (call irs-1) scored 0.03, below threshold 0.50.
- Tiers: anchors 0.00 (weight 0.60), script 0.07 (weight 0.40). structure 0.30 is retrieval and tie-break only (association weight 0.00).
- opening_script_text score 0.20: opening_script_text token Jaccard 0.20; edit-distance bucket 0.00; opening_turns 2 and 2.
- script_language score 0.00: script_language en is shared and is not campaign evidence.
- duration score 1.00: call duration 210s versus 210s (call store started_at/ended_at, not an Observation).

## Later comparison arm

Embeddings and clustering are not part of this scorer. A later slice
can measure them against this same labeled set and compare false
merges, missed merges, and whether each positive decision still has
a human-readable reason. This report is the baseline.
