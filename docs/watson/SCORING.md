# WATSON scoring

WATSON assigns each completed call to a campaign with a deterministic score in `[0, 1]`. Every decision carries human-readable reasons and the leaf feature scores those reasons cite. A finding match cites the finding kind and value. Embeddings and clustering are not used. Sherlock does not assign campaign ids.

The measured gap on the synthetic set is in `docs/watson/EVALUATION.md`. The input contract is `docs/watson/SHERLOCK_ADAPTER.md`.

## Pipeline

```
completed call
  -> FindingProvider.findings_for
  -> feature extraction from IntelligenceFinding rows
  -> candidate retrieval
  -> similarity against each candidate's closest member
  -> associate, or open a new campaign
  -> CampaignAssociation and a campaign.association.decided event
```

`AssociationPipeline` takes the provider, campaign store, event emitter, and `ScoringConfig` as constructor arguments.

## Tiers

Leaf scores live on `CampaignAssociation.feature_scores`. Missing evidence adds 0. Evidence weights are absolute contributions, not renormalized when a kind is absent. The sum is capped at 1. Caller id is stored on the call record and is not a feature, so a repeat caller who changes pretext does not merge on the CLI/ANI.

| Tier | Role | Leaves |
| --- | --- | --- |
| A anchors | association score | `callback_number` 0.72, `organization_name` 0.20, `url` 0.16, `other` 0.14, `payment_method` 0.10 |
| B narrative | association score | `pretext` 0.18, `person_name` 0.06 |
| call store | small association contribution | `transcript_overlap` 0.12 |
| C structure | retrieval and tie-break only | `timing`, `duration` |

`callback_number` is the only kind Sherlock emits today. Its contribution is 0.72, so one shared literal E.164 clears the default threshold without any other finding. Each other kind stays under 0.50 by itself. Several future kinds together can still associate, which is why the synthetic fixtures include them.

`timing` and `duration` come from call-store `started_at` / `ended_at`. They do not add into `association_score`. When two candidates share an association score, the higher tier-C score wins, then the lower campaign id, then the lower member call id.

| Feature | Comparison |
| --- | --- |
| `callback_number` | 1.00 when a literal E.164 value is shared. Non-E.164 text is ignored |
| `organization_name` | 1.00 on a shared normalized name |
| `url` | 1.00 on a shared host; scheme, path, and `www` stripped |
| `payment_method` | 1.00 on a shared normalized method |
| `other` | 1.00 on a shared case or reference token |
| `pretext` | 1.00 on an equal pretext value |
| `person_name` | 1.00 on an equal person-name value |
| `transcript_overlap` | token Jaccard of the opening or the full transcript, from the call store, not a finding |
| `timing` | 1.00 if intervals overlap, 0.80 within 120s, 0.50 within 300s, 0.20 within 3600s, else 0 |
| `duration` | `1 - abs(a-b) / max(a, b, 1)` |

Findings with confidence below 0.50, and findings with status `rejected`, are dropped before scoring. `proposed` and `accepted` both count.

## Decision

Retrieval is high recall. A prior campaign is a candidate when it shares any finding value, when opening or transcript Jaccard is at least 0.08, or when a member call falls within 900 seconds. Caller id is not a retrieval key.

Associate with the best candidate only when both are true:

1. `association_score >= associate_threshold` (default **0.50**).
2. Evidence guard: anchor evidence `>= 0.50`.

A shared `callback_number` produces anchor evidence 0.72, so it passes. Transcript overlap alone tops out at 0.12 and does not pass. Otherwise the call opens a new campaign. A brand-new store yields score 0. A rejected candidate keeps its score on the result; `matched_call_id` is that closest call.

Reasons include the decision sentence and the tier totals. A finding line looks like `callback_number score 1.00: callback_number +18005550101.` Leaf lines appear when the leaf score is at least 0.20, or when a structure score is at least 0.50.

## What this slice does not do

- Embeddings, clustering, or a learned threshold.
- New `FindingKind` members. Those belong to ATLAS in `packages/schemas`.
- Persistence. `CampaignStore` is in memory.
- A platform event bus. `InMemoryEventEmitter` records `campaign.association.decided` locally until SB-012.
