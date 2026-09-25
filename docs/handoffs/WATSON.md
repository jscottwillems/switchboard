# WATSON handoff

Campaign association scoring for Project Switchboard. This slice is a deterministic, explainable baseline. Embeddings are not the scorer. Attribution (`CampaignAssociation`) is WATSON-owned. Sherlock does not invent campaign ids.

`docs/STATUS.md` was not on `main` when this branch was cut, so this note lives here instead of a WATSON section inside a STATUS file ATLAS owns.

## Completed

- Typed `CampaignAssociation` results: `call_id`, `campaign_id`, `association_score` in `[0, 1]`, `reasons`, and per-feature `feature_scores`. Reasons cite Observation and Inference field names and the values that matched.
- Pipeline: completed call, feature extraction, candidate retrieval, similarity, associate-or-new decision, in-memory `campaign.association.decided` event.
- Scoring tiers. A anchors (phones, case ids, domains, emails, company including spoken `calling_from`) weight 0.60. B script and narrative weight 0.40. C structure (timing, duration, `ivr_prompts`) weight 0.00 and is retrieval plus tie-break only. Near-copy edit-distance buckets, token Jaccard, shared identifier sets, and time windows. No embeddings and no dense vectors.
- Thin SHERLOCK adapter (`CallIntelligenceProvider`) plus `FixtureIntelligenceProvider`. Observations use Sherlock's span fields. `CorrelationInference` carries the locked correlation fields. Confidence below 0.50 is dropped. CLI/ANI, timing, duration, and simultaneous calls stay on the call record.
- Labeled synthetic dataset version 2, 15 calls, 8 ground-truth campaigns: near-duplicate scripts, unrelated calls, partial script overlap, and one caller id reused across two campaigns while IRS callback numbers and email local-parts rotate.
- Evaluation at explicit thresholds. Operating point is `associate_threshold` 0.50 plus the evidence guard in `ScoringConfig` (anchor group >= 0.34, or script group >= 0.85).

On that dataset the pairwise operating point and the online pipeline are both precision 1.000 and recall 1.000 (TP 11, FP 0, FN 0, TN 94). Same-campaign scores are at least 0.7872. Different-campaign scores are at most 0.0261. Partial IRS/bank overlap scores 0.0261 (`opening_script_text` 0.20, anchors 0) and is retrieved, then rejected. The repeat caller on a tech-support pretext scores 0.0021 against the IRS campaign. A script-only near copy stays under 0.50 because the script group weight is 0.40.

## Files

- `watson/` scoring package (`features`, `scoring`, `retrieval`, `decision`, `pipeline`, `store`, `events`, `evaluate`, `cli`)
- `watson/sherlock/` adapter protocol, observation and correlation-inference models, fixture provider
- `watson/synthetic.py` and `data/synthetic/dataset.json`
- `docs/watson/SCORING.md` weights, threshold, decision rule
- `docs/watson/SHERLOCK_ADAPTER.md` correlation contract and expected import paths
- `docs/watson/EVALUATION.md` generated measurement (regenerate with the CLI)
- `tests/` pytest suite

## Interfaces

- `CampaignAssociation` in `watson/models.py`
- `CallIntelligenceProvider.indicators_for`, `Observation`, `ObservationKind`, and `CorrelationInference` in `watson/sherlock/`
- Expected imports once Sherlock publishes the correlation models: `switchboard_intelligence.schemas.observation.Observation`, `switchboard_intelligence.schemas.observation.ObservationKind`, and `switchboard_intelligence.schemas.inference` for the correlation fields named in `docs/watson/SHERLOCK_ADAPTER.md`
- `ScoringConfig` in `watson/config.py` (threshold 0.50, group weights anchor 0.60 / script 0.40 / structure 0.00)
- Event `campaign.association.decided` (`producer=watson`) in `watson/events.py`. Envelope is local until a shared events contract exists.
- CLI: `python3 -m watson evaluate`, `python3 -m watson run`, `python3 -m watson export-dataset`

`matched_call_id` is the member the score was computed against. On `new_campaign` it is the closest rejected call when retrieval found one. Ties break by association score, then tier-C score, then campaign id, then call id.

## Tests

```
python3 -m pip install -e ".[dev]"
python3 -m pytest
python3 -m watson evaluate
python3 -m watson run
```

35 tests cover normalization, confidence filtering, opening and IVR extraction, `calling_from` kept distinct from `claimed_company`, the weighted formula, partial-overlap rejection, script-only non-association, structure-only non-association, anchor association without script, tier-C tie-break, threshold boundaries, ground-truth partition, dataset/report freshness, and the CLI.

## Dependencies

- Python >= 3.11
- pydantic >= 2.6
- pytest (dev)
- No network calls, model weights, or SHERLOCK process

Unfinished neighbors are mocked: indicators come from the fixture provider, and events stay in `InMemoryEventEmitter`.

## Blockers

- SHERLOCK's correlation fields are not on `main`, and they are not on `cursor/sherlock-intelligence-slice-1574`. That branch's `Inference` is proposition-style and does not include `claimed_company_normalized`, `phone_e164`, `domain_registrable`, the email split, `email_domain_registrable`, `script_phrase_normalized`, `opening_script_fingerprint`, `pretext_category_canonical`, or `identifier_kind`. WATSON's `CorrelationInference` matches the locked names and should be replaced by the import paths above when that PR grows them. The spoken "calling from" kind is spelled `calling_from` here.
- ATLAS docs (`ARCHITECTURE`, `API_CONTRACTS`, `EVENTS`, `DATA_MODEL`, `SECURITY`, `DECISIONS`, `STATUS`) were not on `main`. This slice does not invent them.
- No completed-call ingress and no durable campaign store.
- Organization aliases are not implemented.
- The 0.50 threshold is justified by the synthetic gap (0.0261 vs 0.7872). It is not calibrated on live honeypot calls.

## Recommended next work

1. Implement `CallIntelligenceProvider` against SHERLOCK once the correlation models exist, importing the paths in `docs/watson/SHERLOCK_ADAPTER.md` and deleting the local stand-in.
2. Persist `CampaignStore` and consume completed-call events once those contracts exist.
3. Add an organization and callback alias table (`I.R.S.` versus `Internal Revenue Service`).
4. Keep this labeled set as the regression baseline. If embeddings or clustering are tried later, report their FP/FN next to `docs/watson/EVALUATION.md` and keep reasons on every positive decision.
5. Revisit `associate_threshold` only with a broader labeled sample. The synthetic gap is wide; partial script overlap must stay under the line.
