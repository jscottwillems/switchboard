# WATSON handoff

Campaign association scoring for Project Switchboard. This slice is a deterministic, explainable baseline. Embeddings are not the scorer.

`docs/STATUS.md` was not on `main` when this branch was cut, so this note lives here instead of a WATSON section inside a STATUS file ATLAS owns.

## Completed

- Typed `CampaignAssociation` results: `call_id`, `campaign_id`, `association_score` in `[0, 1]`, `reasons`, and per-feature `feature_scores`.
- Pipeline: completed call, feature extraction, candidate retrieval, similarity, associate-or-new decision, in-memory `campaign.association.decided` event.
- Eleven deterministic features (opening, transcript, phrases, organization, callback, domain, email pattern, timing, duration, transfer, IVR). Near-copy edit-distance buckets, token Jaccard, identifier overlap, and time windows. No embeddings.
- Thin SHERLOCK adapter (`CallIntelligenceProvider`) plus `FixtureIntelligenceProvider`. Confidence below 0.50 is dropped.
- Labeled synthetic dataset, 15 calls, 8 ground-truth campaigns: near-duplicate scripts, unrelated calls, partial script overlap, and one caller id reused across two campaigns while IRS callback and email rotate.
- Evaluation at explicit thresholds. Operating point is `associate_threshold` 0.50 plus the evidence guard in `ScoringConfig`.

On that dataset the pairwise operating point and the online pipeline are both precision 1.000 and recall 1.000 (TP 11, FP 0, FN 0, TN 94). Same-campaign scores are at least 0.8791. Different-campaign scores are at most 0.1204. Partial IRS/bank overlap scores 0.1204 and is retrieved, then rejected. The repeat caller on a tech-support pretext scores 0.0115 against the IRS campaign.

## Files

- `watson/` scoring package (`features`, `scoring`, `retrieval`, `decision`, `pipeline`, `store`, `events`, `evaluate`, `cli`)
- `watson/sherlock/` adapter protocol, observation models, fixture provider
- `watson/synthetic.py` and `data/synthetic/dataset.json`
- `docs/watson/SCORING.md` weights, threshold, decision rule
- `docs/watson/SHERLOCK_ADAPTER.md` indicator contract
- `docs/watson/EVALUATION.md` generated measurement (regenerate with the CLI)
- `tests/` pytest suite

## Interfaces

- `CampaignAssociation` in `watson/models.py`
- `CallIntelligenceProvider.indicators_for` and `ObservationKind` in `watson/sherlock/`
- `ScoringConfig` in `watson/config.py` (threshold 0.50, group weights 0.70 / 0.25 / 0.05)
- Event `campaign.association.decided` (`producer=watson`) in `watson/events.py`. Envelope is local until a shared events contract exists.
- CLI: `python3 -m watson evaluate`, `python3 -m watson run`, `python3 -m watson export-dataset`

`matched_call_id` is the member the score was computed against. On `new_campaign` it is the closest rejected call when retrieval found one.

## Tests

```
python3 -m pip install -e ".[dev]"
python3 -m pytest
python3 -m watson evaluate
python3 -m watson run
```

34 tests cover normalization, confidence filtering, opening and IVR precedence, the weighted formula, partial-overlap rejection, script-only association, structure-only non-association, the evidence guard, threshold boundaries, ground-truth partition, dataset/report freshness, and the CLI.

## Dependencies

- Python >= 3.11
- pydantic >= 2.6
- pytest (dev)
- No network calls, model weights, or SHERLOCK process

Unfinished neighbors are mocked: indicators come from the fixture provider, and events stay in `InMemoryEventEmitter`.

## Blockers

- SHERLOCK's real observation schema is not on `main`. The kinds in `docs/watson/SHERLOCK_ADAPTER.md` are the fields WATSON scores, not a claim about SHERLOCK's storage model.
- ATLAS docs (`ARCHITECTURE`, `API_CONTRACTS`, `EVENTS`, `DATA_MODEL`, `SECURITY`, `DECISIONS`, `STATUS`) were not on `main`. This slice does not invent them.
- No completed-call ingress and no durable campaign store.
- Organization aliases are not implemented.
- The 0.50 threshold is justified by the synthetic gap (0.12 vs 0.88). It is not calibrated on live honeypot calls.

## Recommended next work

1. Implement `CallIntelligenceProvider` against SHERLOCK once its schema is real, without pushing extraction into the scorer.
2. Persist `CampaignStore` and consume completed-call events once those contracts exist.
3. Add an organization and callback alias table (`I.R.S.` versus `Internal Revenue Service`).
4. Keep this labeled set as the regression baseline. If embeddings or clustering are tried later, report their FP/FN next to `docs/watson/EVALUATION.md` and keep reasons on every positive decision.
5. Revisit `associate_threshold` only with a broader labeled sample. The synthetic gap is wide; partial script overlap must stay under the line.
