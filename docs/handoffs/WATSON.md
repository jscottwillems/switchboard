# WATSON handoff

Campaign association scoring for Project Switchboard. This slice is a deterministic, explainable baseline. Embeddings are not the scorer. Attribution (`CampaignAssociation`) is WATSON-owned. Sherlock does not invent campaign ids.

`docs/STATUS.md` on `main` did not exist when this branch started. The Atlas skeleton now has a STATUS file on its own branch. This note stays here so WATSON does not take over that file.

## Completed

- Typed `CampaignAssociation` results: `call_id`, `campaign_id`, `association_score` in `[0, 1]`, `reasons`, and per-feature `feature_scores`. Finding matches cite kind and value (`callback_number +18005550101`).
- Pipeline: completed call, findings, feature extraction, candidate retrieval, similarity, associate-or-new decision, in-memory `campaign.association.decided` event.
- Live input is `IntelligenceFinding` from `packages/schemas` (`switchboard_schemas.interpretations.IntelligenceFinding`), vendored from SB-009 commit `cfa727a`. `callback_number` is the primary tier A anchor and is enough to associate. The other `FindingKind` values are scored when present and are fixture-only until ATLAS expands emission.
- Labeled synthetic dataset version 3, 15 calls, 8 ground-truth campaigns. Callback values are literal E.164. One caller id is reused across two campaigns. IRS `irs-4` rotates the callback number and still joins through organization, url, payment method, case id (`other`), pretext, and person name.
- Evaluation at explicit thresholds. Operating point is `associate_threshold` 0.50 plus anchor evidence `>= 0.50`.

On that dataset the pairwise operating point and the online pipeline are both precision 1.000 and recall 1.000 (TP 11, FP 0, FN 0, TN 94). Same-campaign scores are at least 0.8927. Different-campaign scores are at most 0.0340. Partial IRS/bank overlap scores 0.0340 and is retrieved, then rejected. The repeat caller on a tech-support pretext scores 0.0146 against the IRS campaign.

## Files

- `packages/schemas` canonical contracts from SB-009 (not a second finding model)
- `watson/` scoring package (`features`, `scoring`, `retrieval`, `decision`, `pipeline`, `store`, `events`, `evaluate`, `cli`)
- `watson/sherlock/` `FindingProvider` and `FixtureFindingProvider`
- `watson/synthetic.py` and `data/synthetic/dataset.json`
- `docs/watson/SCORING.md` weights, threshold, decision rule
- `docs/watson/SHERLOCK_ADAPTER.md` finding contract, emitted vs planned kinds
- `docs/watson/EVALUATION.md` generated measurement (regenerate with the CLI)
- `tests/` pytest suite

## Interfaces

- `CampaignAssociation` in `watson/models.py`
- `FindingProvider.findings_for` in `watson/sherlock/interface.py`
- `IntelligenceFinding`, `FindingKind`, `FindingStatus` from `switchboard_schemas`
- `ScoringConfig` in `watson/config.py` (threshold 0.50, `callback_number` contribution 0.72)
- Event `campaign.association.decided` (`producer=watson`) in `watson/events.py`. Envelope is local until SB-012.
- CLI: `python3 -m watson evaluate`, `python3 -m watson run`, `python3 -m watson export-dataset`

`matched_call_id` is the member the score was computed against. On `new_campaign` it is the closest rejected call when retrieval found one. Ties break by association score, then tier-C score, then campaign id, then call id.

## Tests

```
python3 -m pip install -e ".[dev]"
PYTHONPATH=packages/schemas python3 -m pytest
PYTHONPATH=packages/schemas python3 -m watson evaluate
```

pytest is also configured with `pythonpath = ["packages/schemas"]`.

34 tests cover confidence and rejected-status filtering, literal E.164 callback handling, the other FindingKind values, the weighted formula, partial-overlap rejection, transcript-only non-association, structure-only non-association, callback association, tier-C tie-break, threshold boundaries, ground-truth partition, dataset/report freshness, and the CLI.

## Dependencies

- Python >= 3.12
- pydantic >= 2.7
- `packages/schemas` (`switchboard-schemas`)
- pytest (dev)
- No network calls and no model weights

Unfinished neighbors are mocked: findings come from the fixture provider, and events stay in `InMemoryEventEmitter`.

## Blockers

- SB-009 is pull request 13, based on `cursor/atlas-architecture-skeleton-05c7`, not on `main`. This branch vendors `packages/schemas` from commit `cfa727a` so the import resolves. A full merge of that branch into this one would also bring the Atlas apps, and this pull request's base is still `main`.
- Sherlock emits only `callback_number` today. `pretext`, `organization_name`, `payment_method`, `url`, `person_name`, and `other` are scored from fixtures and will not appear on live calls until ATLAS expands what Sherlock is allowed to emit.
- SB-010 (persisted findings) and SB-012 (bus consumer writing `attr.*`) are not started.
- The 0.50 threshold is justified by the synthetic gap (0.0340 vs 0.8927). It is not calibrated on live honeypot calls.

## Recommended next work

1. Point `FindingProvider` at `POST /v1/internal/extract` or the SB-010 finding stream once those rows exist, and drop the fixture provider for live calls.
2. When ATLAS adds kinds, keep the fixture weights and re-measure `docs/watson/EVALUATION.md` before retuning.
3. Persist `CampaignStore` and emit `campaign.opened` / `campaign.attribution.proposed` in SB-012.
4. Rebase this branch onto the Atlas skeleton once that tree is the merge base, and delete the vendored copy if `packages/schemas` is already an ancestor.
