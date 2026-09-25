# WATSON scoring

WATSON assigns each completed call to a campaign with a deterministic score in `[0, 1]`. Every decision carries human-readable reasons and the leaf feature scores those reasons cite. Embeddings and clustering are not used.

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

## Features

Leaf scores live on `CampaignAssociation.feature_scores`. Missing evidence scores 0. Weights are not renormalized, so one weak feature cannot fill the score. Caller id is stored on the call record and is not a feature, so a repeat caller who changes pretext does not merge on the phone number alone.

| Feature | Source | Comparison |
| --- | --- | --- |
| `opening_script` | SHERLOCK `opening_script` observation, otherwise the first 70 words of the transcript | max(token Jaccard, near-copy edit-distance bucket) |
| `transcript` | call transcript | token Jaccard after stopword removal |
| `repeated_phrases` | SHERLOCK `repeated_phrase` observations | overlap coefficient of normalized phrases |
| `claimed_organization` | SHERLOCK `claimed_organization` | overlap of normalized names; legal suffixes stripped |
| `callback_identifiers` | SHERLOCK `callback_identifier` | overlap of digit-normalized phone numbers |
| `domains` | SHERLOCK `domain` | overlap of hosts; scheme, path, and `www` stripped |
| `email_patterns` | SHERLOCK `email_pattern` | 1.00 on an exact address, 0.70 when only the email domain matches |
| `timing` | call start and end | 1.00 if intervals overlap, 0.80 within 120s, 0.50 within 300s, 0.20 within 3600s, else 0 |
| `duration` | call start and end | `1 - abs(a-b) / max(a, b, 1)` |
| `transfer_behavior` | `call.transferred` | 1.00 only when both calls were transferred |
| `ivr_structure` | `call.ivr_path`, otherwise a SHERLOCK `ivr_structure` observation | 1.00 on an identical path, else sequence edit-distance ratio |

Edit-distance buckets apply only to opening text: 1.00 when the normalized ratio is at least 0.90, 0.85 when it is at least 0.80, and 0 below that. Parallel boilerplate that is merely similar in shape does not get a bucket boost. On the synthetic IRS-versus-bank opening the ratio is about 0.50, so the bucket is 0 and the opening score is the token Jaccard (0.20).

Observations with confidence below `ScoringConfig.min_observation_confidence` (0.50) are dropped before scoring.

## Score

Group scores are weighted sums of their leaves. Defaults are on `ScoringConfig`.

| Group | Weight | Leaves |
| --- | --- | --- |
| script | 0.70 | opening 0.45, transcript 0.35, phrases 0.20 |
| identifier | 0.25 | organization 0.34, callback 0.30, domain 0.20, email 0.16 |
| structure | 0.05 | timing 0.35, duration 0.20, transfer 0.20, IVR 0.25 |

`association_score = 0.70 * script + 0.25 * identifier + 0.05 * structure`.

Structure alone tops out at 0.05. Identifier agreement alone tops out at 0.25. A near-copy script with no indicators still clears the default threshold (the script-only fixture scores about 0.59).

## Decision

Retrieval is high recall. A prior campaign is a candidate when it shares an organization, callback, domain, email, or phrase, when opening or transcript Jaccard is at least 0.08, or when a member call falls within 900 seconds.

Associate with the best candidate only when both are true:

1. `association_score >= associate_threshold` (default **0.50**).
2. Evidence guard: script group `>= 0.40`, or identifier group `>= 0.50` and script group `>= 0.25`.

Otherwise the call opens a new campaign. Ties break toward the smaller campaign id, then the smaller member call id. A brand-new store yields score 0. A rejected candidate keeps its score on the result so the miss is visible; `matched_call_id` is that closest call.

Reasons always include the decision sentence (score and threshold) and the three group scores with their weights. Leaf lines are included when a script or identifier score is at least 0.20, or when a structure score is at least 0.50.

## What this slice does not do

- Embeddings, clustering, or a learned threshold.
- Organization aliases (`I.R.S.` does not match `Internal Revenue Service`).
- Persistence. `CampaignStore` is in memory.
- A platform event bus. `InMemoryEventEmitter` records `campaign.association.decided` locally until a shared envelope exists.
