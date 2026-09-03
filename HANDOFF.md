# DecarbX — Build Handoff

**Purpose:** any assistant or developer can resume this build cold from this file alone. Read this, then `CLAUDE.md` for the full spec.

**Update rule:** this file is rewritten as part of every phase commit. If the timestamp below is older than the last git commit, do not trust the state section — run the verification commands and rebuild the picture yourself.

Last updated: Phase 2 partial — lineage endpoint done, repo made deploy-ready
Deadline: 3 hours total from start. Track remaining time before choosing what to cut.

---

## Context in one paragraph

Placement-drive demo of "Nexgile-DecarbX", an enterprise carbon intelligence platform. Built against a 2-page functional requirements document describing Scope 1/2/3 accounting, product LCA, supplier engagement, AI analytics, regulatory disclosure, and carbon finance. That document is a multi-year enterprise roadmap; this is a deliberately scoped 3-hour vertical slice. The one feature that must work flawlessly is **audit-grade lineage**: any emission figure on the dashboard clicks through to activity data, unit conversion, versioned emission factor, formula, source document, and approval. Everything else is negotiable.

## Stack and ports

- `backend/` FastAPI + SQLAlchemy 2.x + SQLite (`backend/decarbx.db`) on `:8000`
- `frontend/` React 18 + Vite + TS + Tailwind + Recharts on `:5173` — internal enterprise app
- `portal/` Angular 17 standalone components on `:4200` — external supplier portal
- `./run.sh` starts all three. Both frontends proxy `/api` and `/storage` to `:8000`.

Two frontends is deliberate, not redundancy. The client required React and Angular; the requirements document describes a multi-party platform, so internal users get React and external suppliers get Angular, sharing one API. No screen is built twice. This is the answer to give if asked.

No Docker, Redis, Celery, S3, OCR, or LLM calls anywhere. Background work uses FastAPI `BackgroundTasks`. Auth is a role dropdown in the header, no login, because the source document explicitly excludes security standards.

## State: what is done

**Phase 0 — scaffolding.** Complete, committed. All three servers verified running, both proxies pass `/api` and `/storage`, evidence PDFs render in-browser.

**Phase 1 — data model, seed, calculation engine.** Complete, committed, verified.

- 813 activity rows across 4 facilities, 24 months (Jan 2024 – Dec 2025)
- 909 calculations (96 electricity activities are dual-reported location + market, so calcs exceed activities). 798 approved, 111 draft.
- 10 evidence PDFs, generated from seeded quantities at seed time and sha256-verified

Totals (recheck these after any seed change):

| | 2024 | 2025 | Total | Share |
|---|---|---|---|---|
| Scope 1 | 5,364.0 | 5,351.0 | 10,714.9 | 5.7% |
| Scope 2 location-based | 35,557.0 | 34,512.8 | 70,069.8 | 37.4% |
| Scope 2 market-based | 18,862.1 | 19,263.9 | 38,126.1 | |
| Scope 3 | 52,876.1 | 53,476.7 | 106,352.8 | 56.8% |
| **Gross, location-based** | 93,797.1 | 93,340.4 | **187,137.5** | |
| **Gross, market-based** | | | **155,193.8** | |

Emissions are near-flat year on year by design, so the target trajectory shows a real gap to close.

**Phase 2 — routers. Partially done.** `GET /api/v1/emissions/{id}/lineage` is complete and verified; it was built first and alone, before any other router, because everything else hangs off it.

- `engine/lineage.py` reconstructs the chain purely from what the calculator recorded. Nothing is recomputed, so a superseded factor still shows the version that actually produced the number.
- Chain: `reported_value → calculation → unit_conversion → emission_factor → activity_data → evidence → approval`
- Verified against 9 real emission ids covering every interesting case, not just the happy path: location-based (37), market-based on a REC (38), market-based residual proxy (288), 75% equity share (729), superseded factor v1 (11), unapproved draft (47), missing evidence with estimated quality (657), identity unit conversion (778), the Pune anomaly (316). Unknown id returns 404.

**Post-Phase-1 fixes applied:**

1. Consolidation moved to a single org-level equity-share basis (was inconsistently per-entity, which violates GHG Protocol). Totals unchanged by this fix.
2. Seed variance raised to 12–18% CV with the Pune anomaly retuned to z = 5.00 (was CV under 4% with z = 57.8, which looked synthetic and made anomaly detection trivial). **This changed the totals** — the table above is post-fix. Gross went 181,269.9 → 187,137.5 because lognormal rescaling raises the arithmetic mean.
3. Seeded audit timestamps made period-relative. Calculations were being stamped with the moment the seed ran, so a Jun-2024 record showed an approval dated today — on the screen the entire demo rests on. Now stamped four days after period end, approved two days later.

**Repo is deploy-ready.** `render.yaml` (backend), `frontend/vercel.json` and `portal/vercel.json` (one Vercel project each, Root Directory set to the respective folder). Both frontends build clean for production; Angular output is `dist/portal/browser`.

## State: what is not done

**Both UIs are still scaffolding.** They health-check the API and render nothing else. Anyone deploying this right now gets a working API and two near-empty pages — do not describe it as a demoable product yet.

