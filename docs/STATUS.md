## HANDOFF — RADAR — 2026-09-25T20:47:11Z

Completed:
- Vue 3 + TypeScript + Composition API + Pinia + Vite ops dashboard at `apps/dashboard`.
- Routes: `/dashboard/live`, `/dashboard/calls`, `/dashboard/calls/:id`, `/dashboard/campaigns`, `/dashboard/campaigns/:id`, plus `/dashboard/system`.
- Mock catalog: 3 live calls, 10 history calls, 3 campaigns. Provenance (Observed / Inferred / Unverified) and raw vs derived are separate in the types and on screen.
- `docs/FRONTEND_DATA_REQUIREMENTS.md` lists the fields the UI reads. `OpsDataPort` is the swap point in `apps/dashboard/src/data/client.ts`.

Files changed:
- `README.md`
- `package.json`
- `.gitignore`
- `docs/FRONTEND_DATA_REQUIREMENTS.md`
- `docs/STATUS.md`
- `apps/dashboard/` (app, fixtures, fixture generator, fixture checker)

Interfaces added/changed:
- `OpsDataPort`: `fetchLiveCalls`, `fetchCallHistory`, `fetchCallDetail`, `fetchCampaigns`, `fetchCampaignDetail`, `fetchSystemHealth`
- Read models: `LiveCall`, `CallSummary`, `CallDetail`, `CampaignSummary`, `CampaignDetail`, `TranscriptTurn`, `IntelligenceItem`, `StructuredObservation`, `PipelineLatency`, `TechnicalEvent`, `StateTransition`, `CorrelationReasoning`, `SystemHealth`
- Provenance: `observed | inferred | unverified`. Basis on intelligence: `raw | derived`. Observations keep raw text and interpretation as separate objects, each with provenance.

Tests:
- `npm run check:fixtures` (10 history, 3 live, 3 campaigns, provenance coverage, id links, activity sums)
- `npm run typecheck`
- `npm run build`
- Headless Chrome walk of live (select each call), history filter, call detail, live-call detail, campaign list and detail, system, unknown ids, and a 390px viewport. No page errors.

Dependencies:
- Runtime: `vue`, `vue-router`, `pinia`
- Dev: `vite`, `@vitejs/plugin-vue`, `typescript`, `vue-tsc`, `@types/node`

Blocking issues:
- None for this slice. There is no backend yet; the dashboard does not invent one.

Recommended next work:
- ATLAS: diff `docs/FRONTEND_DATA_REQUIREMENTS.md` against the backend read models and flag any missing fields before the HTTP adapter is written.
- Replace the export in `apps/dashboard/src/data/client.ts` with an HTTP adapter, then a live-call push that still uses `LiveCall`.
- Append transcript turns and latency samples on the live board instead of refreshing a full snapshot.
