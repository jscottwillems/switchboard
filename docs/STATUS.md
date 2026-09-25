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

## HANDOFF — RADAR — 2026-09-25T20:53:27Z

Completed:
- Reports list at `/dashboard/reports` and opener at `/dashboard/reports/:reportId`.
- Mock of CLERK `ReportIndexEntry`, `OpenReportRequest`, and `OpenReportResponse` for the four synthetic report ids. No Python package and no server.
- Format picker defaults to markdown when that format exists. The machine-readable report stays JSON-only, and other formats for it return format-unavailable.
- JSON parts map CLERK fact classes onto Observed / Inferred / Unverified badges. The fact-class token stays visible.
- Existing live, history, call detail, campaign, and system routes are unchanged.

Files changed:
- `apps/dashboard/src/types/reports.ts`
- `apps/dashboard/src/lib/reports.ts`
- `apps/dashboard/src/mocks/report-catalog.json`
- `apps/dashboard/src/mocks/parseReports.ts`
- `apps/dashboard/src/mocks/reportFixtures.ts`
- `apps/dashboard/src/mocks/reportFixtureTypes.ts`
- `apps/dashboard/src/mocks/mockAdapter.ts`
- `apps/dashboard/src/data/port.ts`
- `apps/dashboard/src/stores/reports.ts`
- `apps/dashboard/src/views/ReportsView.vue`
- `apps/dashboard/src/views/ReportDetailView.vue`
- `apps/dashboard/src/components/JsonFactTree.vue`
- `apps/dashboard/src/components/AppShell.vue`
- `apps/dashboard/src/router/index.ts`
- `apps/dashboard/src/styles/ops.css`
- `apps/dashboard/scripts/generate-report-fixtures.mjs`
- `apps/dashboard/scripts/check-fixtures.mjs`
- `apps/dashboard/package.json`
- `docs/FRONTEND_DATA_REQUIREMENTS.md`
- `docs/STATUS.md`
- `README.md`

Interfaces added/changed:
- `OpsDataPort.fetchReportIndex(): Promise<ReportIndexEntry[]>`
- `OpsDataPort.openReport(request): Promise<OpenReportResult>` where the success body is CLERK `OpenReportResponse`, and `not_found` / `format_unavailable` cover the two catalog errors
- Fact-class display map (UI only): `confirmed_observation` and `spoken_identifier` → Observed; `reported_caller_metadata` and `raw_observation` → Unverified; `derived_interpretation` and `derived_association` → Inferred

Tests:
- `npm run check:fixtures` now also checks the four report ids, formats, primary filenames, and that every fact class appears in JSON parts
- `npm run typecheck` and `npm run build`
- Headless Chrome: report list, markdown default, JSON badges, CSV parts, machine-readable JSON-only catalog, unavailable markdown on that report, missing id, and `/dashboard/live` still renders

Dependencies:
- None added

Blocking issues:
- None. Report bodies are a compact mock of the CLERK contract, not byte-identical renderer output.

Recommended next work:
- Point `openReport` at CLERK's catalog or a gateway when one exists, and keep this fact-class map in the UI.
- If ATLAS wants the badge map to differ (for example treating reported caller metadata as Observed signaling), that is a display change only.