Remaining Phase 2 routers: org, activities, factors, calculations, emissions summary, analytics, suppliers, products, scenarios, compliance, finance, supplier portal. Then Phase 3 (React dashboard/accounting/lineage panel), Phase 4 (Angular supplier portal), Phase 5 (suppliers, products/PCF, scenarios), Phase 6 (compliance + finance cards). See `CLAUDE.md` section 9 for time boxes and cut order.

## Verification — run these before trusting anything

```bash
cd backend && python verify_phase1.py     # rebuilds DB and re-asserts all invariants
./run.sh                                  # all three servers
curl localhost:8000/api/v1/emissions/37/lineage
```

`verify_phase1.py` asserts twelve invariants:
- Hand-check: 1,568.06 MWh × 1000 × 0.716 = 1,122,731.0 kgCO2e, matching stored `formula_text`
- All 909 calculations converted into their factor's unit rather than assuming a match
- Factor versioning has real work to do: 60 calcs on EF-GRID-IN-01 (2024), 60 on EF-GRID-IN-02 (2025)
- One consolidation basis org-wide, and `Entity` no longer carries a `consolidation_method` attribute at all
- All 96 electricity activities dual-reported location + market
- All 36 activity series have CV within 12–18% (measured excluding the deliberate anomaly)
- Pune Aug-2025 gas anomaly at z = 5.00, asserted within 4.0–6.0
- Deliberate gaps present: Munich waste Q4-2025, Chennai refrigerant
- All evidence PDFs state the exact activity quantity and match stored sha256
- Audit timestamps track their period, not the seed run time
- Data quality is genuinely mixed across primary/secondary/estimated

## Decisions already made — do not silently reverse these

1. **Single equity-share consolidation basis, set at org level.** Mixing operational control and equity share across entities in one inventory is non-compliant. India at 100% ownership yields 100% either way; Munich is 75%.
2. **Market-based residual-mix fallback.** No German market factor exists in the seeded library, so only Hyderabad gets the near-zero REC factor and other sites fall back to their grid factor as a residual-mix proxy. This is standard GHG Protocol practice and is commented in the code.
3. **Evidence PDFs are generated from seeded quantities, never hardcoded.** An earlier hardcoded pass produced a Jul-2025 invoice reading 1,780 MWh against a different activity quantity. That mismatch sits at the bottom of the lineage chain and is exactly what an evaluator would open and catch. Any change to seeded quantities must regenerate the PDFs.
4. **Approved calculations are immutable.** Recalculation creates a new `calc_version`, marks the old row `superseded`, sets `superseded_by_id`, and deletes the stale emission row so totals cannot double-count. Never mutate in place.
5. **Scenarios never write to `emissions` or `calculations`.** Computed in memory and returned, with an "approved actuals unchanged" badge in the UI. This is an explicit requirement in the source document.
6. **Scope 3 at 57% is below the 70–90% typical for manufacturing.** Kept deliberately so Scope 1 and 2 stay visible on the donut. Describe it as a demo composition, never as a representative benchmark.
7. **Seed variance is normalised, not merely randomised.** Each series is an AR(1) walk in log space, then rescaled so its CV lands in a 13–17% target band. At n=24 an unconstrained walk scatters ±5 points and two thirds of series fall outside the band. The Pune spike is specified in standard deviations, not as a multiplier, so its severity is stable however the series is scaled.
8. **The lineage `unit_conversion` step renders even when the multiplier is 1.0**, and a missing source document renders as an explicit step rather than being omitted. "We checked and the units matched" is a different claim from silence, and an invisible gap in an audit trail is worse than a visible one.

## Known risks

- Angular scaffold and first build are slow. If resuming mid-build, check `portal/` actually compiles before assuming Phase 4 is startable.
- Phase 4 (Angular) outranks Phases 5 and 6. Two working frontends is an explicit client requirement; the Products, Scenarios, and Compliance pages are not. If behind, cut the portal to two routes (invite, submit) rather than dropping it.
- If Phase 3 is not done by the 1:55 mark, stop adding pages and polish the dashboard and lineage panel only.
- **Open gap:** emission 38's market-based claim rests on the REC certificate, but the lineage shows the electricity invoice, because `evidence_id` lives on `activity_data` and both calculations share one activity. `REC_Certificate_FY2025_Hyderabad.pdf` is seeded but unreferenced. Linking evidence per calculation needs a schema change — decide whether it is worth it before an auditor-minded evaluator asks.
- **Deploy placeholder:** `frontend/vercel.json` and `portal/vercel.json` both contain `REPLACE-WITH-YOUR-RENDER-URL.onrender.com`. Both must be edited before a Vercel deploy will reach the API.
- **Render free tier is ephemeral.** `decarbx.db` and `./storage/` rebuild on every cold start. Harmless because the seed is deterministic, but the first request after a cold start pays the seeding cost.

## Honesty constraint

The README must carry a plain "Scope and honest limitations" section stating what is implemented, what is stubbed (ERP connectors, OCR, XBRL, real i18n, tenant isolation), and that emission factors are publicly-cited approximations rather than a licensed library. Do not let any assistant generate marketing copy claiming CBAM or CSRD compliance that was not built. One caught overclaim discounts the whole build. The README currently states plainly that both UIs are scaffolding — keep that accurate as they get built.
