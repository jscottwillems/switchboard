# WATSON scoring

WATSON assigns each completed call to a campaign with a deterministic score in `[0, 1]`. Every decision carries human-readable reasons and the leaf feature scores those reasons cite. Reasons name Observation and Inference fields and the values that matched. Embeddings and clustering are not used. Sherlock does not assign campaign ids.

The measured gap on the synthetic set is in `docs/watson/EVALUATION.md`.

## Pipeline

```
completed call
  -> CallIntelligenceProvider.indicators_for
  -> feature extraction
  -> candidate retrieval
  -> similarity against each candidate's closest member
  -> associate, or open a new campaign
  -> CampaignAssociation and a campaign.association.decided event
```

`AssociationPipeline` takes the provider, campaign store, event emitter, and `ScoringConfig` as constructor arguments.

## Tiers

Leaf scores live on `CampaignAssociation.feature_scores`. Missing evidence scores 0. Weights are not renormalized. Caller id is stored on the call record and is not a feature, so a repeat caller who changes pretext does not merge on the CLI/ANI.

| Tier | Role | Leaves |
| --- | --- | --- |
| A anchors | association score | `phone_e164`, `case_id`, `domain_registrable`, `email_domain_registrable`, `claimed_company_normalized` |
| B script | association score | `opening_script_text`, `opening_script_fingerprint`, `script_phrase_normalized`, `pretext_category_canonical`, `transfer_destination_claimed`, `script_language` |
| C structure | retrieval and tie-break only | `timing`, `duration`, `ivr_prompts` |

`timing` and `duration` come from call-store `started_at` / `ended_at` (including simultaneous calls when the intervals overlap). They are not Observations. `ivr_prompts` is an Observation when the honeypot recorded a path. Tier C's group weight on `association_score` is 0. When two candidates share an association score, the higher tier-C score wins, then the lower campaign id, then the lower member call id.

| Feature | Source | Comparison |
| --- | --- | --- |
| `phone_e164` | `phone_e164` entries with `source` `callback` or `spoken`, from `callback_numbers` and `spoken_numbers` | 1.00 when any E.164 number is shared |
| `case_id` | Observation kind `other` (case, badge, or reference numbers). Reasons also cite `identifier_kind=case_id` | 1.00 on a shared normalized id |
| `domain_registrable` | `domain_registrable`, from `domains` and `urls` | 1.00 on a shared host with scheme, path, and `www` removed |
| `email_domain_registrable` | `email` local/domain split plus `email_domain_registrable` | 1.00 when local and domain both match; 0.70 when only the registrable domain matches |
| `claimed_company_normalized` | `claimed_company_normalized` and the distinct `calling_from` observation | 1.00 when the normalized names intersect. Reasons name whichever of the two fields supplied the name |
| `opening_script_text` | `opening_script_text`, otherwise joined `opening_turns`, otherwise the first 70 transcript words | max(token Jaccard, near-copy edit-distance bucket). `opening_turns` are cited in the reason and are not a second weighted leaf |
| `opening_script_fingerprint` | inference fingerprint string | 1.00 on an equal fingerprint. This is a stable label, not a vector |
| `script_phrase_normalized` | `script_phrases` and inference phrases | overlap coefficient |
| `pretext_category_canonical` | inference pretext | 1.00 on an equal category |
| `transfer_destination_claimed` | that observation | 1.00 on a shared destination |
| `script_language` | `script_language` | 0 when both sides are `en` (cited anyway). 1.00 when both sides share some other language |
| `timing` | call store | 1.00 if intervals overlap, 0.80 within 120s, 0.50 within 300s, 0.20 within 3600s, else 0 |
| `duration` | call store | `1 - abs(a-b) / max(a, b, 1)` |
| `ivr_prompts` | `ivr_prompts` | 1.00 on an identical step list, else sequence edit-distance ratio |

Edit-distance buckets apply only to opening text: 1.00 when the normalized ratio is at least 0.90, 0.85 when it is at least 0.80, and 0 below that. Parallel boilerplate that is merely similar in shape does not get a bucket boost.

Observations, and the correlation inference as a whole, are dropped when confidence is below `ScoringConfig.min_observation_confidence` (0.50).

## Score

Group scores are weighted sums of their leaves. Defaults are on `ScoringConfig`.

| Group | Weight | Leaves |
| --- | --- | --- |
| anchor | 0.60 | phone 0.28, case id 0.16, domain 0.22, email 0.16, company 0.18 |
| script | 0.40 | opening text 0.32, fingerprint 0.22, phrases 0.20, pretext 0.12, transfer destination 0.10, language 0.04 |
| structure | 0.00 | timing 0.50, duration 0.20, IVR 0.30 |

`association_score = 0.60 * anchor + 0.40 * script + 0.00 * structure`.

Structure alone scores 0.00. A near-copy script with no anchors stays under the default threshold, because the script group weight is 0.40. Full anchor agreement scores 0.60 and can associate without a matching script.

## Decision

Retrieval is high recall. A prior campaign is a candidate when it shares a phone, case id, domain, email registrable domain, company (including `calling_from`), phrase, fingerprint, or pretext, when opening or transcript Jaccard is at least 0.08, or when a member call falls within 900 seconds. Caller id is not a retrieval key.

Associate with the best candidate only when both are true:

1. `association_score >= associate_threshold` (default **0.50**).
2. Evidence guard: anchor group `>= 0.34`, or script group `>= 0.85`.

Otherwise the call opens a new campaign. A brand-new store yields score 0. A rejected candidate keeps its score on the result so the miss is visible; `matched_call_id` is that closest call.

Reasons always include the decision sentence (score and threshold) and the tier totals. Leaf lines are included when an anchor or script score is at least 0.20, when `script_language` has a detail line, or when a structure score is at least 0.50. Structure lines say they come from the call store when they do.

## What this slice does not do

- Embeddings, dense vectors, clustering, or a learned threshold.
- Organization aliases (`I.R.S.` does not match `Internal Revenue Service`).
- Persistence. `CampaignStore` is in memory.
- A platform event bus. `InMemoryEventEmitter` records `campaign.association.decided` locally until a shared envelope exists.
